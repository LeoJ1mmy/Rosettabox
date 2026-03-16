# GPU-enabled Docker image for Voice Text Processor
# Optimized for ASUS GX10 / NVIDIA GB10 (ARM64 + CUDA 13.0)
# syntax=docker/dockerfile:1.4

# Use NVIDIA PyTorch container for ARM64 with CUDA support
# 25.09-py3: PyTorch 2.9.0a + CUDA 13.0.1, optimized for DGX Spark/GB10
# Fixes sm_120 (Blackwell) NVRTC JIT compilation issues
FROM nvcr.io/nvidia/pytorch:25.09-py3

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install additional system dependencies with BuildKit cache
# 使用 BuildKit 快取，避免每次重建都重新下載 apt 套件
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    curl \
    # torchaudio build dependencies
    sox \
    libsox-dev \
    libsox-fmt-all \
    cmake \
    ninja-build \
    pkg-config \
    git

# Upgrade pip
RUN pip install --upgrade pip

# Set working directory
WORKDIR /app

# Copy requirements file from root
COPY requirements.txt .

# CRITICAL: Preserve CUDA-enabled PyTorch from base image
# Filter out torch packages from requirements.txt before installing
# The NVIDIA base image has PyTorch with CUDA 13.0 support for GB10
# 使用 BuildKit 快取，避免每次重建都重新下載 pip 套件
RUN --mount=type=cache,target=/root/.cache/pip \
    grep -v -E "^torch|^torchaudio|^torchvision" requirements.txt > requirements_filtered.txt && \
    pip install -r requirements_filtered.txt && \
    rm requirements_filtered.txt

# Install OpenAI Whisper (transformers backend) - uses PyTorch CUDA directly
# Bypasses ctranslate2 ARM64 CUDA limitation
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install openai-whisper transformers accelerate

# ============================================================
# Build torchaudio from source to match NVIDIA's PyTorch
# ============================================================
# Standard torchaudio from PyPI has symbol mismatches with NVIDIA's custom PyTorch
# Building from source ensures compatibility
# --no-build-isolation: use system's PyTorch during build
# --no-deps: skip torch version check (NVIDIA uses custom version string)
RUN cd /tmp && \
    git clone --depth 1 --branch v2.9.0 https://github.com/pytorch/audio.git torchaudio && \
    cd torchaudio && \
    pip install --no-build-isolation --no-deps . && \
    cd / && rm -rf /tmp/torchaudio

# Verify torchaudio is working
RUN python3 -c "import torchaudio; print('torchaudio:', torchaudio.__version__)"

# ============================================================
# CRITICAL: Create pip constraints to protect NVIDIA's CUDA PyTorch
# ============================================================
# After torchaudio is built, freeze torch/torchaudio versions.
# All subsequent pip installs use this constraint file to prevent
# packages (clearvoice, etc.) from overwriting CUDA PyTorch
# with a CPU-only version from PyPI.
RUN python3 -c "\
import torch, torchaudio; \
lines = [f'torch=={torch.__version__}', f'torchaudio=={torchaudio.__version__}']; \
open('/tmp/pip-constraints.txt','w').write('\n'.join(lines)+'\n'); \
print('🔒 PyTorch constraints:'); [print(f'   {l}') for l in lines]"

# ============================================================
# P3: ClearerVoice 語音增強（可選，預設關閉）
# ============================================================
# MossFormerGAN_SE_16K: PESQ 3.57, native 16kHz, 匹配 Whisper
# --no-deps: 防止 clearvoice 拉入 CPU-only PyTorch
# clearvoice 的其他依賴（numpy, soundfile, scipy）已由先前步驟安裝
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install clearvoice --no-deps || echo "⚠️ clearvoice 安裝失敗（可選功能，不影響核心服務）"

# ============================================================
# CRITICAL: Verify CUDA PyTorch is intact (FAIL BUILD if not)
# ============================================================
# If any pip install overwrote NVIDIA's CUDA PyTorch, this will catch it
RUN python3 -c "\
import torch; \
v = torch.__version__; \
cuda_ok = torch.backends.cuda.is_built(); \
print(f'PyTorch: {v}, CUDA compiled: {cuda_ok}'); \
assert cuda_ok, f'❌ FATAL: PyTorch {v} has no CUDA support! A pip install likely overwrote NVIDIA CUDA PyTorch with CPU version. Build aborted.'; \
print('✅ CUDA PyTorch verified')"
RUN python3 -c "import torchaudio; print('torchaudio:', torchaudio.__version__)"

# Install Gunicorn for production WSGI server
RUN --mount=type=cache,target=/root/.cache/pip pip install gunicorn

# Set LD_LIBRARY_PATH for cuDNN and ctranslate2 (additional GPU support)
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/dist-packages/nvidia/cudnn/lib:/usr/local/lib/python3.12/dist-packages/ctranslate2.libs:/usr/local/cuda/lib64:$LD_LIBRARY_PATH

# Copy backend code to /app (not /app/backend)
COPY backend/ .

# Create uploads directory
RUN mkdir -p /app/uploads

# Expose port (will be set by environment variable)
EXPOSE ${PORT:-3080}

# Run the backend application with Gunicorn (production WSGI server)
# - Single worker to avoid task processor conflicts
# - Long timeout for audio processing
# - Preload app to share model loading
CMD ["gunicorn", \
     "--bind", "0.0.0.0:3080", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "1800", \
     "--keep-alive", "300", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "--worker-class", "sync", \
     "app:app"]
