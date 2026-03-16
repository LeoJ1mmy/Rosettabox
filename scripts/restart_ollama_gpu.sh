#!/bin/bash
# 重啟 Ollama 並設置 GPU 環境變數

echo "🔄 重啟 Ollama 服務以啟用 GPU..."

# 殺死現有的 Ollama 進程
echo "⏹️ 停止現有的 Ollama 進程..."
pkill -f "ollama serve" || true
pkill -f "ollama runner" || true
sleep 3

# 設置 GPU 相關環境變數
export CUDA_VISIBLE_DEVICES=0
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
export PATH=/usr/local/cuda/bin:$PATH

# 設置 Ollama GPU 選項（儘管有驅動問題，仍嘗試使用GPU）
export OLLAMA_HOST=0.0.0.0:11434
export OLLAMA_ORIGINS=*
export OLLAMA_GPU_LAYERS=-1          # 嘗試使用所有GPU層
export OLLAMA_NUM_PARALLEL=1         # 減少並行以提高穩定性
export OLLAMA_MAX_LOADED_MODELS=1    # 一次只加載一個模型
export OLLAMA_DEBUG=1                # 啟用調試輸出

echo "🚀 使用以下環境變數啟動 Ollama:"
echo "  CUDA_VISIBLE_DEVICES: $CUDA_VISIBLE_DEVICES"
echo "  OLLAMA_GPU_LAYERS: $OLLAMA_GPU_LAYERS"
echo "  OLLAMA_NUM_PARALLEL: $OLLAMA_NUM_PARALLEL"

# 在背景啟動 Ollama
nohup ollama serve > /tmp/ollama.log 2>&1 &

echo "⏳ 等待 Ollama 啟動..."
sleep 10

# 檢查狀態
echo "📊 Ollama 狀態:"
ollama ps

echo "✅ Ollama 已重啟！"
echo "📋 可以使用 'tail -f /tmp/ollama.log' 查看詳細日誌"