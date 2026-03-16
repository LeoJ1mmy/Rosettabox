#!/bin/bash
# ===========================================
# Backend 啟動腳本 - 跨平台 cuDNN 環境設置
# ===========================================
# 此腳本會在啟動 Gunicorn 前動態設置 LD_LIBRARY_PATH
# 支援 WSL, Ubuntu, macOS 等不同環境

set -e

# 獲取腳本所在目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv"

# 激活虛擬環境
source "$VENV_DIR/bin/activate"

# 動態獲取 site-packages 路徑
SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0] if site.getsitepackages() else '')")

if [ -z "$SITE_PACKAGES" ]; then
    # Fallback for venv
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    SITE_PACKAGES="$VENV_DIR/lib/python${PYTHON_VERSION}/site-packages"
fi

# 設置 cuDNN 庫路徑（僅在 CUDA 可用時）
CUDA_AVAILABLE=$(python3 -c "import torch; print('1' if torch.cuda.is_available() else '0')" 2>/dev/null || echo "0")

if [ "$CUDA_AVAILABLE" = "1" ]; then
    CT2_LIBS="$SITE_PACKAGES/ctranslate2.libs"
    CUDNN_LIBS="$SITE_PACKAGES/nvidia/cudnn/lib"

    # 構建 LD_LIBRARY_PATH（優先使用 ctranslate2.libs）
    NEW_LD_PATH=""

    if [ -d "$CT2_LIBS" ]; then
        NEW_LD_PATH="$CT2_LIBS"
    fi

    if [ -d "$CUDNN_LIBS" ]; then
        if [ -n "$NEW_LD_PATH" ]; then
            NEW_LD_PATH="$NEW_LD_PATH:$CUDNN_LIBS"
        else
            NEW_LD_PATH="$CUDNN_LIBS"
        fi
    fi

    # 合併現有的 LD_LIBRARY_PATH
    if [ -n "$NEW_LD_PATH" ]; then
        if [ -n "$LD_LIBRARY_PATH" ]; then
            export LD_LIBRARY_PATH="$NEW_LD_PATH:$LD_LIBRARY_PATH"
        else
            export LD_LIBRARY_PATH="$NEW_LD_PATH"
        fi
        echo "✅ cuDNN 庫路徑已設置: $LD_LIBRARY_PATH"
    fi
fi

# 切換到 backend 目錄
cd "$PROJECT_DIR/backend"

# 啟動 Gunicorn（使用傳入的參數）
exec gunicorn "$@"
