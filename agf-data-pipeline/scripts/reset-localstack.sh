#!/bin/bash

# scripts/reset-localstack.sh
# Limpa todos os stacks e recursos deployados no LocalStack.
# Use quando quiser começar do zero sem reiniciar o container LocalStack.
#
# Uso:
#   ./scripts/reset-localstack.sh          → delete stacks + RDS
#   ./scripts/reset-localstack.sh --hard   → também deleta S3 e SQS (dados perdidos!)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

LOCALSTACK_ENDPOINT="http://localhost.localstack.cloud:4566"
HARD_MODE="${1:-}"

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-2
export AWS_PAGER=""   # desabilita pager (less) nas respostas do AWS CLI

echo -e "${RED}🧹 AGFI LocalStack — Reset${NC}"
echo "================================="
echo ""

# ── Verificar conectividade ────────────────────────────────────────
if ! curl -s "${LOCALSTACK_ENDPOINT}/_localstack/health" | grep -q "running"; then
    echo -e "${RED}❌ LocalStack não acessível${NC}"
    exit 1
fi

# ============================================================================
# 1. Deletar stack Lambda (agfi-lambda-dev)
# ============================================================================
echo -e "${YELLOW}1. Deletando stack Lambda (agfi-lambda-dev)...${NC}"
LAMBDA_STATUS=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation describe-stacks \
    --stack-name agfi-lambda-dev \
    --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "$LAMBDA_STATUS" != "NOT_FOUND" ]]; then
    aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation delete-stack \
        --stack-name agfi-lambda-dev 2>/dev/null || true
    echo -n "   Aguardando deleção"
    for i in $(seq 1 20); do
        sleep 3
        STATUS=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation describe-stacks \
            --stack-name agfi-lambda-dev \
            --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "NOT_FOUND")
        [[ "$STATUS" == "NOT_FOUND" || "$STATUS" == "DELETE_COMPLETE" ]] && break
        echo -n "."
    done
    echo -e " ${GREEN}✓${NC}"
else
    echo -e "   ${BLUE}(não existe)${NC}"
fi

# ============================================================================
# 2. Deletar instância RDS (ignora DeletionPolicy do CFN — força deleção)
# ============================================================================
echo -e "${YELLOW}2. Deletando instância RDS (agfi-db-dev)...${NC}"
DB_STATUS=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" rds describe-db-instances \
    --db-instance-identifier agfi-db-dev \
    --query "DBInstances[0].DBInstanceStatus" --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "$DB_STATUS" != "NOT_FOUND" ]]; then
    aws --endpoint-url="$LOCALSTACK_ENDPOINT" rds delete-db-instance \
        --db-instance-identifier agfi-db-dev \
        --skip-final-snapshot 2>/dev/null || true
    echo -n "   Aguardando deleção"
    for i in $(seq 1 15); do
        sleep 3
        STATUS=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" rds describe-db-instances \
            --db-instance-identifier agfi-db-dev \
            --query "DBInstances[0].DBInstanceStatus" --output text 2>/dev/null || echo "NOT_FOUND")
        [[ "$STATUS" == "NOT_FOUND" ]] && break
        echo -n "."
    done
    echo -e " ${GREEN}✓${NC}"
else
    echo -e "   ${BLUE}(não existe)${NC}"
fi

# ============================================================================
# 3. Deletar stack Infra (agfi-infra-dev)
#    DeletionPolicy: Retain → S3 e SQS sobrevivem (a menos que --hard)
# ============================================================================
echo -e "${YELLOW}3. Deletando stack Infra (agfi-infra-dev)...${NC}"
INFRA_STATUS=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation describe-stacks \
    --stack-name agfi-infra-dev \
    --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "$INFRA_STATUS" != "NOT_FOUND" ]]; then
    aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation delete-stack \
        --stack-name agfi-infra-dev 2>/dev/null || true
    echo -n "   Aguardando deleção"
    for i in $(seq 1 20); do
        sleep 3
        STATUS=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" cloudformation describe-stacks \
            --stack-name agfi-infra-dev \
            --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "NOT_FOUND")
        [[ "$STATUS" == "NOT_FOUND" || "$STATUS" == "DELETE_COMPLETE" ]] && break
        echo -n "."
    done
    echo -e " ${GREEN}✓${NC}"
else
    echo -e "   ${BLUE}(não existe)${NC}"
fi

# ============================================================================
# 4. --hard: deletar S3 e SQS também (dados perdidos!)
# ============================================================================
if [[ "$HARD_MODE" == "--hard" ]]; then
    echo ""
    echo -e "${RED}⚠️  --hard: deletando S3 e SQS...${NC}"

    echo -n "   Esvaziando e deletando s3://agfi-data-lake-dev... "
    aws --endpoint-url="$LOCALSTACK_ENDPOINT" s3 rb s3://agfi-data-lake-dev --force 2>/dev/null || true
    echo -e "${GREEN}✓${NC}"

    echo -n "   Deletando SQS agfi-sync-queue-dev... "
    QUEUE_URL=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" sqs get-queue-url \
        --queue-name agfi-sync-queue-dev --output text 2>/dev/null || echo "")
    [[ -n "$QUEUE_URL" ]] && aws --endpoint-url="$LOCALSTACK_ENDPOINT" sqs delete-queue \
        --queue-url "$QUEUE_URL" 2>/dev/null || true
    echo -e "${GREEN}✓${NC}"

    echo -n "   Deletando SQS agfi-sync-queue-dlq-dev... "
    DLQ_URL=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" sqs get-queue-url \
        --queue-name agfi-sync-queue-dlq-dev --output text 2>/dev/null || echo "")
    [[ -n "$DLQ_URL" ]] && aws --endpoint-url="$LOCALSTACK_ENDPOINT" sqs delete-queue \
        --queue-url "$DLQ_URL" 2>/dev/null || true
    echo -e "${GREEN}✓${NC}"

    echo -n "   Deletando bucket de artefatos SAM... "
    aws --endpoint-url="$LOCALSTACK_ENDPOINT" s3 rb s3://agfi-sam-artifacts --force 2>/dev/null || true
    echo -e "${GREEN}✓${NC}"
fi

# ============================================================================
# 5. Limpar outputs.env local
# ============================================================================
OUTPUTS_FILE="$(dirname "$0")/../infra/.outputs.env"
if [ -f "$OUTPUTS_FILE" ]; then
    echo -e "${YELLOW}4. Removendo infra/.outputs.env...${NC}"
    rm "$OUTPUTS_FILE"
    echo -e "   ${GREEN}✓${NC}"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Reset concluído!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
if [[ "$HARD_MODE" == "--hard" ]]; then
    echo -e "${YELLOW}⚠️  Dados do S3 e SQS foram apagados.${NC}"
else
    echo -e "${BLUE}ℹ️  S3 e SQS preservados (DeletionPolicy: Retain).${NC}"
    echo -e "   Use ${YELLOW}--hard${NC} para apagar dados também."
fi
echo ""
echo -e "${BLUE}Próximo passo — re-deploiar do zero:${NC}"
echo "   ./infra/deploy.sh"
echo "   ./scripts/homelab.sh"
echo ""
