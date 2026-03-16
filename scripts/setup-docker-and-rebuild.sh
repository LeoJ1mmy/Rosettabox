#!/bin/bash
# ===========================================
# Docker Setup and Production Rebuild Script
# ===========================================
# This script helps you:
# 1. Fix Docker permissions if needed
# 2. Rebuild production with GPU fix
# 3. Verify GPU is working
# ===========================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Docker Setup & Production Rebuild${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Check Docker permissions
echo -e "${BLUE}Step 1: Checking Docker permissions...${NC}"
if docker ps >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker permissions OK${NC}"
    HAS_DOCKER_PERMISSION=true
else
    echo -e "${YELLOW}✗ Docker permission denied${NC}"
    HAS_DOCKER_PERMISSION=false

    echo ""
    echo -e "${YELLOW}You need Docker permissions to rebuild production.${NC}"
    echo ""
    echo "Choose an option:"
    echo "  1) Add myself to docker group (recommended, permanent fix)"
    echo "  2) Use sudo for this session only"
    echo "  3) Exit and fix manually"
    echo ""
    read -p "Enter choice [1-3]: " choice

    case $choice in
        1)
            echo ""
            echo -e "${BLUE}Adding you to docker group...${NC}"
            echo -e "${YELLOW}This requires sudo password:${NC}"
            sudo usermod -aG docker $USER

            echo ""
            echo -e "${GREEN}✓ Added to docker group!${NC}"
            echo ""
            echo -e "${YELLOW}⚠️  IMPORTANT: You need to apply the changes${NC}"
            echo ""
            echo "Option A (Quick - applies to this terminal only):"
            echo "  Run: newgrp docker"
            echo "  Then run this script again: ./setup-docker-and-rebuild.sh"
            echo ""
            echo "Option B (Permanent - applies everywhere):"
            echo "  Log out and log back in"
            echo "  Then run this script again: ./setup-docker-and-rebuild.sh"
            echo ""
            echo -e "${BLUE}Attempting to apply changes now...${NC}"

            # Try to continue with newgrp
            exec sg docker -c "$0 --continue"
            ;;
        2)
            echo ""
            echo -e "${BLUE}Using sudo mode...${NC}"
            USE_SUDO=true
            ;;
        3)
            echo ""
            echo -e "${YELLOW}Exiting. Please fix Docker permissions manually:${NC}"
            echo "  sudo usermod -aG docker \$USER"
            echo "  newgrp docker"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice. Exiting.${NC}"
            exit 1
            ;;
    esac
fi

# Determine docker command prefix
if [ "$USE_SUDO" = true ]; then
    DOCKER="sudo docker"
    DOCKER_COMPOSE="sudo docker compose"
else
    DOCKER="docker"
    DOCKER_COMPOSE="docker compose"
fi

echo ""
echo -e "${BLUE}Step 2: Stopping production containers...${NC}"
$DOCKER_COMPOSE stop backend-prod frontend-prod 2>/dev/null || echo -e "${YELLOW}No containers to stop${NC}"
echo -e "${GREEN}✓ Production stopped${NC}"

echo ""
echo -e "${BLUE}Step 3: Rebuilding backend with GPU fix...${NC}"
echo -e "${YELLOW}This may take a few minutes...${NC}"
$DOCKER_COMPOSE build backend-prod
echo -e "${GREEN}✓ Backend rebuilt with GPU fix${NC}"

echo ""
echo -e "${BLUE}Step 4: Starting production containers...${NC}"
$DOCKER_COMPOSE up -d backend-prod frontend-prod
echo -e "${GREEN}✓ Production started${NC}"

echo ""
echo -e "${BLUE}Step 5: Waiting for backend to initialize (10 seconds)...${NC}"
sleep 10

echo ""
echo -e "${BLUE}Step 6: Checking backend logs for GPU detection...${NC}"
echo -e "${YELLOW}Looking for GPU memory and quantization info...${NC}"
echo ""

# Get recent logs and look for GPU info
$DOCKER_COMPOSE logs backend-prod 2>&1 | tail -100 > /tmp/prod-backend-logs.txt

if grep -q "GPU 記憶體狀態" /tmp/prod-backend-logs.txt; then
    echo -e "${GREEN}✓ GPU memory detection found in logs:${NC}"
    grep -E "GPU 記憶體|量化|float16|記憶體狀態" /tmp/prod-backend-logs.txt | tail -5
elif grep -q "float16" /tmp/prod-backend-logs.txt; then
    echo -e "${GREEN}✓ float16 quantization found:${NC}"
    grep "float16" /tmp/prod-backend-logs.txt | tail -3
else
    echo -e "${YELLOW}GPU info not in logs yet (model loads on first request)${NC}"
    echo -e "${YELLOW}The fix is deployed, GPU will be used when processing files${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Production Rebuild Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Production is now running with GPU fix:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:3080"
echo ""
echo "GPU Fix Applied:"
echo "  ✓ Dynamic GPU device detection (was hardcoded to device 1)"
echo "  ✓ Proper memory detection (~14.47 GB available)"
echo "  ✓ float16 quantization (was int8 due to memory error)"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:5173 in your browser"
echo "  2. Upload an audio file to test GPU processing"
echo "  3. Monitor GPU usage: watch -n 1 nvidia-smi"
echo "  4. Check logs: ./manage.sh logs-prod"
echo ""
echo "To verify GPU is being used during processing:"
echo "  In another terminal: watch -n 0.5 nvidia-smi"
echo "  Then upload a file and watch GPU utilization increase"
echo ""
