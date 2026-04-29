# 🧪 Configuração do Ambiente de Teste

## 📋 Visão Geral

Este documento descreve a configuração do ambiente de teste local para validar o pipeline ETL completo antes do deploy em produção.

---

## 🎯 Objetivo

Configurar um ambiente local que simule a AWS para testar:

1. **Requisições à API BTG** → Obter dados cadastrais
2. **Webhook Receiver** → Receber callbacks do BTG via API Gateway (LocalStack)
3. **Processamento de Dados** → Validar schemas, transformar dados
4. **Armazenamento S3** → Salvar tabelas processadas no S3 local

---

## 🏗️ Arquitetura do Ambiente de Teste

```
┌─────────────────────────────────────────────────────────────────┐
│                        AMBIENTE LOCAL                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐         ┌──────────────┐                     │
│  │   BTG API    │────────▶│  btg_sync    │                     │
│  │ (Produção)   │         │   Lambda     │                     │
│  └──────────────┘         └──────┬───────┘                     │
│                                   │                             │
│                                   ▼                             │
│                          ┌─────────────────┐                    │
│                          │  API Gateway    │                    │
│                          │  (LocalStack)   │                    │
│                          └────────┬────────┘                    │
│                                   │                             │
│                                   ▼                             │
│                          ┌─────────────────┐                    │
│                          │ webhook_receiver│                    │
│                          │     Lambda      │                    │
│                          └────────┬────────┘                    │
│                                   │                             │
│                                   ▼                             │
│                          ┌─────────────────┐                    │
│                          │   Validation    │                    │
│                          │   (Pydantic)    │                    │
│                          └────────┬────────┘                    │
│                                   │                             │
│                                   ▼                             │
│                          ┌─────────────────┐                    │
│                          │  S3 (LocalStack)│                    │
│                          │  Parquet Files  │                    │
│                          └─────────────────┘                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🐳 Componentes Docker

### 1. **LocalStack** - Simula serviços AWS

```yaml
services:
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"  # API Gateway unificado
    environment:
      - SERVICES=s3,sqs,lambda,apigateway,cloudwatch,events,iam,sts
      - DEBUG=1
      - PERSISTENCE=1
```

**Serviços Utilizados:**
- ✅ **S3** - Armazenamento de dados (parquet)
- ✅ **API Gateway** - Webhook receiver
- ✅ **Lambda** - Funções serverless
- ✅ **SQS** - Filas de processamento (futuro)
- ✅ **CloudWatch** - Logs

### 2. **MySQL** - Banco de dados local

```yaml
mysql:
  image: mysql:8.0.39
  ports:
    - "3306:3306"
  environment:
    MYSQL_DATABASE: agfi
    MYSQL_USER: agfi_user
```

### 3. **Redis** - Cache (opcional)

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
```

---

## 📂 Estrutura do Pipeline (Primeira Etapa)

### **Fluxo de Dados:**

```
1️⃣  BTG API Request (btg_sync.py)
    ↓
    GET /api/v1/account-management/account/{account}/information
    ↓
    Retorna JSON com holder, users, coHolders
    ↓
2️⃣  Validação (AccountInformationRaw)
    ↓
    Valida estrutura nested JSON
    ↓
3️⃣  Transformação (helpers.py)
    ↓
    _flat_users_key() → user_0_name, user_1_name
    pd.json_normalize() → holder.name → holder_name
    ↓
4️⃣  Validação (AccountInformationFlat)
    ↓
    Valida DataFrame flat
    ↓
5️⃣  Webhook Callback (API Gateway → webhook_receiver.py)
    ↓
    BTG envia link de download do relatório
    ↓
6️⃣  Armazenamento S3
    ↓
    Salva parquet em s3://agfi-data-lake-dev/raw/btg/
```

---

## 🛠️ Configuração Passo a Passo

### **Passo 1: Iniciar Ambiente Docker**

```bash
# No diretório do projeto
cd /Users/lcs/Documents/00-actual-projetcs/00-work/agf/agfi-data-pipeline-working

# Subir containers
docker-compose up -d

# Verificar status
docker-compose ps
```

### **Passo 2: Configurar LocalStack**

```bash
# Criar bucket S3 local
aws --endpoint-url=http://localhost:4566 s3 mb s3://agfi-data-lake-dev

# Listar buckets
aws --endpoint-url=http://localhost:4566 s3 ls
```

### **Passo 3: Deploy das Lambdas (SAM)**

```bash
# Build das funções Lambda
sam build

# Deploy no LocalStack
sam deploy \
  --template-file template.yaml \
  --stack-name agfi-pipeline-dev \
  --parameter-overrides Environment=dev \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --endpoint-url http://localhost:4566
```

### **Passo 4: Configurar Variáveis de Ambiente**

Criar arquivo `.env`:

```bash
# AWS LocalStack
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1

# BTG API
BTG_CLIENT_ID=<seu_client_id>
BTG_CLIENT_SECRET=<seu_client_secret>
BTG_BASE_URL=https://api.btgpactual.com

# HubSpot
HUBSPOT_API_KEY=<sua_api_key>

# Database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=agfi
MYSQL_USER=agfi_user
MYSQL_PASSWORD=agfi_password

# Environment
ENVIRONMENT=dev
LOG_LEVEL=DEBUG
```

---

## 🧪 Testes

### **Teste 1: Requisição BTG API**

```python
# tests/integration/test_btg_api.py
import pytest
from src.btg.client import BTGClient
from src.btg.schemas.account_information import AccountInformationRaw

def test_get_account_information():
    client = BTGClient()
    account_id = "000123456"

    # Fazer requisição
    response = client.get_account_information(account_id)

    # Validar schema
    account = AccountInformationRaw(**response)

    assert account.accountNumber == account_id
    assert account.holder is not None
    assert account.holder.name
```

### **Teste 2: Webhook Receiver**

```bash
# Simular callback do BTG
curl -X POST http://localhost:4566/restapis/{api_id}/dev/_user_request_/webhook/btg \
  -H "Content-Type: application/json" \
  -d '{
    "event": "report_ready",
    "account": "000123456",
    "download_url": "https://btg.com/reports/xyz.csv"
  }'
```

### **Teste 3: Armazenamento S3**

```python
# tests/integration/test_s3_storage.py
import pytest
from src.aws.s3 import S3Client

def test_save_to_s3():
    s3_client = S3Client()

    # Salvar arquivo
    s3_client.upload_file(
        file_path="data/test.parquet",
        bucket="agfi-data-lake-dev",
        key="raw/btg/test.parquet"
    )

    # Verificar se existe
    assert s3_client.file_exists("agfi-data-lake-dev", "raw/btg/test.parquet")
```

---

## 📁 Estrutura de Dados no S3

```
s3://agfi-data-lake-dev/
├── raw/
│   └── btg/
│       ├── account_base/
│       │   └── 2025-01-20/
│       │       └── accounts.parquet
│       ├── account_information/
│       │   └── 2025-01-20/
│       │       └── user_info.parquet
│       └── registration_data/
│           └── 2025-01-20/
│               └── registration.parquet
├── processed/
│   └── btg/
│       └── consolidated/
│           └── 2025-01-20/
│               └── consolidated.parquet
└── hubspot/
    └── uploads/
        └── 2025-01-20/
            └── contacts.parquet
```

---

## 🔄 Fluxo Completo de Teste

### **Cenário: Nova conta BTG → HubSpot**

1. **Trigger Manual:**
   ```bash
   python main.py --sync-account 000123456
   ```

2. **Execução:**
   - ✅ btg_sync.py faz request para API BTG
   - ✅ Valida JSON com AccountInformationRaw
   - ✅ Transforma dados (_flat_users_key + json_normalize)
   - ✅ Valida DataFrame com AccountInformationFlat
   - ✅ Salva parquet no S3 local
   - ✅ BTG envia webhook com link de relatório
   - ✅ webhook_receiver.py processa callback
   - ✅ Download do relatório e armazenamento

3. **Validação:**
   ```bash
   # Verificar arquivo no S3
   aws --endpoint-url=http://localhost:4566 \
       s3 ls s3://agfi-data-lake-dev/raw/btg/account_information/2025-01-20/

   # Verificar logs
   aws --endpoint-url=http://localhost:4566 \
       logs tail /aws/lambda/agfi-btg-sync-dev --follow
   ```

---

## 📊 Monitoramento Local

### **CloudWatch Logs (LocalStack)**

```bash
# Ver logs da Lambda btg_sync
aws --endpoint-url=http://localhost:4566 \
    logs tail /aws/lambda/agfi-btg-sync-dev --follow

# Ver logs do webhook_receiver
aws --endpoint-url=http://localhost:4566 \
    logs tail /aws/lambda/agfi-hubspot-webhook-dev --follow
```

### **S3 Browser**

```bash
# Listar todos os arquivos
aws --endpoint-url=http://localhost:4566 \
    s3 ls s3://agfi-data-lake-dev --recursive
```

---

## ⚠️ Diferenças: FastAPI vs API Gateway

### **Antes (FastAPI):**
```python
@app.post("/webhook/btg")
async def receive_btg_webhook(request: Request):
    data = await request.json()
    # processar...
```

### **Depois (API Gateway + Lambda):**
```python
def lambda_handler(event, context):
    # event contém o corpo do request
    body = json.loads(event.get('body', '{}'))
    # processar...
```

**Principais mudanças:**
1. ✅ Não há mais servidor rodando 24/7
2. ✅ Escalabilidade automática
3. ✅ Logs centralizados no CloudWatch
4. ✅ Integração nativa com SQS, S3, etc

---

## 🚀 Próximos Passos

1. ✅ Implementar `webhook_receiver.py`
2. ✅ Implementar `btg_sync.py`
3. ✅ Configurar S3 client para LocalStack
4. ✅ Criar testes de integração
5. ✅ Validar fluxo end-to-end
6. ⏳ Adicionar processamento de filas (SQS)
7. ⏳ Implementar data_transformer.py

---

## 📚 Referências

- [LocalStack Docs](https://docs.localstack.cloud/)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference.html)
- [BTG API Docs](docs/sources/btg/api/)
