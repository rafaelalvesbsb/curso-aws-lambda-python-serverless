#!/bin/bash

# scripts/test_flow.sh
# Testa o fluxo completo: infraestrutura → webhook → BTGRequestReport → SQS → S3
#
# Pré-requisito:
#   ./infra/deploy.sh    (stack agfi-infra-dev)
#   ./scripts/homelab.sh (stack agfi-lambda-dev)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

ENDPOINT="http://localhost.localstack.cloud:4566"
WEBHOOK_DOMAIN="testefastapi.alphaspark.com.br"

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-2
export AWS_PAGER=""

echo -e "${BLUE}🧪 TESTE DE FLUXO COMPLETO${NC}"
echo "============================"
echo ""

ERRORS=0

# ============================================================================
# 1. LocalStack acessível
# ============================================================================
echo -e "${YELLOW}1️⃣  Verificando LocalStack...${NC}"
if curl -s "${ENDPOINT}/_localstack/health" | grep -q "running"; then
    echo -e "   ${GREEN}✅ LocalStack acessível${NC}"
else
    echo -e "   ${RED}❌ LocalStack não acessível em ${ENDPOINT}${NC}"
    echo "   Verifique: WARP conectado + LocalStack rodando no servidor"
    exit 1
fi

# ============================================================================
# 2. Stacks deployados
# ============================================================================
echo ""
echo -e "${YELLOW}2️⃣  Verificando stacks CloudFormation...${NC}"

for stack in agfi-infra-dev agfi-lambda-dev; do
    STATUS=$(aws --endpoint-url=$ENDPOINT cloudformation describe-stacks \
        --stack-name "$stack" \
        --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "NONE")
    if [[ "$STATUS" == "CREATE_COMPLETE" || "$STATUS" == "UPDATE_COMPLETE" ]]; then
        echo -e "   ${GREEN}✅ $stack ($STATUS)${NC}"
    else
        echo -e "   ${RED}❌ $stack não está deployado (status: $STATUS)${NC}"
        echo "   Execute: ./infra/deploy.sh && ./scripts/homelab.sh"
        ERRORS=$((ERRORS + 1))
    fi
done

[[ $ERRORS -gt 0 ]] && exit 1

# ============================================================================
# 3. Recursos de infra
# ============================================================================
echo ""
echo -e "${YELLOW}3️⃣  Verificando recursos de infra...${NC}"

# S3
if aws --endpoint-url=$ENDPOINT s3 ls 2>&1 | grep -q "agfi-data-lake-dev"; then
    echo -e "   ${GREEN}✅ S3 agfi-data-lake-dev${NC}"
else
    echo -e "   ${RED}❌ S3 bucket não encontrado${NC}"; ERRORS=$((ERRORS + 1))
fi

# SQS
if aws --endpoint-url=$ENDPOINT sqs list-queues 2>&1 | grep -q "agfi-sync-queue-dev"; then
    echo -e "   ${GREEN}✅ SQS agfi-sync-queue-dev${NC}"
else
    echo -e "   ${RED}❌ SQS fila não encontrada${NC}"; ERRORS=$((ERRORS + 1))
fi

# DynamoDB
TABLE_STATUS=$(aws --endpoint-url=$ENDPOINT dynamodb describe-table \
    --table-name agfi-sync-state-dev \
    --query "Table.TableStatus" --output text 2>/dev/null || echo "NOT_FOUND")
if [[ "$TABLE_STATUS" == "ACTIVE" ]]; then
    echo -e "   ${GREEN}✅ DynamoDB agfi-sync-state-dev${NC}"
else
    echo -e "   ${RED}❌ DynamoDB não encontrado (status: $TABLE_STATUS)${NC}"; ERRORS=$((ERRORS + 1))
fi

[[ $ERRORS -gt 0 ]] && { echo -e "\n${RED}❌ Recursos de infra incompletos. Rode ./infra/deploy.sh${NC}"; exit 1; }

# ============================================================================
# 4. Lambdas deployadas
# ============================================================================
echo ""
echo -e "${YELLOW}4️⃣  Verificando Lambdas...${NC}"

for fn in agfi-btg-webhook-dev agfi-btg-request-report-dev agfi-sqs-processor-dev agfi-btg-dlq-reconcile-dev; do
    STATE=$(aws --endpoint-url=$ENDPOINT lambda get-function \
        --function-name "$fn" \
        --query "Configuration.State" --output text 2>/dev/null || echo "NOT_FOUND")
    if [[ "$STATE" == "Active" ]]; then
        echo -e "   ${GREEN}✅ $fn${NC}"
    else
        echo -e "   ${RED}❌ $fn (status: $STATE)${NC}"; ERRORS=$((ERRORS + 1))
    fi
done

[[ $ERRORS -gt 0 ]] && { echo -e "\n${RED}❌ Lambdas incompletas. Rode ./scripts/homelab.sh${NC}"; exit 1; }

# ============================================================================
# 5. Roteamento do webhook (API GW v2 + custom domain)
# ============================================================================
echo ""
echo -e "${YELLOW}5️⃣  Testando roteamento webhook (${WEBHOOK_DOMAIN})...${NC}"

# Deve retornar 404 do API Gateway (não "NoSuchBucket" do S3)
WEBHOOK_RESPONSE=$(curl -s -o /tmp/webhook_test.json -w "%{http_code}" \
    -X POST "https://${WEBHOOK_DOMAIN}/webhook/test-route" \
    -H "Content-Type: application/json" \
    -d '{"test": true}' 2>/dev/null || echo "000")

WEBHOOK_BODY=$(cat /tmp/webhook_test.json 2>/dev/null || echo "")

if [[ "$WEBHOOK_RESPONSE" == "200" || "$WEBHOOK_RESPONSE" == "404" || "$WEBHOOK_RESPONSE" == "403" ]]; then
    # Qualquer resposta do API GW é OK (não é erro do S3)
    if echo "$WEBHOOK_BODY" | grep -qi "NoSuchBucket\|BucketNotFound"; then
        echo -e "   ${RED}❌ Roteando para S3 em vez de API Gateway (NoSuchBucket)${NC}"
        echo "      Verifique: WebhookApiMapping no stack agfi-lambda-dev"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "   ${GREEN}✅ Webhook roteado para API Gateway (HTTP $WEBHOOK_RESPONSE)${NC}"
    fi
elif [[ "$WEBHOOK_RESPONSE" == "000" ]]; then
    echo -e "   ${YELLOW}⚠️  Webhook não acessível (sem conexão com ${WEBHOOK_DOMAIN})${NC}"
    echo "      Verifique: Cloudflare tunnel + WARP conectado"
else
    # Verificar se a resposta tem smell de S3
    if echo "$WEBHOOK_BODY" | grep -qi "NoSuchBucket\|BucketNotFound\|<Error>"; then
        echo -e "   ${RED}❌ Roteando para S3 em vez de API Gateway (HTTP $WEBHOOK_RESPONSE)${NC}"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "   ${GREEN}✅ Webhook alcançável (HTTP $WEBHOOK_RESPONSE)${NC}"
    fi
fi
rm -f /tmp/webhook_test.json

# ============================================================================
# 6. Contar arquivos no S3 antes
# ============================================================================
echo ""
echo -e "${YELLOW}6️⃣  Estado do S3 antes do teste...${NC}"
FILE_COUNT_BEFORE=$(aws --endpoint-url=$ENDPOINT s3 ls s3://agfi-data-lake-dev/raw/btg/ \
    --recursive 2>/dev/null | wc -l | tr -d ' ')
echo "   📊 Arquivos em raw/btg/: ${FILE_COUNT_BEFORE}"

# ============================================================================
# 7. Pré-aquecer Lambda de webhook (evitar cold start no BTG callback)
# ============================================================================
echo ""
echo -e "${YELLOW}7️⃣  Pré-aquecendo Lambdas (evitar cold start)...${NC}"
echo "   ⏳ Disparando invocações assíncronas para aquecer os containers..."

# --invocation-type Event = async, retorna imediatamente (202) sem aguardar execução
# Isso dispara a inicialização do container sem travar o script
aws --endpoint-url=$ENDPOINT lambda invoke \
    --function-name agfi-btg-webhook-dev \
    --invocation-type Event \
    --payload '{"rawPath":"/webhook/warmup","requestContext":{"http":{"method":"POST"}},"body":"{}"}' \
    /dev/null > /dev/null 2>&1 || true

aws --endpoint-url=$ENDPOINT lambda invoke \
    --function-name agfi-sqs-processor-dev \
    --invocation-type Event \
    --payload '{"Records":[]}' \
    /dev/null > /dev/null 2>&1 || true

echo "   ⏳ Aguardando 15s para containers inicializarem..."
sleep 15
echo -e "   ${GREEN}✅ Containers aquecidos${NC}"

# ============================================================================
# 8. Invocar BTGRequestReportFunction
# ============================================================================
echo ""
echo -e "${YELLOW}8️⃣  Invocando BTGRequestReportFunction...${NC}"
echo "   ⏳ Solicitando relatórios ao BTG API..."

aws --endpoint-url=$ENDPOINT lambda invoke \
    --function-name agfi-btg-request-report-dev \
    --payload '{}' \
    --log-type Tail \
    /tmp/btg_request_result.json 2>/dev/null | python3 -c "
import sys, json, base64, re
resp = json.load(sys.stdin)
status = resp.get('StatusCode', 0)
err = resp.get('FunctionError', '')
log = base64.b64decode(resp.get('LogResult', '')).decode('utf-8', errors='replace')
print(f'   Status: {status}' + (f' ⚠️  {err}' if err else ' ✅'))
for line in log.split('\n'):
    if any(x in line for x in ['Requesting', 'Response', 'ERROR', 'error', 'Exception', 'report']):
        print('  ', re.sub(r'\x1b\[[0-9;]*m', '', line).strip())
" 2>/dev/null || echo "   (sem logs disponíveis)"

# Verificar resultado
RESULT_STATUS=$(python3 -c "
import json
d = json.load(open('/tmp/btg_request_result.json'))
print(d.get('statusCode', d.get('StatusCode', '?')))
" 2>/dev/null || echo "?")
rm -f /tmp/btg_request_result.json

# ============================================================================
# 9. Aguardar webhooks do BTG
# ============================================================================
echo ""
echo -e "${YELLOW}9️⃣  Aguardando callbacks do BTG (webhooks)...${NC}"
echo "   ⏳ Aguardando 120s para BTG enviar os relatórios..."
for i in $(seq 1 24); do
    sleep 5
    echo -n "   .${i}."
done
echo ""

# ============================================================================
# 🔟. Verificar SQS
# ============================================================================
echo ""
echo -e "${YELLOW}🔟  Verificando SQS após webhooks...${NC}"
QUEUE_URL="http://sqs.us-east-2.localhost.localstack.cloud:4566/000000000000/agfi-sync-queue-dev"
MSG_INFO=$(aws --endpoint-url=$ENDPOINT sqs get-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
    --output json 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
a = d.get('Attributes', {})
print(f\"visible={a.get('ApproximateNumberOfMessages','0')} processando={a.get('ApproximateNumberOfMessagesNotVisible','0')}\")
" 2>/dev/null || echo "não disponível")
echo "   📬 Fila: $MSG_INFO"

# ============================================================================
# 1️⃣1️⃣. Aguardar SQSProcessor e verificar S3
# ============================================================================
echo ""
echo -e "${YELLOW}1️⃣1️⃣  Aguardando SQSProcessorFunction (120s para arquivos grandes)...${NC}"
sleep 120

echo ""
echo -e "${YELLOW}1️⃣2️⃣  Verificando arquivos no S3...${NC}"
FILE_COUNT_AFTER=$(aws --endpoint-url=$ENDPOINT s3 ls s3://agfi-data-lake-dev/raw/btg/ \
    --recursive 2>/dev/null | wc -l | tr -d ' ')
echo "   📊 Arquivos em raw/btg/: ${FILE_COUNT_AFTER}"

NEW_FILES=$((FILE_COUNT_AFTER - FILE_COUNT_BEFORE))
if [[ "$FILE_COUNT_AFTER" -gt "$FILE_COUNT_BEFORE" ]]; then
    echo -e "   ${GREEN}✅ $NEW_FILES novo(s) arquivo(s) salvo(s)!${NC}"
    echo ""
    echo -e "   ${BLUE}📄 Últimos arquivos:${NC}"
    aws --endpoint-url=$ENDPOINT s3 ls s3://agfi-data-lake-dev/raw/btg/ \
        --human-readable --recursive 2>/dev/null | sort | tail -n 15 | sed 's/^/      /'
else
    echo -e "   ${YELLOW}⚠️  Nenhum arquivo novo salvo${NC}"
    echo ""
    echo -e "   ${BLUE}💡 Diagnóstico:${NC}"
    echo "      Logs webhook:   awslocal logs tail /aws/lambda/agfi-btg-webhook-dev --follow"
    echo "      Logs request:   awslocal logs tail /aws/lambda/agfi-btg-request-report-dev --follow"
    echo "      Logs processor: awslocal logs tail /aws/lambda/agfi-sqs-processor-dev --follow"
fi

# ============================================================================
# Resumo
# ============================================================================
echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✅ TESTE CONCLUÍDO${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}🔍 Comandos úteis para debug:${NC}"
echo "  Logs Lambda: awslocal logs tail /aws/lambda/<nome> --follow"
echo "  SQS fila:    awslocal sqs get-queue-attributes --queue-url <url> --attribute-names All"
echo "  S3 arquivos: awslocal s3 ls s3://agfi-data-lake-dev/raw/btg/ --recursive"
echo "  DLQ fila:    awslocal sqs get-queue-attributes --queue-url <url-dlq> --attribute-names All"
echo ""
