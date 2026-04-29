"""
BTG DLQ Reconciliation Lambda Handler

Processa mensagens da Dead Letter Queue (DLQ) que falharam na fila principal.
Para cada mensagem falha:
  1. Se já existe arquivo S3 fresco (< FRESHNESS_HOURS) → descarta (já processado).
  2. Verifica quantas retentativas já foram feitas (DynamoDB).
  3. Se abaixo do limite:
       - Marca o intent DynamoDB como 'error' (permite que o workflow re-solicite).
       - Invoca BTGRequestReportFunction({"report_type": "..."}) de forma assíncrona.
       - O BTGRequestReportFunction encontra status=error → não pula → re-solicita ao BTG.
       - BTG envia novo webhook com URL fresca → novo ciclo de processamento.
  4. Se limite excedido: notifica via SNS e descarta a mensagem.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

from src.core.logging import setup_logging, get_logger, add_lambda_context
from src.etl.workflows.request_btg_report import (
    FRESHNESS_HOURS,
    _dynamo_key,
    _has_fresh_s3_file,
)

# Máximo de vezes que tentamos re-solicitar o mesmo relatório
MAX_RETRIES = 3


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler para re-solicitação de relatórios via DLQ.

    Triggered por: SQS EventSourceMapping apontando para agfi-sync-queue-dlq-{env}
    """
    setup_logging()
    add_lambda_context(event, context)
    log = get_logger(__name__)

    records = event.get("Records", [])
    log.info("DLQ batch received", batch_size=len(records))

    # ── Clientes AWS ──────────────────────────────────────────────────
    endpoint_url  = os.environ.get("AWS_ENDPOINT_URL") or None
    region        = os.environ.get("AWS_REGION", "us-east-1")
    environment   = os.environ.get("ENVIRONMENT", "dev")
    table_name    = os.environ.get("SYNC_STATE_TABLE", "agfi-sync-state-dev")
    bucket        = os.environ.get("S3_BUCKET", "agfi-data-lake-dev")
    sns_topic_arn = os.environ.get("SNS_TOPIC_ARN", "")

    dynamodb      = boto3.resource("dynamodb", endpoint_url=endpoint_url, region_name=region)
    table         = dynamodb.Table(table_name)
    s3_client     = boto3.client("s3",    endpoint_url=endpoint_url, region_name=region)
    lambda_client = boto3.client("lambda", endpoint_url=endpoint_url, region_name=region)
    sns_client    = boto3.client("sns",   endpoint_url=endpoint_url) if sns_topic_arn else None

    today              = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    batch_item_failures = []
    request_fn_name    = f"agfi-btg-request-report-{environment}"

    for record in records:
        message_id = record.get("messageId", "unknown")
        log_ctx    = log.bind(message_id=message_id)

        try:
            body        = json.loads(record.get("body", "{}"))
            report_type = body.get("report_type", "unknown")
            log_ctx     = log_ctx.bind(report_type=report_type)

            log_ctx.info("Processing DLQ message", original_body=body)

            # ── 1. Arquivo S3 fresco? → já processado, descartar ─────
            if _has_fresh_s3_file(s3_client, bucket, report_type):
                log_ctx.info(
                    "Fresh S3 file found — message already processed, discarding",
                    report_type=report_type,
                )
                continue  # mensagem consumida sem re-request

            # ── 2. Incrementar contador de retentativas no DynamoDB ──
            attrs            = record.get("attributes", {})
            first_receive_ms = attrs.get("ApproximateFirstReceiveTimestamp", "0")
            first_receive_min = (int(first_receive_ms) // 1000 // 60) * 60

            retry_key = {
                "sync_id":   f"dlq_retry#{report_type}#{first_receive_min}",
                "timestamp": 0,
            }

            update_resp = table.update_item(
                Key=retry_key,
                UpdateExpression=(
                    "ADD retry_count :inc "
                    "SET last_attempt = :ts, report_type = :rt, #s = :s_retrying"
                ),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":inc":        1,
                    ":ts":         datetime.now(timezone.utc).isoformat(),
                    ":rt":         report_type,
                    ":s_retrying": "retrying",
                },
                ReturnValues="ALL_NEW",
            )

            retry_count = int(update_resp["Attributes"].get("retry_count", 1))
            log_ctx.info("Retry counter updated", retry_count=retry_count, max=MAX_RETRIES)

            # ── 3. Verificar limite de retentativas ──────────────────
            if retry_count > MAX_RETRIES:
                log_ctx.error(
                    "Max retries exceeded — giving up on this report",
                    report_type=report_type,
                    retry_count=retry_count,
                    date=today,
                )
                table.update_item(
                    Key=retry_key,
                    UpdateExpression="SET #s = :s",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={":s": "max_retries_exceeded"},
                )
                if sns_client and sns_topic_arn:
                    _notify_max_retries(sns_client, sns_topic_arn, report_type, retry_count, today)
                continue  # mensagem consumida

            # ── 4. Marcar intent como 'error' para liberar re-request ─
            # O BTGRequestReportFunction checa o intent no DynamoDB.
            # Se status='error', ele não pula — re-solicita ao BTG.
            try:
                table.update_item(
                    Key=_dynamo_key(report_type),
                    UpdateExpression="SET #s = :s, last_error = :e",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":s": "error",
                        ":e": f"DLQ retry #{retry_count} — {today}",
                    },
                )
                log_ctx.info("Intent marked as error in DynamoDB", report_type=report_type)
            except ClientError as exc:
                log_ctx.warning("Could not mark intent as error", error=str(exc))

            # ── 5. Invocar BTGRequestReportFunction ───────────────────
            payload = json.dumps({"report_type": report_type}).encode()
            log_ctx.info(
                "Invoking BTGRequestReportFunction",
                function=request_fn_name,
                report_type=report_type,
                retry_count=retry_count,
            )

            lambda_client.invoke(
                FunctionName=request_fn_name,
                InvocationType="Event",  # async — não aguarda resultado
                Payload=payload,
            )

            log_ctx.info(
                "BTGRequestReportFunction invoked — waiting for new webhook",
                report_type=report_type,
                retry_count=retry_count,
            )

            # Atualizar contador de retry com status re_requested
            table.update_item(
                Key=retry_key,
                UpdateExpression="SET #s = :s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "re_requested"},
            )

        except Exception as e:
            log_ctx.error(
                "Unexpected error processing DLQ message",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            batch_item_failures.append({"itemIdentifier": message_id})

    log.info(
        "DLQ batch complete",
        total=len(records),
        lambda_failures=len(batch_item_failures),
    )

    return {"batchItemFailures": batch_item_failures}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _notify_max_retries(
    sns_client: Any,
    topic_arn: str,
    report_type: str,
    retry_count: int,
    date: str,
) -> None:
    """Publica alerta no SNS quando max retentativas é excedido."""
    try:
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=f"[AGFI] DLQ max retries: {report_type}",
            Message=json.dumps(
                {
                    "alert":       "max_retries_exceeded",
                    "report_type": report_type,
                    "retry_count": retry_count,
                    "date":        date,
                    "message": (
                        f"Relatório {report_type} falhou {retry_count}x em {date}. "
                        "Verificar logs do SQSProcessor e acessibilidade da BTG API."
                    ),
                },
                indent=2,
            ),
        )
    except Exception as e:
        print(f"[WARN] Failed to publish SNS notification: {e}")
