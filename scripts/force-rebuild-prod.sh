#!/bin/bash
# ===========================================
# Force Clean Rebuild of Production
# ===========================================
# Rebuilds production WITHOUT cache to ensure
# all code changes are included:
# - GPU memory fix
# - Upload blocking fix
# ===========================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Force Clean Rebuild (No Cache)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Docker permissions
if docker ps >/dev/null 2>&1; then
    DOCKER="docker"
    DOCKER_COMPOSE="docker compose"
    echo -e "${GREEN}✓ Docker permissions OK${NC}"
else
    echo -e "${YELLOW}Using sudo for Docker commands${NC}"
    DOCKER="sudo docker"
    DOCKER_COMPOSE="sudo docker compose"
fi

echo ""
echo -e "${BLUE}Step 1: Stopping production...${NC}"
$DOCKER_COMPOSE stop backend-prod frontend-prod 2>/dev/null || echo -e "${YELLOW}No containers running${NC}"
echo -e "${GREEN}✓ Stopped${NC}"

echo ""
echo -e "${BLUE}Step 2: Removing old containers...${NC}"
$DOCKER_COMPOSE rm -f backend-prod frontend-prod 2>/dev/null || true
echo -e "${GREEN}✓ Removed${NC}"

echo ""
echo -e "${BLUE}Step 3: Clean rebuild WITHOUT cache (this ensures all fixes are included)...${NC}"
echo -e "${YELLOW}This will take several minutes...${NC}"
$DOCKER_COMPOSE build --no-cache backend-prod
echo -e "${GREEN}✓ Backend rebuilt from scratch${NC}"

echo ""
echo -e "${BLUE}Step 4: Starting production...${NC}"
$DOCKER_COMPOSE up -d backend-prod frontend-prod
echo -e "${GREEN}✓ Production started${NC}"

echo ""
echo -e "${BLUE}Step 5: Waiting for initialization (15 seconds)...${NC}"
sleep 15

echo ""
echo -e "${BLUE}Step 6: Checking logs...${NC}"
$DOCKER_COMPOSE logs --tail 50 backend-prod | tail -20

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Clean Rebuild Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Fixes now deployed in production:"
echo "  ✓ GPU memory detection fix (float16 instead of int8)"
echo "  ✓ Non-blocking file upload (validation moved to background)"
echo "  ✓ Docker networking optimizations (60min timeout, no buffering)"
echo "  ✓ Vite proxy streaming (prevents client disconnection)"
echo ""
echo "Production URLs:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:3080"
echo ""
echo "Test the fixes:"
echo "  1. Upload a file - should not get stuck"
echo "  2. Monitor GPU: watch -n 1 nvidia-smi"
echo "  3. Check logs: ./manage.sh logs-prod"
echo ""
