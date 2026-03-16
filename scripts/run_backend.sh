#!/bin/bash
# Backend startup script for ASUS GX10 / NVIDIA GB10
# 128GB Unified Memory, CUDA 13.0, ARM64 Architecture

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 LeoQxAIBox Backend Startup (ASUS GX10)"
echo "=========================================="

# Activate virtual environment
if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
else
    echo "⚠️  Virtual environment not found at $PROJECT_DIR/venv"
    echo "   Please create it with: python3 -m venv $PROJECT_DIR/venv"
    exit 1
fi

# Find the cuDNN library path in venv
PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
CUDNN_LIB_PATH="$PROJECT_DIR/venv/lib/python${PYTHON_VERSION}/site-packages/nvidia/cudnn/lib"

# Also add ctranslate2 bundled cuDNN libraries
CT2_LIB_PATH="$PROJECT_DIR/venv/lib/python${PYTHON_VERSION}/site-packages/ctranslate2.libs"

# Set LD_LIBRARY_PATH to include cuDNN libraries (CRITICAL for GPU support)
if [ -d "$CUDNN_LIB_PATH" ]; then
    export LD_LIBRARY_PATH="$CUDNN_LIB_PATH:$CT2_LIB_PATH:/usr/local/cuda/lib64:$LD_LIBRARY_PATH"
    echo "✅ cuDNN library paths set:"
    echo "   - $CUDNN_LIB_PATH"
    echo "   - $CT2_LIB_PATH"
    echo ""
    echo "📊 GPU Support: Enabled (NVIDIA GB10 with CUDA 13.0)"
    echo "   - Architecture: Blackwell (sm_120)"
    echo "   - Memory: 128GB Unified"
else
    echo "⚠️  cuDNN library path not found"
    echo "📊 GPU Support: CPU fallback only"
fi

echo ""
echo "🔧 Starting backend server..."
echo ""

# Check if gunicorn is installed
if ! command -v gunicorn &> /dev/null; then
    echo "📥 Installing Gunicorn (production WSGI server)..."
    pip install gunicorn
    echo ""
fi

echo "🚀 Using Gunicorn (production server) instead of Flask dev server"
echo "   - Workers: 4 (handles concurrent uploads)"
echo "   - Timeout: 60 minutes (for large file processing)"
echo "   - Port: 3080"
echo ""

# Start backend with Gunicorn
cd "$PROJECT_DIR/backend"
exec gunicorn \
  --bind 0.0.0.0:3080 \
  --workers 4 \
  --threads 2 \
  --timeout 3600 \
  --keep-alive 300 \
  --max-requests 1000 \
  --max-requests-jitter 50 \
  --limit-request-line 8190 \
  --limit-request-field_size 8190 \
  --limit-request-body 0 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  --worker-class sync \
  app:app
