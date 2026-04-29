#!/bin/bash

# scripts/homelab.sh
# Deploy completo do stack SAM no LocalStack (modo homelab).
#
# DIFERENÇA vs dev.sh:
#   dev.sh      → sam local start-api  (Lambdas rodam no host, estado volátil)
#   homelab.sh  → samlocal deploy       (Lambdas rodam dentro do LocalStack, estado persistido)
#
# PRÉ-REQUISITOS:
#   pip install aws-sam-cli-local   (instala o comando `samlocal`)
#   LocalStack Pro rodando          (./scripts/setup.sh)
#
# USO:
#   Primeiro deploy:  ./scripts/homelab.sh
#   Após mudança de código: ./scripts/homelab.sh --redeploy

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Endpoint remoto do LocalStack (Mac → homelab via WARP)
LOCALSTACK_ENDPOINT="http://localhost.localstack.cloud:4566"

# Carregar variáveis do .env
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -o allexport
    source "$PROJECT_ROOT/.env"
    set +o allexport
fi

echo -e "${BLUE}🏠 AGFI Homelab — Deploy para LocalStack${NC}"
echo "========================================="
echo ""

# ============================================================================
# FASE 1: Verificar pré-requisitos
# ============================================================================
echo -e "${YELLOW}FASE 1: Verificando pré-requisitos...${NC}"

ERRORS=0

echo -n "  samlocal... "
if ! command -v samlocal &> /dev/null; then
    echo -e "${RED}❌ Não instalado${NC}"
    echo "     Instale com: pip install aws-sam-cli-local"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓${NC}"
fi

echo -n "  LocalStack acessível (${LOCALSTACK_ENDPOINT})... "
if curl -s "${LOCALSTACK_ENDPOINT}/_localstack/health" | grep -q "running"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}❌ Não acessível${NC}"
    echo "     Verifique: WARP conectado + LocalStack rodando no servidor"
    echo "     Portainer: https://portainer.internal"
    ERRORS=$((ERRORS + 1))
fi

echo -n "  LocalStack Pro (licença)... "
IS_LICENSED=$(curl -s "${LOCALSTACK_ENDPOINT}/_localstack/info" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('is_license_activated', False))" 2>/dev/null || echo "false")
if [ "$IS_LICENSED" != "True" ]; then
    echo -e "${YELLOW}⚠️  Licença não ativada — persistência limitada${NC}"
    echo "     Configure LOCALSTACK_AUTH_TOKEN no servidor"
else
    echo -e "${GREEN}✓ (Pro ativado)${NC}"
fi

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ $ERRORS erro(s) encontrado(s). Corrija antes de continuar.${NC}"
    exit 1
fi

echo ""

# ============================================================================
# FASE 2: Verificar stack de infra (agfi-infra-dev)
# ============================================================================
echo -e "${YELLOW}FASE 2: Verificando stack de infra (agfi-infra-dev)...${NC}"

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-2
# samlocal usa LOCALSTACK_HOSTNAME + EDGE_PORT para encontrar o LocalStack remoto
export LOCALSTACK_HOSTNAME=localhost.localstack.cloud
export EDGE_PORT=4566

INFRA_OUTPUTS="$PROJECT_ROOT/infra/.outputs.env"
INFRA_STATUS=$(aws --endpoint-url="${LOCALSTACK_ENDPOINT}" cloudformation describe-stacks \
    --stack-name agfi-infra-dev \
    --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "NONE")

if [[ "$INFRA_STATUS" != "CREATE_COMPLETE" && "$INFRA_STATUS" != "UPDATE_COMPLETE" ]]; then
    echo -e "${RED}❌ Stack agfi-infra-dev não encontrado (status: ${INFRA_STATUS}).${NC}"
    echo "   Execute primeiro: ./infra/deploy.sh"
    exit 1
fi

# Carregar outputs da infra
if [ ! -f "$INFRA_OUTPUTS" ]; then
    echo -e "${YELLOW}  ⚠️  infra/.outputs.env não encontrado — gerando...${NC}"
    bash "$PROJECT_ROOT/infra/deploy.sh" --status > /dev/null 2>&1 || true
    # Gerar manualmente se o script --status não criou o arquivo
    "$PROJECT_ROOT/infra/deploy.sh" 2>/dev/null || true
fi

if [ -f "$INFRA_OUTPUTS" ]; then
    source "$INFRA_OUTPUTS"
    echo -e "${GREEN}  ✅ Infra OK — ${INFRA_DATA_LAKE_BUCKET} | ${INFRA_SQS_QUEUE_NAME} | ${INFRA_SYNC_STATE_TABLE}${NC}"
else
    echo -e "${RED}❌ Não foi possível carregar infra/.outputs.env${NC}"
    exit 1
fi
echo ""

# ============================================================================
# FASE 3: Preparar S3 para artefatos SAM
# ============================================================================
echo -e "${YELLOW}FASE 3: Preparando bucket de artefatos SAM...${NC}"

echo -n "  s3://agfi-sam-artifacts... "
aws --endpoint-url="${LOCALSTACK_ENDPOINT}" s3 mb s3://agfi-sam-artifacts 2>/dev/null || true
echo -e "${GREEN}✓${NC}"
echo ""

# ============================================================================
# FASE 4: Build
# ============================================================================
echo -e "${YELLOW}FASE 4: Build do stack SAM...${NC}"
echo ""

cd "$PROJECT_ROOT"

# Sincronizar bibliotecas na layer antes do build
LAYER_DIR="layers/shared-libs"
LIBS_BASE="../python_libraries"
WORKSPACE_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

echo "  Sincronizando bibliotecas na layer..."
# Atualiza apenas os subdirs de código customizado — NÃO deleta requirements.txt
# que define os pacotes pesados (pandas, pyarrow, numpy) instalados na layer.
mkdir -p "$LAYER_DIR"
for lib in btg aws; do
    lib_path="$LIBS_BASE/$lib/src/$lib"
    if [ -d "$lib_path" ]; then
        rm -rf "$LAYER_DIR/$lib"
        cp -r "$lib_path" "$LAYER_DIR/"
    else
        echo -e "  ${RED}✗ Library não encontrada: $lib_path${NC}"
        exit 1
    fi
done
rm -rf "$LAYER_DIR/src"
cp -r src "$LAYER_DIR/"
echo -e "  ${GREEN}✓ Layer sincronizada${NC}"

echo ""
echo "  Executando sam build..."
sam build --config-env local --cached
echo ""

# Remover pacotes instalados dos diretórios de função após o build.
# Todas as dependências (httpx, pydantic, boto3, pandas, pyarrow, etc.)
# já estão na SharedLibrariesLayer — duplicá-las nas funções faz o pacote
# exceder o limite de 250MB descompactado do Lambda.
# Mantemos apenas os arquivos .py dos handlers.
BUILD_LOCAL=".aws-sam/build-local"
LAYER_PY="$BUILD_LOCAL/SharedLibrariesLayer/python"

if [ -d "$LAYER_PY" ]; then
    # pyarrow (~200MB) excede o limite mesmo na layer — removido até termos
    # um build containerizado (--use-container) que gera wheels Linux corretos.
    # numpy + pandas (~60MB total) ficam na layer normalmente.
    echo "  Limpando pyarrow da layer (excede 250MB descompactado)..."
    rm -rf "$LAYER_PY"/pyarrow "$LAYER_PY"/pyarrow-*.dist-info
    echo "  Layer: $(du -sm "$LAYER_PY" 2>/dev/null | cut -f1)MB (numpy+pandas+código customizado)"
fi

for fn_dir in BTGWebhookFunction BTGRequestReportFunction SQSProcessorFunction BTGDLQReconcileFunction; do
    fn_path="$BUILD_LOCAL/$fn_dir"
    if [ -d "$fn_path" ]; then
        # pandas, numpy, pyarrow agora estão na layer — remover das funções
        # para evitar duplicação e reduzir tamanho do pacote.
        rm -rf \
            "$fn_path"/pyarrow         "$fn_path"/pyarrow-*.dist-info \
            "$fn_path"/numpy           "$fn_path"/numpy-*.dist-info "$fn_path"/numpy.libs \
            "$fn_path"/pandas          "$fn_path"/pandas-*.dist-info
        echo "  $fn_dir: $(du -sm "$fn_path" 2>/dev/null | cut -f1)MB"
    fi
done
echo ""

# ============================================================================
# FASE 5: Deploy Lambda stack (agfi-lambda-dev)
# ============================================================================
echo -e "${YELLOW}FASE 5: Deploy Lambda stack (agfi-lambda-dev)...${NC}"
echo ""

# Parâmetros: credenciais BTG + outputs do stack de infra
PARAMETER_OVERRIDES=(
    "Environment=dev"
    "LogLevel=DEBUG"
    "BTGClientId=${BTG_CLIENT_ID:-}"
    "BTGClientSecret=${BTG_CLIENT_SECRET:-}"
    "BTGBaseUrl=${BTG_API_BASE:-https://api.btgpactual.com}"
    # Endpoint LocalStack interno (usado pelas Lambdas dentro do Docker do servidor)
    "AwsEndpointUrl=http://localstack:4566"
    # ScheduleExpression não sobrescrito aqui — usa o default do template:
    # cron(0 11 ? * MON-FRI *)  →  seg–sex às 08:00 BRT (11:00 UTC)
    # No LocalStack o EventBridge é mock (não dispara). Scheduling via n8n.
    # Outputs do stack agfi-infra-dev
    "DataLakeBucketName=${INFRA_DATA_LAKE_BUCKET}"
    "SyncQueueUrl=${INFRA_SQS_QUEUE_URL}"
    "SyncQueueArn=${INFRA_SQS_QUEUE_ARN}"
    "SyncQueueName=${INFRA_SQS_QUEUE_NAME}"
    "SyncQueueDLQArn=${INFRA_SQS_QUEUE_DLQ_ARN}"
    "SyncStateTableName=${INFRA_SYNC_STATE_TABLE}"
    "WebhookDomainName=${INFRA_WEBHOOK_DOMAIN}"
)

samlocal deploy \
    --config-env local \
    --no-confirm-changeset \
    --parameter-overrides "${PARAMETER_OVERRIDES[@]}"

echo ""

# ============================================================================
# FASE 5: Resumo
# ============================================================================
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Deploy concluído!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""

# Buscar outputs do stack
echo -e "${BLUE}📍 Stack outputs:${NC}"
aws --endpoint-url="${LOCALSTACK_ENDPOINT}" cloudformation describe-stacks \
    --stack-name agfi-lambda-dev \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table 2>/dev/null || echo "  (sem outputs definidos no template)"

echo ""
echo -e "${BLUE}📡 Endpoints disponíveis:${NC}"
echo "  LocalStack:      ${LOCALSTACK_ENDPOINT}  (homelab via WARP)"
echo "  API Gateway:     ${LOCALSTACK_ENDPOINT}/restapis  (via LocalStack)"
echo "  Portainer:       https://portainer.internal"
echo ""
echo -e "${BLUE}🔁 Para re-deployar após mudança de código:${NC}"
echo "   ./scripts/homelab.sh"
echo ""
echo -e "${BLUE}🧪 Para invocar uma Lambda diretamente:${NC}"
echo "   awslocal lambda invoke --function-name BTGWebhookFunction /tmp/out.json"
echo ""
echo -e "${BLUE}📋 Para ver logs de uma Lambda:${NC}"
echo "   awslocal logs tail /aws/lambda/BTGWebhookFunction --follow"
echo ""
