# AGF Data Pipeline - Monorepo

Pipeline de dados para integração BTG → S3 Data Lake → HubSpot CRM.

## 📁 Estrutura do Projeto

```
working/
├── python_libraries/          # Bibliotecas compartilhadas (workspace members)
│   ├── btg/                   # agf-btg-client
│   ├── hubspot/               # agf-hubspot-client
│   └── aws/                   # agf-aws-utils
├── agf-data-pipeline/         # Projeto principal
│   ├── src/
│   │   ├── core/              # Configuração, logging, exceções
│   │   ├── etl/               # Workflows de ETL
│   │   ├── database/          # Modelos e operações de banco
│   │   ├── models/            # Modelos de dados
│   │   └── lambda_handler/    # Handlers AWS Lambda
│   └── handlers/              # Lambda handlers específicos
├── exemples/                  # Exemplos de uso
├── pyproject.toml             # Configuração do workspace
├── .env                       # Variáveis de ambiente
└── README.md                  # Este arquivo
```

## 🎯 Funcionalidades Principais

O pipeline possui três funções principais:

### 1. **ETL Diário - Ingestão de Dados Brutos**
- Extrai dados da API BTG (contas, posições, open finance)
- Salva dados brutos no S3 com particionamento por data
- Executa uma vez por dia

### 2. **Processamento e Sincronização**
- Limpa e transforma dados brutos
- Salva dados curados no S3
- Sincroniza com banco de dados
- Atualiza HubSpot CRM
- Executa uma vez por dia após a ingestão 

### 3. **Monitoramento em Tempo Real**
- Monitora criação de novas contas via API BTG
- Loop de 60 segundos
- Notifica sistemas externos via webhook

## 📚 Bibliotecas

### `agf-btg-client` - Cliente BTG API

Cliente OAuth2 para integração com APIs do BTG Pactual.

**Características:**
- Autenticação OAuth2 com refresh automático de tokens
- Retry logic com exponential backoff
- Schemas Pydantic para validação de dados
- Tratamento de rate limits e erros transientes

**Uso:**
```python
from btg import BTGClient

client = BTGClient(
    client_id="your-client-id",
    client_secret="your-secret"
)

# Buscar informações de conta
account = client.get_account_information(account_id="123456")
```

### `agf-hubspot-client` - Cliente HubSpot CRM

Cliente genérico para HubSpot CRM API.

**Características:**
- Suporte a Custom Objects genéricos (aceita `object_type_id`)
- Operações em batch (create, update, archive)
- Busca e listagem com paginação automática
- Gerenciamento de contatos e associações

**Uso:**
```python
from hubspot import HubSpotCustomObject

client = HubSpotCustomObject(api_key="your-api-key")

# Trabalhar com BTG Accounts (Custom Object)
BTG_ACCOUNTS_OBJECT_ID = "2-51787688"

client.create_batch(
    objects=[{"properties": {"account_number": "123", ...}}],
    object_type_id=BTG_ACCOUNTS_OBJECT_ID
)

# Buscar registros
results = client.search(
    query={"filterGroups": [...]},
    object_type_id=BTG_ACCOUNTS_OBJECT_ID
)

# Listar todos
all_accounts = client.get_all(
    object_type_id=BTG_ACCOUNTS_OBJECT_ID,
    properties=["account_number", "balance"],
    limit=100
)
```

### `agf-aws-utils` - Utilitários AWS

Utilitários para operações com AWS S3, SQS e Lambda.

**Características:**
- Cliente S3 para Data Lake com estrutura particionada
- Upload/download de DataFrames como CSV
- Identificação automática da última partição
- Suporte a credenciais explícitas ou default chain

**Uso:**
```python
from aws import S3Client
import pandas as pd

client = S3Client(
    bucket_name="agfi-data-lake-dev",
    region="us-east-2"
)

# Ler última partição
df = client.read_last_partition_csv(
    source="rm-reports-account-base",
    event_date="20250128",
    domain="btg"
)

# Upload de DataFrame
client.upload_dataframe_as_csv(
    df=processed_df,
    s3_key="curated/domain=btg/.../data.csv"
)
```

## 🚀 Setup e Instalação

### Pré-requisitos

- Python 3.13+
- uv (gerenciador de pacotes)

### Instalação

```bash
# Clonar repositório
cd /path/to/working

# Instalar dependências com uv workspace
uv sync

# Ativar ambiente virtual
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows
```

### Configuração

Criar arquivo `.env` na raiz do projeto:

```bash
# BTG API
BTG_CLIENT_ID=your-client-id
BTG_CLIENT_SECRET=your-client-secret
BTG_BASE_URL=https://api.btg.com

# HubSpot
HUBSPOT_API_KEY=your-api-key

# AWS
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-2
S3_BUCKET_NAME=agfi-data-lake-dev

# Database (se aplicável)
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

## 🧪 Desenvolvimento

### Executar testes

```bash
# Testes de uma biblioteca específica
cd python_libraries/btg
pytest

# Testes do projeto principal
cd agf-data-pipeline
pytest
```

### Adicionar nova dependência

```bash
# Para biblioteca específica
cd python_libraries/btg
uv add httpx

# Para projeto principal
cd agf-data-pipeline
uv add pandas
```

### Estrutura de particionamento S3

```
s3://bucket-name/
├── raw/                           # Dados brutos da API
│   └── domain=btg/
│       └── source=rm-reports-account-base/
│           └── event_date=20250128/
│               └── data--eventts=20250128T120000Z--hash=abc123.csv
└── curated/                       # Dados processados
    └── domain=btg/
        └── source=processed-accounts/
            └── event_date=20250128/
                └── accounts--eventts=20250128T130000Z.csv
```

## 📖 Exemplos

Veja `exemples/library_usage_example.py` para exemplos completos de:
- Uso individual de cada biblioteca
- Pipeline completo BTG → S3 → HubSpot
- Operações em batch
- Tratamento de erros

## 🏗️ Arquitetura

### Monorepo Workspace

Este projeto usa `uv workspace` para gerenciar múltiplos pacotes:

**Vantagens:**
- Bibliotecas instaladas em modo de desenvolvimento (editable)
- Dependências compartilhadas
- Versionamento independente
- Reutilização entre projetos

### Hierarquia de Exceções

Todas as bibliotecas seguem o mesmo padrão de exceções:

```python
class BaseError(Exception):
    def __init__(self, message, details=None, original_error=None):
        self.message = message
        self.details = details or {}
        self.original_error = original_error

    def to_dict(self):
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "original_error": str(self.original_error)
        }
```

## 📝 TODO

- [ ] Implementar Function 1: Daily ETL raw data ingestion
- [ ] Implementar Function 2: Data transformation & sync
- [ ] Implementar Function 3: Real-time account monitoring
- [ ] Adicionar testes unitários para todas as bibliotecas
- [ ] Configurar CI/CD pipeline
- [ ] Adicionar documentação API completa

## 📄 Licença

Proprietário - AGF

## 👥 Contribuidores

- Time AGF Data Engineering
