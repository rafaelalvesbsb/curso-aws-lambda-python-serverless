# AGFI Data Pipeline — Guideline

> **Última atualização:** 28 de Abril de 2026
> **Status do Projeto:** Em Produção (LocalStack Homelab) — Pipeline BTG → S3 funcionando

---

## Índice

1. [Visão Geral](#-visão-geral)
2. [Arquitetura](#-arquitetura)
3. [Stacks CloudFormation](#-stacks-cloudformation)
4. [Lambdas](#-lambdas)
5. [Proteção contra Requisições Duplicadas](#-proteção-contra-requisições-duplicadas)
6. [Fluxo de Retry (DLQ)](#-fluxo-de-retry-dlq)
7. [Estrutura de Arquivos](#-estrutura-de-arquivos)
8. [Ambiente Homelab (LocalStack)](#-ambiente-homelab-localstack)
9. [Scheduling via n8n](#-scheduling-via-n8n)
10. [Mapeamento report_type → S3](#-mapeamento-report_type--s3)
11. [Troubleshooting](#-troubleshooting)
12. [Comandos Úteis](#-comandos-úteis)

---

## Visão Geral

Pipeline serverless que extrai relatórios da **API BTG Pactual** via webhook assíncrono e os salva no **S3 Data Lake**.

**Stack tecnológica:**
- **Cloud:** AWS Lambda, S3, SQS, DynamoDB, API Gateway v2, SNS
- **Runtime:** Python 3.13 (x86_64)
- **IaC:** AWS SAM (`samlocal` para LocalStack)
- **Ambiente local:** LocalStack Pro (homelab via WARP), Docker
- **Scheduling local:** n8n (substitui EventBridge, que é mock no LocalStack)
- **Bibliotecas:** `httpx`, `pydantic`, `boto3`, `pandas`, `loguru`, `tenacity`

---

## Arquitetura

```
n8n (schedule seg–sex 08:00 BRT)
    │
    ▼
BTGRequestReportFunction          ← ReservedConcurrentExecutions: 1
    │  Verifica DynamoDB (intent < 5h?) + S3 (arquivo < 5h?)
    │  Claim atômico via ConditionalPut no DynamoDB
    │
    │  para cada relatório não recente:
    ▼
BTG Pactual API  ─────────────────────────────────────────────────┐
(202 Accepted — processamento assíncrono)                         │
                                                              webhook
                                                                   │
                                                                   ▼
                                                     BTGWebhookFunction
                                                     (API GW v2 HTTP API)
                                                     testefastapi.alphaspark.com.br
                                                           │
                                                           │ SQS send_message
                                                           │ (QueueUrl normalizado para
                                                           │  http://localstack:4566/...)
                                                           ▼
                                                     agfi-sync-queue-dev
                                                     VisibilityTimeout: 360s
                                                     maxReceiveCount: 3
                                                           │
                                                           │ SQS trigger
                                                           │ BatchSize: 1
                                                           ▼
                                                    SQSProcessorFunction
                                                    ReservedConcurrentExecutions: 5
                                                           │
                                                           │ httpx download + S3 put_object
                                                           ▼
                                              s3://agfi-data-lake-dev/raw/btg/
                                              └── {report_type}/{timestamp}.{csv|parquet}

                                                    (após 3 falhas)
                                                           │
                                                           ▼
                                                agfi-sync-queue-dlq-dev
                                                           │
                                                           │ SQS trigger
                                                           ▼
                                                BTGDLQReconcileFunction
                                                    │
                                                    │ 1. Arquivo S3 fresco? → discard
                                                    │ 2. Marca intent DynamoDB = error
                                                    │ 3. Invoca BTGRequestReportFunction
                                                    │    {"report_type": "..."}
                                                    └──► (max 3 retentativas, depois SNS alert)
```

---

## Stacks CloudFormation

O projeto usa **dois stacks separados**:

### Stack 1: `agfi-infra-{Environment}`
**Arquivo:** `infra/template.yaml`
**Deploy:** `./infra/deploy.sh`
**Recursos persistentes** (não destruídos entre deploys de Lambda):

| Recurso | Nome | Descrição |
|---------|------|-----------|
| S3 Bucket | `agfi-data-lake-{env}` | Data Lake principal |
| SQS Queue | `agfi-sync-queue-{env}` | Fila principal (VisibilityTimeout: 360s, maxReceiveCount: 3) |
| SQS DLQ | `agfi-sync-queue-dlq-{env}` | Dead Letter Queue (retenção: 14 dias) |
| DynamoDB | `agfi-sync-state-{env}` | Tracking de intents e retry state |
| API GW Domain | `testefastapi.alphaspark.com.br` | Custom domain para webhook |

### Stack 2: `agfi-lambda-{Environment}`
**Arquivo:** `template.yaml`
**Deploy:** `./scripts/homelab.sh`
**Recursos de compute** (Lambda, API Gateway, SNS, Layer):

| Recurso | Descrição |
|---------|-----------|
| `SharedLibrariesLayer` | Layer com btg/, aws/, src/ (numpy, pandas) |
| `BTGWebhookFunction` | Recebe callbacks do BTG |
| `BTGRequestReportFunction` | Solicita relatórios ao BTG |
| `SQSProcessorFunction` | Baixa arquivos e salva no S3 |
| `BTGDLQReconcileFunction` | Re-solicita relatórios falhos |
| `WebhookApi` (API GW v2) | HTTP API para receber webhooks |
| `NotificationsTopic` (SNS) | Alertas de falhas |

---

## Lambdas

### 1. `BTGRequestReportFunction`

**Handler:** `handlers/btg_requests.py::lambda_handler`
**Timeout:** 180s | **Memory:** 256 MB | **Concurrency:** 1 (serializado)

Solicita relatórios à API BTG. Antes de cada requisição, aplica três camadas de proteção contra duplicatas (ver [seção dedicada](#-proteção-contra-requisições-duplicadas)).

**Evento aceito:**
```json
// Roda todos os relatórios (schedule normal do n8n)
{}

// Roda apenas um relatório específico (DLQ Reconcile ou invocação manual)
{ "report_type": "rm-reports-banking" }
```

**Relatórios configurados (10):**

| Método BTGClient | report_type (S3/webhook) |
|-----------------|--------------------------|
| `get_office_informations_by_partner` | `office-informations-by-partner` |
| `get_rm_reports_principality` | `rm-reports-principality` |
| `position_by_partner` | `position-by-partner-refresh` |
| `rm_reports_position` | `rm-reports-position` |
| `rm_reports_registration_data` | `rm-reports-registration-data` |
| `rm_reports_account_base` | `rm-reports-account-base` |
| `rm_reports_representative` | `rm-reports-representative` |
| `rm_reports_banking` | `rm-reports-banking` |
| `rm_reports_openfinance` | `rm-reports-openfinance` |
| `rm_reports_consent_openfinance` | `rm-reports-consent-openfinance` |

---

### 2. `BTGWebhookFunction`

**Handler:** `handlers/webhook_receiver.py::lambda_handler`
**Trigger:** API Gateway v2 `POST /webhook/{proxy+}`
**Endpoint público:** `https://testefastapi.alphaspark.com.br/webhook/{report_type}`

Recebe callbacks do BTG quando um relatório fica pronto. Valida o payload com Pydantic e enfileira no SQS.

**Fix crítico — QueueUrl normalization:**
```python
# boto3 SQS usa o QueueUrl como URL HTTP real da requisição.
# Dentro do container Lambda no LocalStack, "localhost.localstack.cloud"
# resolve para 127.0.0.1 (o próprio container), causando timeout de ~20s.
# Normalizamos para o host interno do Docker:
if aws_endpoint_url and queue_url:
    parsed = urlparse(queue_url)
    queue_url = f"{aws_endpoint_url.rstrip('/')}{parsed.path}"
    # Resultado: http://localstack:4566/000000000000/agfi-sync-queue-dev
```

---

### 3. `SQSProcessorFunction`

**Handler:** `handlers/data_processor.py::lambda_handler`
**Trigger:** SQS `agfi-sync-queue-{env}` (BatchSize: 1)
**Memory:** 512 MB | **Concurrency:** 5

Baixa o arquivo do BTG via URL assinada e salva no S3.

**Path S3:** `raw/btg/{report_type}/{YYYY-MM-DD-HHmmss}.{csv|parquet}`

Usa `batchItemFailures` para partial batch failure — apenas mensagens que falharam voltam para a fila. Após 3 falhas, vai para a DLQ.

---

### 4. `BTGDLQReconcileFunction`

**Handler:** `handlers/btg_dlq_reconcile.py::lambda_handler`
**Trigger:** SQS `agfi-sync-queue-dlq-{env}` (BatchSize: 1)
**Timeout:** 120s | **Memory:** 256 MB

Processa mensagens que falharam 3x na fila principal. Ao invés de chamar o BTG diretamente, **invoca `BTGRequestReportFunction`** com o `report_type` específico, aproveitando toda a lógica de deduplicação já implementada.

**Fluxo:**
1. Arquivo S3 fresco (< 5h)? → discard silencioso (já processado por outro caminho)
2. `retry_count` ≤ `MAX_RETRIES` (3)?
   - Marca intent DynamoDB como `status=error` (libera re-request)
   - Invoca `BTGRequestReportFunction({"report_type": "..."})` — async
3. `retry_count` > `MAX_RETRIES`? → publica alerta no SNS e descarta

---

## Proteção contra Requisições Duplicadas

O `BTGRequestReportFunction` aplica **três camadas** antes de solicitar cada relatório ao BTG, protegendo contra chamadas simultâneas, runs acidentais e re-invocações antes que o BTG termine de processar.

### Camada 1 — DynamoDB Intent (leitura rápida)
```
Existe intent com requested_at < 5h E status ≠ 'error'?
  → Sim: skip (relatório em processamento ou já entregue)
  → Não: continuar
```

### Camada 2 — S3 File Freshness (fallback)
```
Existe arquivo em raw/btg/{report_type}/ com LastModified < 5h?
  → Sim: skip (arquivo já salvo com sucesso)
  → Não: continuar
```

### Camada 3 — Atomic DynamoDB Claim (previne race condition)
```python
# ConditionalPut — apenas UMA execução concorrente passa
table.put_item(
    Item={...status: "requested", requested_at: now},
    ConditionExpression=(
        "attribute_not_exists(sync_id) OR "
        "requested_at < :threshold OR "
        "#s = :error"
    )
)
# ConditionalCheckFailedException → outra execução já ganhou → skip
```

**Resultado:** Mesmo com duas invocações simultâneas (ex: n8n + DLQ Reconcile), apenas uma execução chega a chamar o BTG para cada `report_type`.

### Chave DynamoDB dos intents

```
sync_id:   "btg_request_intent#{report_type}"
timestamp: 0   (fixo — upsert, um registro por report_type)
```

**Status possíveis:** `requested` → `error` (em caso de falha BTG) ou implicitamente `completed` quando arquivo aparece no S3.

---

## Fluxo de Retry (DLQ)

```
SQS Message falha 3x (VisibilityTimeout: 360s cada)
    ↓
agfi-sync-queue-dlq-dev
    ↓
BTGDLQReconcileFunction
    ├── Checa S3: arquivo fresco? → discard (0 retries consumidos)
    ├── retry_count ≤ 3:
    │       marca intent = error no DynamoDB
    │       invoca BTGRequestReportFunction({"report_type": "..."})
    │       BTG envia novo webhook → URL fresca → novo ciclo SQS
    └── retry_count > 3:
            SNS alert → discard (loga para investigação manual)
```

**Tracking de retries no DynamoDB:**
```
sync_id:   "dlq_retry#{report_type}#{first_receive_minute}"
timestamp: 0
status:    "retrying" | "re_requested" | "max_retries_exceeded"
```

O uso de `first_receive_minute` como parte da chave isola contadores entre sessões de teste diferentes.

---

## Estrutura de Arquivos

```
agf-data-pipeline/
│
├── handlers/                          # Lambda entry points
│   ├── btg_requests.py               # ✅ BTGRequestReportFunction
│   ├── webhook_receiver.py           # ✅ BTGWebhookFunction
│   ├── data_processor.py             # ✅ SQSProcessorFunction
│   ├── btg_dlq_reconcile.py          # ✅ BTGDLQReconcileFunction
│   └── requirements.txt
│
├── src/                               # Business logic (source of truth)
│   ├── core/
│   │   ├── logging.py                # Loguru + structlog
│   │   ├── config.py                 # Pydantic settings
│   │   └── exceptions.py
│   ├── etl/
│   │   └── workflows/
│   │       └── request_btg_report.py # Workflow com intent tracking + race condition fix
│   └── models/
│       └── webhook.py                # BTGWebhookPayload, SQSMessagePayload (Pydantic)
│
├── layers/shared-libs/                # Lambda Layer (sincronizado pelo homelab.sh)
│   ├── btg/                          # cliente BTG API
│   ├── aws/                          # utilitários AWS
│   ├── src/                          # cópia de src/ acima
│   └── requirements.txt              # pandas, numpy, httpx, pydantic, loguru...
│
├── infra/
│   ├── template.yaml                 # Stack agfi-infra-{env} (S3, SQS, DynamoDB, Domain)
│   ├── deploy.sh                     # Deploy do stack de infra
│   └── .outputs.env                  # Outputs gerados pelo deploy.sh (não commitar)
│
├── scripts/
│   └── homelab.sh                    # Build + deploy do stack Lambda no LocalStack
│
├── python_libraries/                  # Monorepo — bibliotecas compartilhadas
│   ├── btg/src/btg/                  # BTG API client (OAuth2, retry, 10+ endpoints)
│   └── aws/src/aws/                  # AWS utilities
│
├── template.yaml                      # Stack agfi-lambda-{env} (Lambdas, API GW, SNS)
├── samconfig.toml                     # Configurações SAM (profile local)
└── .env                              # Credenciais locais (não commitar)
```

---

## Ambiente Homelab (LocalStack)

### Pré-requisitos

- LocalStack Pro rodando no servidor (homelab via WARP)
- `samlocal` instalado: `pip install aws-sam-cli-local`
- Tunnel Cloudflare: `testefastapi.alphaspark.com.br` → `http://localstack:4566`

### Deploy completo (primeira vez)

```bash
# 1. Recursos persistentes (S3, SQS, DynamoDB, API GW Domain)
./infra/deploy.sh

# 2. Lambdas + API Gateway + SNS + Layer
./scripts/homelab.sh
```

### Re-deploy após mudança de código

```bash
./scripts/homelab.sh
```

O `homelab.sh` sincroniza automaticamente as bibliotecas para a Layer antes do build.

### O que o homelab.sh faz

1. Verifica pré-requisitos (samlocal, LocalStack acessível, Pro ativado)
2. Verifica stack `agfi-infra-dev` (deve estar `CREATE_COMPLETE`)
3. Carrega outputs da infra (`infra/.outputs.env`)
4. Cria bucket S3 `agfi-sam-artifacts` (artefatos SAM)
5. Sincroniza libs (`btg/`, `aws/`, `src/`) para `layers/shared-libs/`
6. `sam build --config-env local --cached`
7. Remove pyarrow (> 250 MB) e pandas/numpy das funções (já estão na Layer)
8. `samlocal deploy` com parâmetros da infra

### Variáveis de ambiente importantes nas Lambdas

| Variável | Valor (LocalStack) | Descrição |
|----------|-------------------|-----------|
| `AWS_ENDPOINT_URL` | `http://localstack:4566` | Endpoint interno Docker |
| `S3_BUCKET` | `agfi-data-lake-dev` | Data Lake |
| `SQS_QUEUE_URL` | `http://sqs.us-east-2.localhost.localstack.cloud:4566/...` | URL original (normalizada no código) |
| `SYNC_STATE_TABLE` | `agfi-sync-state-dev` | DynamoDB para intent tracking |
| `ENVIRONMENT` | `dev` | |
| `LAMBDA_DOCKER_NETWORK` | `internal_net` | Rede Docker das Lambdas |

### Estrutura S3

```
s3://agfi-data-lake-dev/
└── raw/
    └── btg/
        ├── office-informations-by-partner/   → .parquet
        ├── rm-reports-principality/          → .csv
        ├── position-by-partner-refresh/      → .parquet
        ├── rm-reports-position/              → .csv
        ├── rm-reports-registration-data/     → .csv
        ├── rm-reports-account-base/          → .csv
        ├── rm-reports-representative/        → .csv
        ├── rm-reports-banking/               → .csv
        ├── rm-reports-openfinance/           → .csv
        └── rm-reports-consent-openfinance/   → .csv
```

---

## Scheduling via n8n

O **EventBridge está desabilitado** no LocalStack (é mock — não executa regras). O scheduling é feito pelo n8n.

**Workflow:** `AGFI — BTG Daily Sync (seg–sex 08:00 BRT)`
**Schedule:** `cron(0 11 * * 1-5)` = seg–sex às 11:00 UTC = 08:00 BRT

**Nós do workflow:**
1. **Schedule Trigger** — cron acima
2. **HTTP Request** — invoca `BTGRequestReportFunction` via API Lambda:
   - URL: `http://localstack:4566/2015-03-31/functions/agfi-btg-request-report-dev/invocations`
   - Method: POST
   - Header: `X-Amz-Invocation-Type: Event` (async)
   - Body: `{}` (roda todos os relatórios)

**Para re-run de relatório específico (manual):**
- Body: `{"report_type": "rm-reports-banking"}`

**Para produção AWS:**
Descomentar `DailySyncRule` e `DailySyncPermission` no `template.yaml` (já estão comentados com as configurações corretas: `cron(0 11 ? * MON-FRI *)`).

---

## Mapeamento report_type → S3

O `report_type` é o último segmento do path do webhook BTG (`/webhook/{report_type}`), e corresponde ao nome da pasta no S3.

| report_type (kebab-case) | Método BTGClient | Formato |
|--------------------------|-----------------|---------|
| `office-informations-by-partner` | `get_office_informations_by_partner` | parquet |
| `rm-reports-principality` | `get_rm_reports_principality` | csv |
| `position-by-partner-refresh` | `position_by_partner` | parquet |
| `rm-reports-position` | `rm_reports_position` | csv |
| `rm-reports-registration-data` | `rm_reports_registration_data` | csv |
| `rm-reports-account-base` | `rm_reports_account_base` | csv |
| `rm-reports-representative` | `rm_reports_representative` | csv |
| `rm-reports-banking` | `rm_reports_banking` | csv |
| `rm-reports-openfinance` | `rm_reports_openfinance` | csv |
| `rm-reports-consent-openfinance` | `rm_reports_consent_openfinance` | csv |

Este mapeamento está centralizado em `src/etl/workflows/request_btg_report.py` (`_METHOD_TO_REPORT_TYPE` e `_REPORT_TYPE_TO_METHOD`).

---

## Troubleshooting

### SQS messages acumulando na fila

**Causa:** `BTGRequestReportFunction` foi chamado múltiplas vezes antes dos arquivos aparecerem no S3. O BTG envia **um webhook por arquivo** (não por relatório), e alguns tipos geram múltiplos arquivos.

**Solução:**
```bash
# Purgar a fila principal
awslocal sqs purge-queue \
  --queue-url "http://sqs.us-east-2.localhost.localstack.cloud:4566/000000000000/agfi-sync-queue-dev"

# Purgar a DLQ
awslocal sqs purge-queue \
  --queue-url "http://sqs.us-east-2.localhost.localstack.cloud:4566/000000000000/agfi-sync-queue-dlq-dev"
```

Depois limpar o DynamoDB para permitir novo run:
```bash
# Listar e deletar todos os itens da tabela
awslocal dynamodb scan --table-name agfi-sync-state-dev \
  --query 'Items[*].{sync_id:sync_id.S,timestamp:timestamp.N}' \
  --output json
```

### Webhook retornando timeout (~20s)

**Causa:** `QueueUrl` do SQS contém `localhost.localstack.cloud` que resolve para `127.0.0.1` dentro do container Lambda (o próprio container, não o LocalStack).

**Status:** ✅ Corrigido em `webhook_receiver.py` — o código normaliza o `QueueUrl` para usar `AWS_ENDPOINT_URL` quando disponível.

### Múltiplos containers `btg-request-report` rodando simultaneamente

**Causa:** Múltiplas invocações concorrentes da Lambda.

**Status:** ✅ Corrigido com `ReservedConcurrentExecutions: 1` no `template.yaml`. Apenas uma instância roda por vez.

### Arquivos duplicados no S3

**Causa:** Race condition — duas execuções concorrentes passavam pela verificação de intent antes de qualquer uma gravar.

**Status:** ✅ Corrigido com `ConditionalPut` no DynamoDB (Camada 3 do sistema de proteção). Apenas a execução que ganha o `put_item` condicional prossegue.

### DLQ com mensagens mesmo após re-request

**Causa:** Antiga versão do `btg_dlq_reconcile.py` tinha `NameError: name 'today' is not defined` na função `lambda_handler` quando `retry_count > MAX_RETRIES`.

**Status:** ✅ Corrigido — `today = datetime.now(timezone.utc).strftime("%Y-%m-%d")` adicionado antes do loop.

### LocalStack perdeu dados após reinício

**Causa:** Arquivos do bind mount `/opt/localstack-data` são de propriedade do root — `rm -rf` sem `sudo` falha silenciosamente.

**Solução:**
```bash
sudo rm -rf /opt/localstack-data && sudo mkdir -p /opt/localstack-data
# Depois reiniciar o container LocalStack
# Depois: ./infra/deploy.sh && ./scripts/homelab.sh
```

---

## Comandos Úteis

### Deploy

```bash
# Infra (primeira vez ou após mudança de infra)
./infra/deploy.sh

# Lambdas (após qualquer mudança de código)
./scripts/homelab.sh
```

### Monitoramento

```bash
# Status das filas SQS
awslocal sqs get-queue-attributes \
  --queue-url "http://sqs.us-east-2.localhost.localstack.cloud:4566/000000000000/agfi-sync-queue-dev" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible

# Listar arquivos no S3
awslocal s3 ls s3://agfi-data-lake-dev/raw/btg/ --recursive --human-readable

# Logs de uma Lambda (últimas invocações)
awslocal logs tail /aws/lambda/agfi-btg-request-report-dev --follow
awslocal logs tail /aws/lambda/agfi-btg-webhook-dev --follow
awslocal logs tail /aws/lambda/agfi-sqs-processor-dev --follow
awslocal logs tail /aws/lambda/agfi-btg-dlq-reconcile-dev --follow
```

### Invocar Lambdas manualmente

```bash
# Solicitar todos os relatórios
awslocal lambda invoke \
  --function-name agfi-btg-request-report-dev \
  --payload '{}' \
  /tmp/out.json && cat /tmp/out.json

# Solicitar um relatório específico
awslocal lambda invoke \
  --function-name agfi-btg-request-report-dev \
  --payload '{"report_type": "rm-reports-banking"}' \
  /tmp/out.json && cat /tmp/out.json
```

### Limpar estado para novo teste

```bash
# 1. Purgar filas
awslocal sqs purge-queue --queue-url "http://sqs.us-east-2.localhost.localstack.cloud:4566/000000000000/agfi-sync-queue-dev"
awslocal sqs purge-queue --queue-url "http://sqs.us-east-2.localhost.localstack.cloud:4566/000000000000/agfi-sync-queue-dlq-dev"

# 2. Limpar intents no DynamoDB (scan + batch delete)
python3 -c "
import boto3
ddb = boto3.resource('dynamodb', endpoint_url='http://localhost.localstack.cloud:4566',
                     region_name='us-east-2',
                     aws_access_key_id='test', aws_secret_access_key='test')
table = ddb.Table('agfi-sync-state-dev')
items = table.scan().get('Items', [])
with table.batch_writer() as batch:
    for item in items:
        batch.delete_item(Key={'sync_id': item['sync_id'], 'timestamp': item['timestamp']})
print(f'Deleted {len(items)} items')
"
```

### Verificar outputs dos stacks

```bash
# Stack de infra
awslocal cloudformation describe-stacks \
  --stack-name agfi-infra-dev \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table

# Stack de Lambda
awslocal cloudformation describe-stacks \
  --stack-name agfi-lambda-dev \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table
```

---

**Última atualização:** 28 de Abril de 2026
**Status:** Pipeline BTG → S3 funcionando em homelab LocalStack Pro
