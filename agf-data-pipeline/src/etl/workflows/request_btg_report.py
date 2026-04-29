# src/etl/workflows/request_btg_report.py
import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from btg.client import BTGClient

# Intervalo entre requisições ao BTG para evitar rate limiting
REQUEST_DELAY_SECONDS = 5

# Não re-solicita um relatório se já existe um intent recente ou arquivo S3 < X horas
FRESHNESS_HOURS = 5

# Prefixo de chave no DynamoDB para distinguir de outros registros na tabela
_DYNAMO_KEY_PREFIX = "btg_request_intent"

# Mapeamento: nome do método BTGClient → report_type que o BTG usa no webhook
# (= último segmento do path do webhook e nome da pasta no S3)
_METHOD_TO_REPORT_TYPE: dict[str, str] = {
    "get_office_informations_by_partner": "office-informations-by-partner",
    "get_rm_reports_principality":        "rm-reports-principality",
    "position_by_partner":                "position-by-partner-refresh",
    "rm_reports_position":                "rm-reports-position",
    "rm_reports_registration_data":       "rm-reports-registration-data",
    "rm_reports_account_base":            "rm-reports-account-base",
    "rm_reports_representative":          "rm-reports-representative",
    "rm_reports_banking":                 "rm-reports-banking",
    "rm_reports_openfinance":             "rm-reports-openfinance",
    "rm_reports_consent_openfinance":     "rm-reports-consent-openfinance",
}

# Reverso: report_type (kebab-case) → nome do método
# Usado para filtrar pelo report_type recebido no evento Lambda.
_REPORT_TYPE_TO_METHOD: dict[str, str] = {v: k for k, v in _METHOD_TO_REPORT_TYPE.items()}


# ──────────────────────────────────────────────────────────────────────────────
# DynamoDB helpers
# ──────────────────────────────────────────────────────────────────────────────

def _dynamo_key(report_type: str) -> dict:
    """Chave DynamoDB para o intent de requisição de um relatório."""
    return {
        "sync_id":   f"{_DYNAMO_KEY_PREFIX}#{report_type}",
        "timestamp": 0,  # fixo — um registro por report_type (upsert)
    }


def _has_recent_intent(table, report_type: str) -> bool:
    """
    Retorna True se existe um intent recente (< FRESHNESS_HOURS) com status
    que não seja 'error'. Cobre a janela entre "pedido enviado ao BTG" e
    "arquivo salvo no S3".

    Retorna False (= deve solicitar) quando:
    - Nenhum intent encontrado
    - Intent expirado (>= FRESHNESS_HOURS)
    - Intent recente mas com status='error' (deve retentar)
    """
    key = _dynamo_key(report_type)
    try:
        item = table.get_item(Key=key).get("Item")
    except ClientError as exc:
        print(f"[WARN] DynamoDB get_item failed for {report_type}: {exc} — will request.")
        return False

    if not item:
        return False

    requested_at_str = item.get("requested_at")
    if not requested_at_str:
        return False

    try:
        requested_at = datetime.fromisoformat(requested_at_str)
        if requested_at.tzinfo is None:
            requested_at = requested_at.replace(tzinfo=timezone.utc)
    except ValueError:
        return False

    age_hours = (datetime.now(timezone.utc) - requested_at).total_seconds() / 3600
    status = item.get("status", "requested")

    if age_hours >= FRESHNESS_HOURS:
        print(f"  [{report_type}] Intent is {age_hours:.1f}h old (>= {FRESHNESS_HOURS}h) → will request")
        return False

    if status == "error":
        print(f"  [{report_type}] Intent found ({age_hours:.1f}h ago) but status=error → will retry")
        return False

    print(f"  [{report_type}] Intent found — {age_hours:.1f}h ago (status={status}) → skipping")
    return True


def _try_claim_request(table, report_type: str) -> bool:
    """
    Tenta gravar atomicamente o intent de requisição no DynamoDB.

    Usa ConditionalExpression para garantir que apenas UMA execução concorrente
    consiga avançar para chamar o BTG — mesmo que duas Lambdas passem pela
    verificação de leitura ao mesmo tempo (race condition).

    Retorna True  → esta execução ganhou o "lock", deve chamar o BTG.
    Retorna False → outra execução já gravou um intent recente, deve pular.
    """
    threshold_iso = (
        datetime.now(timezone.utc) - __import__('datetime').timedelta(hours=FRESHNESS_HOURS)
    ).isoformat()

    try:
        table.put_item(
            Item={
                **_dynamo_key(report_type),
                "report_type":  report_type,
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "status":       "requested",
            },
            # Só escreve se: não existe registro OU o existente está expirado OU tem status=error
            ConditionExpression=(
                "attribute_not_exists(sync_id) OR "
                "requested_at < :threshold OR "
                "#s = :error"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":threshold": (datetime.now(timezone.utc) - timedelta(hours=FRESHNESS_HOURS)).isoformat(),
                ":error":     "error",
            },
        )
        return True  # ganhou o lock

    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            print(f"  [{report_type}] Lost race — another execution already claimed this request → skipping")
            return False
        # Erro inesperado: logar mas não bloquear a execução
        print(f"[WARN] DynamoDB conditional put failed for {report_type}: {exc} — proceeding anyway")
        return True


def _mark_error(table, report_type: str, error: str) -> None:
    """Atualiza o status do intent para 'error' após falha na chamada BTG."""
    try:
        table.update_item(
            Key=_dynamo_key(report_type),
            UpdateExpression="SET #s = :s, last_error = :e",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "error", ":e": error},
        )
    except ClientError:
        pass  # melhor esforço


# ──────────────────────────────────────────────────────────────────────────────
# S3 helper
# ──────────────────────────────────────────────────────────────────────────────

def _has_fresh_s3_file(s3_client, bucket: str, report_type: str) -> bool:
    """
    Retorna True se existe um arquivo no S3 para este report_type com menos de
    FRESHNESS_HOURS. Funciona como check secundário: confirma que o arquivo
    foi de fato salvo mesmo que o intent esteja ausente (ex: redeploy limpou DynamoDB).
    """
    prefix = f"raw/btg/{report_type}/"
    try:
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        objects = response.get("Contents", [])
        if not objects:
            return False

        most_recent = max(objects, key=lambda obj: obj["LastModified"])
        age_hours = (
            datetime.now(timezone.utc) - most_recent["LastModified"]
        ).total_seconds() / 3600

        if age_hours < FRESHNESS_HOURS:
            print(
                f"  [{report_type}] S3 file is {age_hours:.1f}h old "
                f"(< {FRESHNESS_HOURS}h) → skipping"
            )
            return True

        return False

    except Exception as exc:
        print(f"[WARN] Could not check S3 for {report_type}: {exc} — will request.")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Workflow
# ──────────────────────────────────────────────────────────────────────────────

class RequestBTGAPIWorkflow:
    """
    Workflow to request reports from the BTG API.

    Ordem de verificação antes de cada requisição:
      1. DynamoDB intent recente (< FRESHNESS_HOURS, status != error)
         → cobre a janela "pedido enviado, BTG ainda processando"
      2. Arquivo S3 fresco (< FRESHNESS_HOURS)
         → fallback: confirma que o arquivo chegou mesmo sem intent válido

    Se ambas falharem → grava novo intent no DynamoDB e chama o BTG.
    """

    async def run_requests(self, report_type: Optional[str] = None):
        """
        Executa as requisições de relatórios ao BTG.

        Args:
            report_type: report_type no formato kebab-case do BTG
                         (ex: "rm-reports-banking", "position-by-partner-refresh").
                         Se None, requisita todos os relatórios configurados.
                         Se especificado, requisita apenas aquele tipo.

        Returns:
            Dict com o resultado por método: status "requested" | "skipped" | "error"
        """
        results = {}

        # ── Clientes AWS ──────────────────────────────────────────────
        endpoint_url = os.environ.get("AWS_ENDPOINT_URL") or None
        region       = os.environ.get("AWS_REGION", "us-east-1")
        table_name   = os.environ.get("SYNC_STATE_TABLE", "agfi-sync-state-dev")
        bucket       = os.environ.get("S3_BUCKET", "agfi-data-lake-dev")

        dynamodb   = boto3.resource("dynamodb", endpoint_url=endpoint_url, region_name=region)
        table      = dynamodb.Table(table_name)
        s3_client  = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)

        print(
            f"RequestBTGAPIWorkflow starting — "
            f"table={table_name}, bucket={bucket}, "
            f"freshness={FRESHNESS_HOURS}h, target={report_type or 'all'}"
        )

        async with BTGClient() as client:
            all_requests = [
                ("get_office_informations_by_partner", client.get_office_informations_by_partner),
                ("get_rm_reports_principality",        client.get_rm_reports_principality),
                ("position_by_partner",                client.position_by_partner),
                ("rm_reports_position",                client.rm_reports_position),
                ("rm_reports_registration_data",       client.rm_reports_registration_data),
                ("rm_reports_account_base",            client.rm_reports_account_base),
                ("rm_reports_representative",          client.rm_reports_representative),
                ("rm_reports_banking",                 client.rm_reports_banking),
                ("rm_reports_openfinance",             client.rm_reports_openfinance),
                ("rm_reports_consent_openfinance",     client.rm_reports_consent_openfinance),
            ]

            # ── Filtrar por report_type específico, se fornecido ──────
            if report_type:
                target_method = _REPORT_TYPE_TO_METHOD.get(report_type)
                if not target_method:
                    known = list(_REPORT_TYPE_TO_METHOD.keys())
                    print(f"[ERROR] Unknown report_type='{report_type}'. Known: {known}")
                    return {
                        report_type: {
                            "status": "error",
                            "error":  f"Unknown report_type '{report_type}'. Known: {known}",
                        }
                    }
                requests_list = [(m, f) for m, f in all_requests if m == target_method]
                print(f"Filtered to 1 report: {target_method}")
            else:
                requests_list = all_requests

            first_request = True  # controla o delay entre requisições reais

            for method_name, request_func in requests_list:
                rtype = _METHOD_TO_REPORT_TYPE.get(method_name, method_name)
                print(f"\nChecking {method_name} (report_type={rtype})...")

                # ── 1. Intent DynamoDB recente? ───────────────────────
                if _has_recent_intent(table, rtype):
                    results[method_name] = {
                        "status":      "skipped",
                        "reason":      f"recent_intent (< {FRESHNESS_HOURS}h)",
                        "report_type": rtype,
                    }
                    continue

                # ── 2. Arquivo S3 fresco? (fallback) ─────────────────
                if _has_fresh_s3_file(s3_client, bucket, rtype):
                    results[method_name] = {
                        "status":      "skipped",
                        "reason":      f"fresh_s3_file (< {FRESHNESS_HOURS}h)",
                        "report_type": rtype,
                    }
                    continue

                # ── Claim atômico no DynamoDB (previne race condition) ─
                # Duas execuções concorrentes podem passar pelas verificações
                # de leitura acima ao mesmo tempo. O put condicional garante
                # que apenas uma delas avance para chamar o BTG.
                if not _try_claim_request(table, rtype):
                    results[method_name] = {
                        "status":      "skipped",
                        "reason":      "lost_race (concurrent execution claimed first)",
                        "report_type": rtype,
                    }
                    continue

                # ── Delay entre requisições reais ─────────────────────
                if not first_request:
                    print(f"Waiting {REQUEST_DELAY_SECONDS}s before next request...")
                    await asyncio.sleep(REQUEST_DELAY_SECONDS)
                first_request = False

                # ── Requisição ao BTG ─────────────────────────────────
                print(f"Requesting BTG report: {method_name}...")
                try:
                    response = await request_func()
                    results[method_name] = {
                        "status":      "requested",
                        "response":    response,
                        "report_type": rtype,
                    }
                    print(f"Response for {method_name}: {response}")
                except Exception as e:
                    _mark_error(table, rtype, str(e))
                    results[method_name] = {
                        "status":      "error",
                        "error":       str(e),
                        "report_type": rtype,
                    }
                    print(f"Error for {method_name}: {e}")

        skipped   = sum(1 for r in results.values() if r["status"] == "skipped")
        requested = sum(1 for r in results.values() if r["status"] == "requested")
        errors    = sum(1 for r in results.values() if r["status"] == "error")
        print(f"\nDone — requested={requested}, skipped={skipped}, errors={errors}")

        return results
