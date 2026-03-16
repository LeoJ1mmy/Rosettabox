#!/bin/bash
# ==========================================
# ASUS GX10 Production Deployment Script
# Voice-Text-Processor
# ==========================================

set -e

echo "=========================================="
echo "  ASUS GX10 Production Deployment"
echo "  Voice-Text-Processor"
echo "=========================================="
echo ""

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Check if running as root or with docker access
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Cannot access Docker. Please run with sudo or add user to docker group."
    echo "  sudo usermod -aG docker \$USER"
    echo "  newgrp docker"
    exit 1
fi

# Display hardware info
echo "Hardware Information:"
echo "---------------------"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null || echo "GPU: NVIDIA GB10"
echo ""

# Check Ollama status
echo "Checking Ollama status..."
if ollama list | grep -q "gpt-oss:120b"; then
    echo "✅ Model gpt-oss:120b is available"
else
    echo "⚠️  Model gpt-oss:120b not found. Please wait for download to complete."
    echo "   Check progress: tail -f /tmp/ollama_pull.log"
fi
echo ""

# Step 1: Pull base image
echo "Step 1: Pulling NVIDIA PyTorch base image (ARM64)..."
echo "-----------------------------------------------------"
docker pull nvcr.io/nvidia/pytorch:25.09-py3
echo ""

# Step 2: Build images
echo "Step 2: Building production Docker images..."
echo "---------------------------------------------"
docker compose build --no-cache
echo ""

# Step 3: Start services
echo "Step 3: Starting production services..."
echo "----------------------------------------"
docker compose up -d
echo ""

# Step 4: Wait for services to start
echo "Step 4: Waiting for services to start..."
echo "-----------------------------------------"
sleep 10

# Step 5: Check status
echo "Step 5: Checking service status..."
echo "-----------------------------------"
docker compose ps
echo ""

# Health check
echo "Step 6: Running health checks..."
echo "---------------------------------"
if curl -s http://localhost:3080/api/info > /dev/null 2>&1; then
    echo "✅ Backend is healthy (http://localhost:3080)"
else
    echo "⏳ Backend is starting up..."
fi

if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ Frontend is healthy (http://localhost:5173)"
else
    echo "⏳ Frontend is starting up..."
fi
echo ""

echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "Service URLs:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:3080"
echo ""
echo "Commands:"
echo "  View logs:    docker compose logs -f"
echo "  Stop:         docker compose down"
echo "  Restart:      docker compose restart"
echo ""
