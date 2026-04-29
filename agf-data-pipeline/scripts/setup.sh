#!/bin/bash

# scripts/setup.sh
# Setup inicial completo: verifica pré-requisitos, conectividade com LocalStack remoto,
# configura recursos AWS e faz build SAM.
# Uso: ./scripts/setup.sh
#
# LocalStack roda no homelab server — acessível via WARP em localhost.localstack.cloud:4566

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================
# CONFIGURAÇÃO DO ENDPOINT REMOTO
# ============================================
# localhost.localstack.cloud → IP WARP do homelab (via /etc/hosts ou CoreDNS)
# As Lambdas no servidor usam http://localstack:4566 (rede Docker interna)
LOCALSTACK_ENDPOINT="http://localhost.localstack.cloud:4566"

echo -e "${BLUE}🚀 SETUP INICIAL - AGF Data Pipeline${NC}"
echo "========================================"
echo -e "${BLUE}   LocalStack: ${LOCALSTACK_ENDPOINT}${NC}"
echo ""

# ============================================
# FASE 1: PRÉ-REQUISITOS
# ============================================

echo -e "${YELLOW}FASE 1: Verificando pré-requisitos...${NC}"
echo ""

ERRORS=0

# Docker (necessário para sam build --use-container)
echo -n "  Docker... "
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Não instalado${NC}"
    ERRORS=$((ERRORS + 1))
elif ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Não está rodando${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓${NC}"
fi

# AWS CLI
echo -n "  AWS CLI... "
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ Não instalado${NC}"
    echo "     Instale com: brew install awscli"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓${NC}"
fi

# Python
echo -n "  Python 3... "
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Não instalado${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓${NC}"
fi

# SAM CLI
echo -n "  SAM CLI... "
if ! command -v sam &> /dev/null; then
    echo -e "${YELLOW}⚠️  Não instalado (opcional)${NC}"
    echo "     Instale com: brew install aws-sam-cli"
else
    echo -e "${GREEN}✓${NC}"
fi

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ $ERRORS erro(s) encontrado(s). Corrija antes de continuar.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Todos os pré-requisitos OK!${NC}"

# ============================================
# FASE 2: VERIFICAR CONECTIVIDADE COM LOCALSTACK REMOTO
# ============================================

echo ""
echo -e "${YELLOW}FASE 2: Verificando conectividade com LocalStack remoto...${NC}"
echo "  Endpoint: ${LOCALSTACK_ENDPOINT}"
echo ""

max_attempts=10
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s "${LOCALSTACK_ENDPOINT}/_localstack/health" | grep -q "running"; then
        echo -e "${GREEN}✅ LocalStack acessível${NC}"
        break
    fi
    attempt=$((attempt + 1))
    echo -n "."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo ""
    echo -e "${RED}❌ LocalStack não acessível em ${LOCALSTACK_ENDPOINT}${NC}"
    echo "   Verifique:"
    echo "   - WARP está conectado ao homelab"
    echo "   - localhost.localstack.cloud resolve para o servidor (verifique /etc/hosts)"
    echo "   - LocalStack está rodando no servidor"
    exit 1
fi

# ============================================
# FASE 3: CONFIGURAR RECURSOS AWS
# ============================================

echo ""
echo -e "${YELLOW}FASE 3: Configurando recursos AWS...${NC}"

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-2

# Criar bucket S3
echo -n "  S3 Bucket... "
aws --endpoint-url="${LOCALSTACK_ENDPOINT}" s3 mb s3://agfi-data-lake-dev 2>/dev/null || true
echo -e "${GREEN}✓${NC}"

# Re-seed de fixtures locais → S3
# Com LocalStack Pro + PERSISTENCE=1, o S3 já restaura o estado do volume automaticamente.
# O re-seed só é feito quando o bucket está vazio (primeiro uso ou após limpeza do volume).
FIXTURES_DIR="$PROJECT_ROOT/fixtures"
S3_OBJECT_COUNT=$(aws --endpoint-url="${LOCALSTACK_ENDPOINT}" s3 ls s3://agfi-data-lake-dev --recursive 2>/dev/null | wc -l | tr -d ' ')
if [ "$S3_OBJECT_COUNT" -gt 0 ]; then
    echo "  S3 fixtures: $S3_OBJECT_COUNT objeto(s) restaurado(s) do volume — sem re-seed"
elif [ -d "$FIXTURES_DIR" ] && [ "$(ls -A "$FIXTURES_DIR" 2>/dev/null)" ]; then
    echo -n "  S3 fixtures (re-seed — bucket vazio)... "
    aws --endpoint-url="${LOCALSTACK_ENDPOINT}" s3 sync "$FIXTURES_DIR" s3://agfi-data-lake-dev --quiet
    echo -e "${GREEN}✓${NC}"
else
    echo "  S3 fixtures: bucket vazio e pasta fixtures/ não encontrada — sem re-seed"
    echo "  (coloque arquivos de teste em $FIXTURES_DIR para re-seed automático)"
fi

# Nota: a fila SQS (agfi-sync-queue-dev) é criada pelo samlocal deploy.
echo "  SQS Queue: será criada pelo samlocal deploy (com DLQ configurada)"

# ============================================
# FASE 4: SINCRONIZAR BIBLIOTECAS E BUILD
# ============================================

echo ""
echo -e "${YELLOW}FASE 4: Sincronizando bibliotecas e gerando imagens SAM...${NC}"

LAYER_DIR="layers/shared-libs"
LIBS_BASE="../python_libraries"
WORKSPACE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV_PYTHON="$WORKSPACE_ROOT/.venv/bin/python"

# Sincronização
echo "  Criando estrutura da Layer..."
rm -rf "$LAYER_DIR"
mkdir -p "$LAYER_DIR"

echo "  Copiando bibliotecas internas..."
for lib in btg hubspot aws database; do
    lib_path="$LIBS_BASE/$lib/src/$lib"
    if [ -d "$lib_path" ]; then
        echo "  ✓ Copiando $lib..."
        cp -r "$lib_path" "$LAYER_DIR/"
    else
        echo -e "  ${RED}✗ Library not found: $lib_path${NC}"
        exit 1
    fi
done

echo "  Copiando código fonte do projeto..."
if [ -d "src" ]; then
    echo "  ✓ Copiando src/ para layer..."
    cp -r src "$LAYER_DIR/"
else
    echo -e "  ${RED}✗ src/ directory not found${NC}"
    exit 1
fi

# Geração do requirements.txt
echo "  Gerando requirements.txt..."
"$VENV_PYTHON" -c "
import tomllib, pathlib, sys
workspace = pathlib.Path('$WORKSPACE_ROOT')
layer_dir = pathlib.Path('$LAYER_DIR')
deps = set()
for lib in ['btg', 'hubspot', 'aws', 'database']:
    toml_path = workspace / 'python_libraries' / lib / 'pyproject.toml'
    if not toml_path.exists():
        print(f'  ✗ Not found: {toml_path}')
        sys.exit(1)
    with open(toml_path, 'rb') as f:
        data = tomllib.load(f)
    lib_deps = data.get('project', {}).get('dependencies', [])
    deps.update(lib_deps)
    print(f'  ✓ {lib}: {len(lib_deps)} dependencies')
req_file = layer_dir / 'requirements.txt'
req_file.write_text(
    '# Auto-generated by setup.sh — do not edit manually\n'
    '# Source: python_libraries/*/pyproject.toml\n\n'
    + '\n'.join(sorted(deps))
    + '\n'
)
print(f'  ✓ Written: {req_file} ({len(deps)} packages)')
"

# Build 1: template.yaml → .aws-sam/build/ → usado pelo sam local start-api
echo "  [1/2] sam build (template.yaml → .aws-sam/build/)..."
sam build --use-container
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Falha no sam build (template.yaml)${NC}"
    exit 1
fi

# Build 2: template-local.yaml → .aws-sam/build-local/ → usado pelo samlocal deploy
echo "  [2/2] sam build --config-env local (template-local.yaml → .aws-sam/build-local/)..."
sam build --use-container --config-env local
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Falha no sam build (template-local.yaml)${NC}"
    exit 1
fi

# Limpar pacotes pesados do layer e das funções no build local.
BUILD_LOCAL=".aws-sam/build-local"
LAYER_PY="$BUILD_LOCAL/SharedLibrariesLayer/python"

rm -rf \
    "$LAYER_PY/pyarrow" \
    "$LAYER_PY/pyarrow-23.0.1.dist-info"
echo "  Layer local: $(du -sm "$LAYER_PY" 2>/dev/null | cut -f1)MB (limite: 250MB)"

for fn_dir in BTGWebhookFunction BTGRequestReportFunction BTGToHubSpotFunction SQSProcessorFunction DataTransformerFunction; do
    rm -rf \
        "$BUILD_LOCAL/$fn_dir/pyarrow" \
        "$BUILD_LOCAL/$fn_dir/pyarrow-23.0.1.dist-info"
done
echo "  Funções locais: $(du -sm "$BUILD_LOCAL/BTGWebhookFunction" 2>/dev/null | cut -f1)MB cada (limite: 250MB)"

echo -e "${GREEN}✅ Build concluído com sucesso!${NC}"

# ============================================
# FASE 5: RESUMO
# ============================================

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Setup completo!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"

echo ""
echo -e "${BLUE}📊 Serviços disponíveis:${NC}"
echo "  🏠 LocalStack:    ${LOCALSTACK_ENDPOINT}  (homelab via WARP)"
echo "  🗄️  RDS (MySQL):   via LocalStack — provisionado pelo sam deploy"
echo "  📦 S3 Bucket:      s3://agfi-data-lake-dev"
echo "  📬 SQS Queue:      agfi-sync-queue-dev"
echo "  🐳 SAM Images:    Build concluído"

echo ""

# ============================================
# FASE 6: DEPLOY PARA LOCALSTACK (opcional)
# ============================================
echo -e "${BLUE}🚀 Deploy para LocalStack${NC}"
echo "  Faz o deploy do stack SAM (RDS, Lambdas, S3 triggers, etc.)"
read -p "  Rodar samlocal deploy agora? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    if ! command -v samlocal &> /dev/null; then
        echo -e "${RED}  ❌ samlocal não instalado. Instale com: pip install aws-sam-cli-local${NC}"
    else
        echo ""

        # Criar bucket de artefatos SAM
        aws --endpoint-url="${LOCALSTACK_ENDPOINT}" s3 mb s3://agfi-sam-artifacts 2>/dev/null || true

        # Se o stack Lambda está em ROLLBACK_COMPLETE, deletar e re-criar.
        # NOTA: NÃO deletamos o stack agfi-infra-dev — os dados persistem.
        STACK_STATUS=$(aws --endpoint-url="${LOCALSTACK_ENDPOINT}" cloudformation describe-stacks \
            --stack-name agfi-lambda-dev \
            --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "NONE")
        if [[ "$STACK_STATUS" == "ROLLBACK_COMPLETE" ]]; then
            echo "  Stack Lambda em ROLLBACK_COMPLETE — deletando para re-criar..."
            aws --endpoint-url="${LOCALSTACK_ENDPOINT}" cloudformation delete-stack \
                --stack-name agfi-lambda-dev 2>/dev/null || true
            sleep 3
        fi

        # Carregar .env
        if [ -f "$PROJECT_ROOT/.env" ]; then
            set -o allexport; source "$PROJECT_ROOT/.env"; set +o allexport
        fi
        export AWS_ACCESS_KEY_ID=test
        export AWS_SECRET_ACCESS_KEY=test
        export AWS_DEFAULT_REGION=us-east-2
        export LOCALSTACK_HOSTNAME=localhost.localstack.cloud
        export EDGE_PORT=4566
        unset AWS_REGION

        # Carregar outputs do stack de infra
        INFRA_OUTPUTS="$(cd "$(dirname "$0")/.." && pwd)/infra/.outputs.env"
        if [ ! -f "$INFRA_OUTPUTS" ]; then
            echo -e "${RED}  ❌ infra/.outputs.env não encontrado. Execute primeiro: ./infra/deploy.sh${NC}"
            exit 1
        fi
        source "$INFRA_OUTPUTS"

        PARAMS="Environment=dev"
        PARAMS="$PARAMS LogLevel=DEBUG"
        PARAMS="$PARAMS MySQLDatabase=agfi"
        PARAMS="$PARAMS MySQLUser=agfi_user"
        PARAMS="$PARAMS MySQLPassword=agfi_password"
        PARAMS="$PARAMS AwsEndpointUrl=http://localstack:4566"
        PARAMS="$PARAMS DataLakeBucketName=${INFRA_DATA_LAKE_BUCKET}"
        PARAMS="$PARAMS SyncQueueUrl=${INFRA_SQS_QUEUE_URL}"
        PARAMS="$PARAMS SyncQueueArn=${INFRA_SQS_QUEUE_ARN}"
        PARAMS="$PARAMS SyncQueueName=${INFRA_SQS_QUEUE_NAME}"
        PARAMS="$PARAMS DatabaseEndpoint=${INFRA_DB_ENDPOINT}"
        PARAMS="$PARAMS DatabasePort=${INFRA_DB_PORT}"
        [ -n "${BTG_CLIENT_ID:-}" ]     && PARAMS="$PARAMS BTGClientId=$BTG_CLIENT_ID"
        [ -n "${BTG_CLIENT_SECRET:-}" ] && PARAMS="$PARAMS BTGClientSecret=$BTG_CLIENT_SECRET"
        [ -n "${BTG_API_BASE:-}" ]      && PARAMS="$PARAMS BTGBaseUrl=$BTG_API_BASE"
        [ -n "${HUBSPOT_API_KEY:-}" ]   && PARAMS="$PARAMS HubSpotApiKey=$HUBSPOT_API_KEY"

        samlocal deploy \
            --config-env local \
            --no-confirm-changeset \
            --parameter-overrides $PARAMS

        if [ $? -eq 0 ]; then
            echo ""
            echo -e "${GREEN}  ✅ Deploy concluído! RDS provisionado pelo LocalStack.${NC}"

            RDS_ENDPOINT=$(aws --endpoint-url="${LOCALSTACK_ENDPOINT}" cloudformation describe-stacks \
                --stack-name agfi-lambda-dev \
                --query "Stacks[0].Outputs[?OutputKey=='DatabaseEndpoint'].OutputValue" \
                --output text 2>/dev/null || echo "")
            RDS_PORT=$(aws --endpoint-url="${LOCALSTACK_ENDPOINT}" cloudformation describe-stacks \
                --stack-name agfi-lambda-dev \
                --query "Stacks[0].Outputs[?OutputKey=='DatabasePort'].OutputValue" \
                --output text 2>/dev/null || echo "3306")

            if [ -n "$RDS_ENDPOINT" ]; then
                echo -e "  🗄️  RDS endpoint: ${YELLOW}${RDS_ENDPOINT}:${RDS_PORT}${NC}"
                echo ""
                echo -e "  ${BLUE}ℹ️  MySQL acessível do Mac via localhost.localstack.cloud:${RDS_PORT}${NC}"
            fi
        else
            echo -e "${RED}  ❌ Falha no deploy${NC}"
        fi
    fi
else
    echo "  Pulando deploy — rode manualmente quando quiser:"
    echo -e "     ${YELLOW}samlocal deploy --config-env local --no-confirm-changeset${NC}"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Setup completo!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
