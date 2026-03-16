#!/bin/bash
# ===========================================
# Install NVIDIA Container Toolkit
# ===========================================
# Enables Docker containers to access NVIDIA GPUs
# ===========================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Installing NVIDIA Container Toolkit${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${BLUE}Step 1: Adding NVIDIA Container Toolkit repository...${NC}"
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

echo -e "${GREEN}✓ Repository added${NC}"

echo ""
echo -e "${BLUE}Step 2: Updating package list...${NC}"
sudo apt-get update
echo -e "${GREEN}✓ Package list updated${NC}"

echo ""
echo -e "${BLUE}Step 3: Installing nvidia-container-toolkit...${NC}"
sudo apt-get install -y nvidia-container-toolkit
echo -e "${GREEN}✓ NVIDIA Container Toolkit installed${NC}"

echo ""
echo -e "${BLUE}Step 4: Configuring Docker to use NVIDIA runtime...${NC}"
sudo nvidia-ctk runtime configure --runtime=docker
echo -e "${GREEN}✓ Docker configured${NC}"

echo ""
echo -e "${BLUE}Step 5: Restarting Docker service...${NC}"
sudo systemctl restart docker
echo -e "${GREEN}✓ Docker restarted${NC}"

echo ""
echo -e "${BLUE}Step 6: Verifying GPU access in Docker...${NC}"
if sudo docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi 2>/dev/null | grep -q "RTX"; then
    echo -e "${GREEN}✓ GPU is accessible in Docker!${NC}"
    echo ""
    sudo docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
else
    echo -e "${RED}✗ GPU verification failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "NVIDIA Container Toolkit is now installed!"
echo ""
echo "Next step: Run ./scripts/enable-gpu-production.sh to enable GPU in production"
echo ""
