#!/bin/bash

# scripts/cleanup.sh
# Stop all services and clean up development environment

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Always resolve paths relative to project root (not scripts/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Carregar variáveis do .env para resolver os caminhos reais dos volumes
# (docker-compose faz o mesmo — sem isso MYSQL_VOLUME, LOCALSTACK_VOLUME e REDIS_VOLUME
#  ficam indefinidos e o fallback ./mysql-data etc. pode não ser o caminho correto)
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -o allexport
    source "$PROJECT_ROOT/.env"
    set +o allexport
fi

# Resolver os caminhos dos volumes usando os mesmos defaults do docker-compose.yaml
# Caminhos relativos no .env são interpretados a partir do PROJECT_ROOT
_resolve_volume_path() {
    local raw="$1"
    local default="$2"
    local path="${raw:-$default}"
    # Se começa com ./ ou ../ → relativo ao PROJECT_ROOT
    if [[ "$path" == ./* ]] || [[ "$path" == ../* ]]; then
        echo "$(cd "$PROJECT_ROOT" && cd "$(dirname "$path")" && pwd)/$(basename "$path")"
    else
        echo "$path"
    fi
}

LOCALSTACK_VOLUME_PATH="$(_resolve_volume_path "${LOCALSTACK_VOLUME:-}" "./localstack-data")"
REDIS_VOLUME_PATH="$(_resolve_volume_path "${REDIS_VOLUME:-}" "./redis-data")"

echo -e "${BLUE}🧹 Cleaning Up Development Environment${NC}"
echo "===================================="
echo ""

# ============================================================================
# PHASE 1: Stop SAM Local
# ============================================================================
echo -e "${YELLOW}Phase 1: Stopping SAM Local API Gateway${NC}"
echo "-------------------------------------------"

# Find and kill SAM processes
SAM_PIDS=$(pgrep -f "sam local start-api" || true)
if [ ! -z "$SAM_PIDS" ]; then
    echo "Stopping SAM Local processes..."
    kill $SAM_PIDS 2>/dev/null || true
    sleep 2
    echo -e "${GREEN}✅ SAM Local stopped${NC}"
else
    echo "No SAM Local processes found"
fi

# Find and kill SQS Poller
POLLER_PIDS=$(pgrep -f "sqs_poller.py" || true)
if [ ! -z "$POLLER_PIDS" ]; then
    echo "Stopping SQS Poller..."
    kill $POLLER_PIDS 2>/dev/null || true
    echo -e "${GREEN}✅ SQS Poller stopped${NC}"
else
    echo "No SQS Poller process found"
fi

# Kill any process on port 3000
if lsof -ti:3000 >/dev/null 2>&1; then
    echo "Freeing port 3000..."
    kill -9 $(lsof -ti:3000) 2>/dev/null || true
    sleep 1
    echo -e "${GREEN}✅ Port 3000 freed${NC}"
fi

echo ""

# ============================================================================
# PHASE 2: Limpar imagens SAM locais
# ============================================================================
# Nota: Lambda e RDS containers rodam no homelab server (gerenciados pelo LocalStack remoto).
# Aqui limpamos apenas imagens SAM geradas localmente pelo sam build --use-container.
echo -e "${YELLOW}Phase 2: Limpando imagens SAM locais${NC}"
echo "-------------------------------------------"

# SAM Lambda images (criadas pelo sam build --use-container)
echo "Removing SAM Lambda images..."
SAM_IMAGES=$(docker images --format "{{.ID}}\t{{.Repository}}" | awk '/samcli\/lambda-python/{print $1}')
if [ -n "$SAM_IMAGES" ]; then
    docker rmi -f $SAM_IMAGES 2>/dev/null || true
    echo -e "${GREEN}✅ SAM Lambda images removed${NC}"
else
    echo "No SAM Lambda images found"
fi

# Remove dangling images (<none>:<none>) — geradas a cada sam build --use-container
echo "Removing dangling images (<none>)..."
DANGLING=$(docker images -f "dangling=true" -q)
if [ -n "$DANGLING" ]; then
    COUNT=$(echo "$DANGLING" | wc -l | tr -d ' ')
    echo "Found $COUNT dangling image(s), removing..."
    docker image prune -f 2>/dev/null || true
    echo -e "${GREEN}✅ Dangling images removed${NC}"
else
    echo "No dangling images found"
fi

echo ""

# ============================================================================
# PHASE 3: Informativo — serviços no homelab
# ============================================================================
echo -e "${YELLOW}Phase 3: Serviços remotos (homelab)${NC}"
echo "-------------------------------------------"
echo -e "  ${BLUE}ℹ️  LocalStack, RDS e Redis rodam no homelab server.${NC}"
echo "  Para gerenciar: https://portainer.internal"
echo "  Para limpar o estado do LocalStack no servidor:"
echo "    - Acesse Portainer → reinicie o container agfi-localstack"
echo "    - Ou via WARP: awslocal --endpoint-url=http://localhost.localstack.cloud:4566 s3 rb s3://agfi-data-lake-dev --force"

echo ""

# ============================================================================
# PHASE 4: Clean SAM Build Artifacts (Optional)
# ============================================================================
echo -e "${YELLOW}Phase 4: Clean Build Artifacts${NC}"
echo "-------------------------------------------"

read -p "Remove SAM build artifacts? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "$PROJECT_ROOT/.aws-sam" ]; then
        echo "Removing .aws-sam directory..."
        rm -rf "$PROJECT_ROOT/.aws-sam"
        echo -e "${GREEN}✅ Build artifacts removed${NC}"
    else
        echo "No build artifacts found"
    fi

    if [ -f "$PROJECT_ROOT/sam-local.log" ]; then
        echo "Removing SAM log file..."
        rm -f "$PROJECT_ROOT/sam-local.log"
        echo -e "${GREEN}✅ SAM log removed${NC}"
    fi

    if [ -f "$PROJECT_ROOT/sqs-poller.log" ]; then
        echo "Removing SQS Poller log file..."
        rm -f "$PROJECT_ROOT/sqs-poller.log"
        echo -e "${GREEN}✅ Poller log removed${NC}"
    fi
else
    echo "Keeping build artifacts"
fi

echo ""

# ============================================================================
# PHASE 5: Clean Layer Directory (Optional)
# ============================================================================
echo -e "${YELLOW}Phase 5: Clean Layer Directory${NC}"
echo "-------------------------------------------"

read -p "Remove synced libraries from layer? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "$PROJECT_ROOT/layers/shared-libs" ]; then
        echo "Removing layer directory..."
        rm -rf "$PROJECT_ROOT/layers/shared-libs"
        echo -e "${GREEN}✅ Layer directory cleaned${NC}"
    else
        echo "No layer directory found"
    fi
else
    echo "Keeping layer directory"
fi

echo ""

# ============================================================================
# PHASE 6: Summary
# ============================================================================
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Cleanup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${BLUE}📊 Current Status:${NC}"
echo "-------------------"

# Check running containers
RUNNING_CONTAINERS=$(docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -v "NAMES" || true)
if [ ! -z "$RUNNING_CONTAINERS" ]; then
    echo -e "${YELLOW}Running containers:${NC}"
    echo "$RUNNING_CONTAINERS"
else
    echo "No containers running"
fi

echo ""
echo -e "${BLUE}🔄 To restart development:${NC}"
echo "   ./scripts/setup.sh    - Reconfigure environment"
echo "   ./scripts/dev.sh      - Start development"
echo ""
