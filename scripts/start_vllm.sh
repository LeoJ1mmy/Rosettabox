#!/bin/bash
# ===========================================
# vLLM Server Startup Script for GX10
# NVIDIA GB10 Grace Blackwell (128GB Unified Memory)
# ===========================================
#
# This script starts vLLM using Docker container (recommended for ARM64+CUDA)
#
# Sources:
#   - NVIDIA NGC vLLM: https://catalog.ngc.nvidia.com/orgs/nvidia/containers/vllm
#   - vLLM Docker docs: https://docs.vllm.ai/en/stable/deployment/docker/

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load specific env vars from .env file (avoiding shell parsing issues)
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "📄 Loading .env from $PROJECT_ROOT/.env"
    export HF_TOKEN=$(grep -E "^HF_TOKEN=" "$PROJECT_ROOT/.env" | cut -d'=' -f2-)
    export VLLM_MAX_MODEL_LEN=$(grep -E "^VLLM_MAX_MODEL_LEN=" "$PROJECT_ROOT/.env" | cut -d'=' -f2- || echo "65536")
    export VLLM_GPU_MEM=$(grep -E "^VLLM_GPU_MEM=" "$PROJECT_ROOT/.env" | cut -d'=' -f2- || echo "0.85")
fi

# Configuration
MODEL_ID="${VLLM_MODEL:-google/gemma-3-27b-it}"
PORT="${VLLM_PORT:-8000}"
VLLM_IMAGE="${VLLM_IMAGE:-nvcr.io/nvidia/vllm:25.11-py3}"

# GX10 Optimized Settings
DTYPE="bfloat16"
MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-65536}"
GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEM:-0.85}"

echo "================================================"
echo "🚀 Starting vLLM Server on GX10 (Docker)"
echo "================================================"
echo "Image: ${VLLM_IMAGE}"
echo "Model: ${MODEL_ID}"
echo "Port: ${PORT}"
echo "Max Context: ${MAX_MODEL_LEN} tokens"
echo "GPU Memory: ${GPU_MEMORY_UTILIZATION}"
echo "Dtype: ${DTYPE}"
echo "HF_TOKEN: ${HF_TOKEN:0:10}..."
echo "================================================"

# Check HF_TOKEN for gated models
if [ -z "$HF_TOKEN" ]; then
    echo "⚠️  Warning: HF_TOKEN not set. Required for gated models like Gemma."
    echo "   Set HF_TOKEN in .env file"
    exit 1
fi

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker."
    exit 1
fi

# Stop existing container if running
echo "🛑 Stopping existing vllm-server container..."
docker stop vllm-server 2>/dev/null || true
docker rm vllm-server 2>/dev/null || true

# Create network if not exists
docker network create voice-processor-network 2>/dev/null || true

# Start vLLM container
# NVIDIA NGC vLLM container requires explicit vllm command
echo "🔄 Starting vLLM container..."
exec docker run \
    --name vllm-server \
    --runtime nvidia \
    --gpus all \
    --ipc=host \
    --ulimit memlock=-1 \
    --ulimit stack=67108864 \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e HF_TOKEN="${HF_TOKEN}" \
    -e HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}" \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    -p ${PORT}:8000 \
    --network voice-processor-network \
    --restart no \
    ${VLLM_IMAGE} \
    vllm serve "${MODEL_ID}" \
    --host 0.0.0.0 \
    --port 8000 \
    --dtype "${DTYPE}" \
    --max-model-len "${MAX_MODEL_LEN}" \
    --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
    --tensor-parallel-size 1 \
    --trust-remote-code \
    --enable-prefix-caching \
    --enforce-eager \
    --disable-log-stats \
    --disable-log-requests
