#!/bin/bash
# ===========================================
# Setup Dual GPU Environments
# ===========================================
# Enables GPU in both:
# - Production (Docker on ports 5173/3080)
# - Development (Native on ports 5175/3082)
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
echo -e "${BLUE}Dual GPU Environment Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ============================================
# Step 1: Check NVIDIA Container Toolkit
# ============================================
echo -e "${BLUE}Step 1: Checking NVIDIA Container Toolkit...${NC}"

if docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
    echo -e "${GREEN}✓ NVIDIA Container Toolkit already installed${NC}"
    TOOLKIT_INSTALLED=true
else
    echo -e "${YELLOW}✗ NVIDIA Container Toolkit not installed${NC}"
    TOOLKIT_INSTALLED=false

    echo ""
    echo "NVIDIA Container Toolkit is required for GPU access in Docker."
    echo ""
    read -p "Install it now? (y/n): " install_choice

    if [ "$install_choice" = "y" ] || [ "$install_choice" = "Y" ]; then
        echo ""
        echo -e "${BLUE}Installing NVIDIA Container Toolkit...${NC}"

        # Add repository
        echo -e "${BLUE}  - Adding repository...${NC}"
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
        curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
          sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
          sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

        # Install
        echo -e "${BLUE}  - Updating packages...${NC}"
        sudo apt-get update

        echo -e "${BLUE}  - Installing nvidia-container-toolkit...${NC}"
        sudo apt-get install -y nvidia-container-toolkit

        # Configure Docker
        echo -e "${BLUE}  - Configuring Docker...${NC}"
        sudo nvidia-ctk runtime configure --runtime=docker

        # Restart Docker
        echo -e "${BLUE}  - Restarting Docker...${NC}"
        sudo systemctl restart docker

        echo -e "${GREEN}✓ NVIDIA Container Toolkit installed${NC}"
        TOOLKIT_INSTALLED=true
    else
        echo -e "${YELLOW}Skipping toolkit installation. Production will run without GPU.${NC}"
    fi
fi

# ============================================
# Step 2: Start Development (Native)
# ============================================
echo ""
echo -e "${BLUE}Step 2: Checking Development Environment (Native)...${NC}"

if [ -f ".dev-backend.pid" ] && kill -0 $(cat .dev-backend.pid) 2>/dev/null; then
    echo -e "${GREEN}✓ Development backend already running (PID: $(cat .dev-backend.pid))${NC}"
else
    echo -e "${BLUE}Starting development backend...${NC}"
    ../manage.sh start-dev
    sleep 3
    echo -e "${GREEN}✓ Development backend started${NC}"
fi

echo -e "${GREEN}Development (Native):${NC}"
echo "  Backend:  http://localhost:3082 (GPU: ✓ Native access)"
echo "  Frontend: http://localhost:5175"

# ============================================
# Step 3: Start Production (Docker with GPU)
# ============================================
echo ""
echo -e "${BLUE}Step 3: Setting up Production Environment (Docker)...${NC}"

if [ "$TOOLKIT_INSTALLED" = true ]; then
    # Check Docker permissions
    if docker ps >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker compose"
    else
        echo -e "${YELLOW}Using sudo for Docker commands${NC}"
        DOCKER_COMPOSE="sudo docker compose"
    fi

    echo -e "${BLUE}Recreating production backend with GPU...${NC}"
    $DOCKER_COMPOSE stop backend-prod 2>/dev/null || true
    $DOCKER_COMPOSE rm -f backend-prod 2>/dev/null || true
    $DOCKER_COMPOSE up -d backend-prod

    echo -e "${BLUE}Recreating production frontend...${NC}"
    $DOCKER_COMPOSE stop frontend-prod 2>/dev/null || true
    $DOCKER_COMPOSE rm -f frontend-prod 2>/dev/null || true
    $DOCKER_COMPOSE up -d frontend-prod

    echo ""
    echo -e "${BLUE}Waiting for containers to start (15 seconds)...${NC}"
    sleep 15

    echo ""
    echo -e "${BLUE}Verifying GPU in production container...${NC}"
    if $DOCKER_COMPOSE exec -T backend-prod nvidia-smi 2>&1 | grep -q "RTX"; then
        echo -e "${GREEN}✓ GPU accessible in production container!${NC}"
    else
        echo -e "${YELLOW}⚠️ GPU status unclear, check logs after first upload${NC}"
    fi

    echo -e "${GREEN}Production (Docker):${NC}"
    echo "  Frontend: http://localhost:5173 (GPU: ✓ Via Docker)"
    echo "  Backend:  http://localhost:3080"
else
    echo -e "${YELLOW}Skipping production GPU setup (toolkit not installed)${NC}"
    echo "Production can still run, but will use CPU mode."
fi

# ============================================
# Summary
# ============================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Dual Environment Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Your system now has TWO environments running:"
echo ""
echo "1️⃣  Development (Native - Rapid Development)"
echo "   Frontend: http://localhost:5175"
echo "   Backend:  http://localhost:3082"
echo "   GPU:      ✓ Native access (always enabled)"
echo "   Use for:  Development, testing new features"
echo ""

if [ "$TOOLKIT_INSTALLED" = true ]; then
    echo "2️⃣  Production (Docker - Stable Deployment)"
    echo "   Frontend: http://localhost:5173"
    echo "   Backend:  http://localhost:3080"
    echo "   GPU:      ✓ Via Docker (isolated)"
    echo "   Use for:  Production, public access"
else
    echo "2️⃣  Production (Docker - CPU Mode)"
    echo "   Frontend: http://localhost:5173"
    echo "   Backend:  http://localhost:3080"
    echo "   GPU:      ✗ Toolkit not installed"
    echo "   Note:     Runs on CPU (slower)"
fi

echo ""
echo "Management Commands:"
echo "  ./manage.sh status        # Check both environments"
echo "  ./manage.sh stop-dev      # Stop development"
echo "  ./manage.sh stop-prod     # Stop production"
echo "  ./manage.sh logs-dev      # View dev logs"
echo "  ./manage.sh logs-prod     # View prod logs"
echo ""
echo "Monitor GPU usage:"
echo "  watch -n 1 nvidia-smi"
echo ""
