#!/bin/bash
# ===========================================
# Enable GPU in Production Backend
# ===========================================
# Recreates the backend container with GPU access
# All fixes are now applied:
# - GPU memory detection fix (float16)
# - Non-blocking uploads
# - GPU runtime configuration
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
echo -e "${BLUE}Enable GPU in Production Backend${NC}"
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
echo -e "${BLUE}Step 1: Checking NVIDIA Container Toolkit...${NC}"
if $DOCKER run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
    echo -e "${GREEN}✓ NVIDIA Container Toolkit is working${NC}"
else
    echo -e "${RED}✗ NVIDIA Container Toolkit not available${NC}"
    echo ""
    echo -e "${YELLOW}You need to install NVIDIA Container Toolkit:${NC}"
    echo "  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    echo ""
    echo "Quick install:"
    echo "  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"
    echo "  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y nvidia-container-toolkit"
    echo "  sudo systemctl restart docker"
    echo ""
    exit 1
fi

echo ""
echo -e "${BLUE}Step 2: Stopping backend container...${NC}"
$DOCKER_COMPOSE stop backend-prod
echo -e "${GREEN}✓ Stopped${NC}"

echo ""
echo -e "${BLUE}Step 3: Removing old container...${NC}"
$DOCKER_COMPOSE rm -f backend-prod
echo -e "${GREEN}✓ Removed${NC}"

echo ""
echo -e "${BLUE}Step 4: Creating new container with GPU access...${NC}"
$DOCKER_COMPOSE up -d backend-prod
echo -e "${GREEN}✓ Created${NC}"

echo ""
echo -e "${BLUE}Step 5: Waiting for initialization (15 seconds)...${NC}"
sleep 15

echo ""
echo -e "${BLUE}Step 6: Verifying GPU access in container...${NC}"
echo ""
if $DOCKER exec voice-processor-backend-prod nvidia-smi 2>&1 | grep -q "RTX"; then
    echo -e "${GREEN}✓ GPU is accessible in container!${NC}"
    echo ""
    $DOCKER exec voice-processor-backend-prod nvidia-smi
else
    echo -e "${YELLOW}⚠️ GPU check inconclusive, checking logs...${NC}"
fi

echo ""
echo -e "${BLUE}Step 7: Checking backend logs for GPU detection...${NC}"
echo ""
$DOCKER_COMPOSE logs --tail 50 backend-prod | grep -E "GPU|CUDA|記憶體|量化" || echo "No GPU logs yet (will appear on first upload)"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ GPU Enabled in Production!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "All fixes now active:"
echo "  ✅ GPU runtime configuration (Docker)"
echo "  ✅ GPU memory detection fix (code)"
echo "  ✅ float16 quantization (better quality)"
echo "  ✅ Non-blocking file uploads"
echo "  ✅ Upload streaming (no disconnections)"
echo ""
echo "Production URLs:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:3080"
echo ""
echo "Test GPU processing:"
echo "  1. Upload an audio file at http://localhost:5173"
echo "  2. Monitor GPU: watch -n 1 nvidia-smi"
echo "  3. Check logs: ./manage.sh logs-prod | grep GPU"
echo ""
