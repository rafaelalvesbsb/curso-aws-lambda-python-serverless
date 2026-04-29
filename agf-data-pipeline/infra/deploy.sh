#!/bin/bash

# infra/deploy.sh
# Deploy IDEMPOTENTE da infraestrutura persistente (S3, SQS, DynamoDB, API GW Domain).
#
# Todos os recursos são gerenciados via CloudFormation (DeletionPolicy: Retain).
#
# Roda UMA VEZ (ou quando infra mudar). Não precisa rodar a cada mudança de código Lambda.
#
# Uso:
#   ./infra/deploy.sh           → cria ou atualiza infra
#   ./infra/deploy.sh --status  → mostra outputs atuais sem fazer deploy
#
# Outputs salvos em: infra/.outputs.env  (sourceável por outros scripts)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

INFRA_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$INFRA_DIR/.." && pwd)"
OUTPUTS_FILE="$INFRA_DIR/.outputs.env"
STACK_NAME="agfi-infra-dev"
LOCALSTACK_ENDPOINT="http://localhost.localstack.cloud:4566"

# ── Credenciais LocalStack ─────────────────────────────────────────
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-2

# ── Carregar .env ──────────────────────────────────────────────────
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -o allexport; source "$PROJECT_ROOT/.env"; set +o allexport
fi

# ── Helper: ler output do stack CloudFormation ────────────────────
_get_cfn_output() {
    local key="$1"
    aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query "Stacks[0].Outputs[?OutputKey=='${key}'].OutputValue" \
        --output text 2>/dev/null || echo ""
}

# ── Helper: salvar outputs em arquivo ─────────────────────────────
_save_outputs() {
    echo "# Auto-gerado por infra/deploy.sh — não editar manualmente" > "$OUTPUTS_FILE"
    echo "# $(date)" >> "$OUTPUTS_FILE"
    echo "" >> "$OUTPUTS_FILE"

    local bucket queue_url queue_arn queue_name queue_dlq_arn sync_state_table webhook_domain
    bucket=$(_get_cfn_output "DataLakeBucketName")
    queue_url=$(_get_cfn_output "SyncQueueUrl")
    queue_arn=$(_get_cfn_output "SyncQueueArn")
    queue_name=$(_get_cfn_output "SyncQueueName")
    queue_dlq_arn=$(_get_cfn_output "SyncQueueDLQArn")
    sync_state_table=$(_get_cfn_output "SyncStateTableName")
    webhook_domain=$(_get_cfn_output "WebhookDomainName")

    cat >> "$OUTPUTS_FILE" <<EOF
INFRA_DATA_LAKE_BUCKET=${bucket}
INFRA_SQS_QUEUE_URL=${queue_url}
INFRA_SQS_QUEUE_ARN=${queue_arn}
INFRA_SQS_QUEUE_NAME=${queue_name}
INFRA_SQS_QUEUE_DLQ_ARN=${queue_dlq_arn}
INFRA_SYNC_STATE_TABLE=${sync_state_table}
INFRA_WEBHOOK_DOMAIN=${webhook_domain}
EOF

    echo -e "${GREEN}  ✅ Outputs salvos em infra/.outputs.env${NC}"
}

# ============================================================================
# MODE: --status → só mostra outputs
# ============================================================================
if [[ "${1:-}" == "--status" ]]; then
    echo -e "${BLUE}📊 Status da Infraestrutura${NC}"
    echo ""

    STATUS=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "NOT_DEPLOYED")

    echo "  CloudFormation Stack (${STACK_NAME}): ${STATUS}"
    echo ""

    if [[ "$STATUS" != "NOT_DEPLOYED" && "$STATUS" != "None" ]]; then
        echo -e "${BLUE}  Outputs:${NC}"
        aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
            --output table 2>/dev/null || true
    fi

    echo ""
    if [ -f "$OUTPUTS_FILE" ]; then
        echo ""
        echo -e "${BLUE}  Outputs salvos (.outputs.env):${NC}"
        grep -v "^#" "$OUTPUTS_FILE" | grep -v "^$" | sed 's/^/    /'
    fi
    exit 0
fi

# ============================================================================
# FASE 1: Conectividade
# ============================================================================
echo -e "${BLUE}🏗️  AGFI Infra — Deploy Idempotente${NC}"
echo "======================================"
echo ""
echo -e "${YELLOW}FASE 1: Verificando conectividade com LocalStack...${NC}"

if ! curl -s "${LOCALSTACK_ENDPOINT}/_localstack/health" | grep -q "running"; then
    echo -e "${RED}❌ LocalStack não acessível em ${LOCALSTACK_ENDPOINT}${NC}"
    echo "   Verifique: WARP conectado + LocalStack rodando no servidor"
    exit 1
fi
echo -e "${GREEN}✅ LocalStack acessível${NC}"
echo ""

# ============================================================================
# FASE 2: Verificar estado atual do stack
# ============================================================================
echo -e "${YELLOW}FASE 2: Verificando estado do stack...${NC}"

STACK_STATUS=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "NONE")

echo "  Status atual: ${STACK_STATUS}"

if [[ "$STACK_STATUS" == "CREATE_COMPLETE" || "$STACK_STATUS" == "UPDATE_COMPLETE" ]]; then
    echo -e "${GREEN}  ✅ Infra já existe — verificando se há mudanças...${NC}"
elif [[ "$STACK_STATUS" == "ROLLBACK_COMPLETE" || "$STACK_STATUS" == "CREATE_FAILED" ]]; then
    echo -e "${YELLOW}  ⚠️  Stack em ${STACK_STATUS} — limpando recursos orphans e re-criando...${NC}"
    aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation delete-stack \
        --stack-name "$STACK_NAME" 2>/dev/null || true
    sleep 3

    # Limpar recursos com DeletionPolicy: Retain que bloqueiam a re-criação
    echo "  Limpando recursos Retain orphans..."

    # DynamoDB
    TABLE_S=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" dynamodb describe-table \
        --table-name agfi-sync-state-dev --query "Table.TableStatus" \
        --output text 2>/dev/null || echo "NOT_FOUND")
    if [[ "$TABLE_S" != "NOT_FOUND" ]]; then
        aws --endpoint-url="$LOCALSTACK_ENDPOINT" dynamodb delete-table \
            --table-name agfi-sync-state-dev > /dev/null 2>&1 || true
        echo "    DynamoDB agfi-sync-state-dev → deletado"
    fi

    # SQS
    for q in agfi-sync-queue-dev agfi-sync-queue-dlq-dev; do
        Q_URL=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" sqs get-queue-url \
            --queue-name "$q" --output text 2>/dev/null || echo "")
        if [[ -n "$Q_URL" && "$Q_URL" != "None" ]]; then
            aws --endpoint-url="$LOCALSTACK_ENDPOINT" sqs delete-queue \
                --queue-url "$Q_URL" 2>/dev/null || true
            echo "    SQS $q → deletado"
        fi
    done

    # S3 (esvazia antes de deletar)
    if aws --endpoint-url="$LOCALSTACK_ENDPOINT" s3api head-bucket \
            --bucket agfi-data-lake-dev > /dev/null 2>&1; then
        aws --endpoint-url="$LOCALSTACK_ENDPOINT" s3 rb s3://agfi-data-lake-dev \
            --force > /dev/null 2>&1 || true
        echo "    S3 agfi-data-lake-dev → deletado"
    fi

    echo "  Stack e recursos orphans removidos."
elif [[ "$STACK_STATUS" == "NONE" ]]; then
    echo "  Stack não existe — será criado."
fi
echo ""

# ============================================================================
# FASE 3: Deploy CloudFormation (todos os recursos persistentes)
# ============================================================================
echo -e "${YELLOW}FASE 3: Deploying infra via CloudFormation...${NC}"
echo "  Stack:    ${STACK_NAME}"
echo "  Template: infra/template.yaml"
echo "  Recursos: S3, SQS, DynamoDB, API GW Domain"
echo ""

# --no-fail-on-empty-changeset → retorna 0 mesmo se não houver mudanças (idempotente)
aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation deploy \
    --stack-name "$STACK_NAME" \
    --template-file "$INFRA_DIR/template.yaml" \
    --no-fail-on-empty-changeset \
    --parameter-overrides \
        "Environment=dev" \
        "WebhookDomainName=${WEBHOOK_DOMAIN:-testefastapi.alphaspark.com.br}"

FINAL_STATUS=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "UNKNOWN")

if [[ "$FINAL_STATUS" != "CREATE_COMPLETE" && "$FINAL_STATUS" != "UPDATE_COMPLETE" ]]; then
    echo -e "${RED}❌ Deploy falhou. Status: ${FINAL_STATUS}${NC}"
    exit 1
fi

echo -e "${GREEN}  ✅ Infra pronta (stack: ${FINAL_STATUS})${NC}"
echo ""

# ============================================================================
# FASE 4: Salvar outputs
# ============================================================================
echo -e "${YELLOW}FASE 4: Salvando outputs...${NC}"
_save_outputs
echo ""

# ============================================================================
# RESUMO
# ============================================================================
source "$OUTPUTS_FILE" 2>/dev/null || true

echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Infra pronta!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}📦 Recursos:${NC}"
echo "  S3 Bucket:      ${INFRA_DATA_LAKE_BUCKET}"
echo "  SQS Queue:      ${INFRA_SQS_QUEUE_NAME}"
echo "  DynamoDB:       ${INFRA_SYNC_STATE_TABLE}"
echo "  Webhook Domain: ${INFRA_WEBHOOK_DOMAIN}"
echo ""
echo -e "${BLUE}ℹ️  Próximo passo — deploy das Lambdas:${NC}"
echo "   ./scripts/homelab.sh"
echo ""
echo -e "${YELLOW}⚠️  DeletionPolicy: Retain — recursos sobrevivem mesmo se o stack for deletado.${NC}"
echo ""
