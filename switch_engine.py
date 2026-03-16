#!/usr/bin/env python3
"""
AI 引擎快速切換工具
使用方法:
  python switch_engine.py --engine ollama    # 切換到 Ollama
  python switch_engine.py --engine vllm      # 切換到 vLLM
  python switch_engine.py --status           # 查看當前狀態
  python switch_engine.py --health           # 健康檢查
  python switch_engine.py --models           # 查看可用模型
  python switch_engine.py --setup-vllm       # 設置 vLLM 環境
"""
import os
import sys
import argparse
import subprocess
import requests
import json
from pathlib import Path

# 添加 backend 到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def load_env_config():
    """載入 .env 配置"""
    env_file = Path(__file__).parent / '.env'
    config = {}
    
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key] = value
    
    return config

def update_env_config(key, value):
    """更新 .env 配置"""
    env_file = Path(__file__).parent / '.env'
    lines = []
    
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    
    # 尋找並更新現有配置
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            updated = True
            break
    
    # 如果沒找到，添加新配置
    if not updated:
        lines.append(f"{key}={value}\n")
    
    # 寫回文件
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def check_service_health(url, engine_type):
    """檢查服務健康狀態"""
    try:
        if engine_type == "ollama":
            response = requests.get(f"{url}/api/tags", timeout=5)
        else:  # vllm
            response = requests.get(f"{url}/v1/models", timeout=5)
        
        return response.status_code == 200, response.status_code
    except Exception as e:
        return False, str(e)

def get_models(url, engine_type):
    """獲取可用模型"""
    try:
        if engine_type == "ollama":
            response = requests.get(f"{url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                return [m['name'] for m in models]
        else:  # vllm
            response = requests.get(f"{url}/v1/models", timeout=5)
            if response.status_code == 200:
                models_data = response.json()
                return [m['id'] for m in models_data.get('data', [])]
    except Exception as e:
        print(f"❌ 獲取模型失敗: {e}")
    
    return []

def switch_engine(engine_type):
    """切換 AI 引擎"""
    if engine_type not in ['ollama', 'vllm']:
        print("❌ 引擎類型必須是 'ollama' 或 'vllm'")
        return False
    
    print(f"🔄 切換至 {engine_type.upper()} 引擎...")
    
    # 更新 .env 配置
    update_env_config('AI_ENGINE', engine_type)
    
    # 獲取對應的配置
    config = load_env_config()
    if engine_type == "ollama":
        url = config.get('OLLAMA_URL', 'http://localhost:11434')
        model = config.get('OLLAMA_MODEL_FIXED', 'TwinkleAI/Llama-3.2-3B-F1-Resoning-Instruct:3b')
    else:
        url = config.get('VLLM_URL', 'http://localhost:8000')
        model = config.get('VLLM_MODEL_FIXED', 'twinkle-ai/Llama-3.2-3B-F1-Instruct')
    
    # 檢查服務狀態
    is_healthy, status = check_service_health(url, engine_type)
    
    if is_healthy:
        print(f"✅ {engine_type.upper()} 服務正常運行")
        print(f"🔗 服務地址: {url}")
        print(f"🤖 預設模型: {model}")
        
        # 獲取可用模型
        models = get_models(url, engine_type)
        if models:
            print(f"📋 可用模型: {', '.join(models)}")
        
        return True
    else:
        print(f"❌ {engine_type.upper()} 服務不可用 (狀態: {status})")
        print(f"🔗 檢查地址: {url}")
        
        if engine_type == "vllm":
            print("\n💡 啟動 vLLM 服務:")
            print("   1. 設置 HF Token: hf auth login")
            print("   2. 啟動服務: vllm serve twinkle-ai/Llama-3.2-3B-F1-Instruct")
        else:
            print("\n💡 啟動 Ollama 服務:")
            print("   1. 啟動服務: ollama serve")
            print("   2. 拉取模型: ollama pull TwinkleAI/Llama-3.2-3B-F1-Resoning-Instruct:3b")
        
        if engine_type == "vllm":
            print("\n🔧 vLLM 記憶體優化建議:")
            print("   • 您的 GPU 0 目前使用了 515MB 記憶體")
            print("   • 建議清理其他 GPU 程序或使用 GPU 1")
            print("   • 嘗試降低 --gpu-memory-utilization 到 0.6 或更低")
            print("   • 減少 --max-num-seqs 到 32 或更低")
            print("\n💡 清理 GPU 記憶體:")
            print("   sudo fuser -v /dev/nvidia*  # 查看使用 GPU 的程序") 
            print("   pkill -f rustdesk  # 清理 RustDesk 程序")
            print("   pkill -f python3   # 清理其他 Python 程序")
        
        return False

def show_status():
    """顯示當前狀態"""
    config = load_env_config()
    current_engine = config.get('AI_ENGINE', 'ollama')
    
    print(f"🔧 當前 AI 引擎: {current_engine.upper()}")
    print("=" * 50)
    
    # Ollama 狀態
    ollama_url = config.get('OLLAMA_URL', 'http://localhost:11434')
    ollama_healthy, ollama_status = check_service_health(ollama_url, 'ollama')
    
    print(f"🦙 Ollama 引擎:")
    print(f"   地址: {ollama_url}")
    print(f"   狀態: {'🟢 運行中' if ollama_healthy else '🔴 離線'} ({ollama_status})")
    print(f"   模型: {config.get('OLLAMA_MODEL_FIXED', 'TwinkleAI/Llama-3.2-3B-F1-Resoning-Instruct:3b')}")
    
    if ollama_healthy:
        models = get_models(ollama_url, 'ollama')
        if models:
            print(f"   可用: {', '.join(models[:3])}{'...' if len(models) > 3 else ''}")
    
    print()
    
    # vLLM 狀態
    vllm_url = config.get('VLLM_URL', 'http://localhost:8000')
    vllm_healthy, vllm_status = check_service_health(vllm_url, 'vllm')
    
    print(f"⚡ vLLM 引擎:")
    print(f"   地址: {vllm_url}")
    print(f"   狀態: {'🟢 運行中' if vllm_healthy else '🔴 離線'} ({vllm_status})")
    print(f"   模型: {config.get('VLLM_MODEL_FIXED', 'twinkle-ai/Llama-3.2-3B-F1-Instruct')}")
    print(f"   Token: {'✅ 已設置' if config.get('HF_TOKEN') else '❌ 未設置'}")
    
    if vllm_healthy:
        models = get_models(vllm_url, 'vllm')
        if models:
            print(f"   可用: {', '.join(models[:3])}{'...' if len(models) > 3 else ''}")

def setup_vllm():
    """設置 vLLM 環境"""
    print("🚀 設置 vLLM 環境...")
    
    # 檢查 vLLM 是否已安裝
    try:
        import vllm
        print("✅ vLLM 已安裝")
    except ImportError:
        print("📦 安裝 vLLM...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "vllm"], check=True)
            print("✅ vLLM 安裝完成")
        except subprocess.CalledProcessError:
            print("❌ vLLM 安裝失敗")
            return False
    
    # 檢查 HF Token
    config = load_env_config()
    hf_token = config.get('HF_TOKEN')
    
    if not hf_token:
        print("\n🔑 設置 Hugging Face Token:")
        print("1. 前往 https://huggingface.co/settings/tokens")
        print("2. 創建或複製您的 Access Token")
        print("3. 執行: hf auth login")
        print("4. 或手動設置環境變數 HF_TOKEN")
        
        # 提供手動輸入選項
        token = input("\n請輸入您的 HF Token (或按 Enter 跳過): ").strip()
        if token:
            update_env_config('HF_TOKEN', token)
            print("✅ HF Token 已保存")
    else:
        print("✅ HF Token 已設置")
    
    print("\n🚀 啟動 vLLM 服務命令 (針對 12GB GPU 優化):")
    print("# 基本啟動命令")
    print("vllm serve twinkle-ai/Llama-3.2-3B-F1-Instruct \\")
    print("  --gpu-memory-utilization 0.7 \\")
    print("  --max-num-seqs 64 \\")
    print("  --max-model-len 4096")
    print("\n# 進一步優化 (如果仍然 OOM)")
    print("vllm serve twinkle-ai/Llama-3.2-3B-F1-Instruct \\")
    print("  --gpu-memory-utilization 0.6 \\")
    print("  --max-num-seqs 32 \\")
    print("  --max-model-len 2048 \\")
    print("  --dtype half")
    print("\n# 使用第二個 GPU (如果需要)")
    print("CUDA_VISIBLE_DEVICES=1 vllm serve twinkle-ai/Llama-3.2-3B-F1-Instruct \\")
    print("  --gpu-memory-utilization 0.8")
    
    return True

def main():
    parser = argparse.ArgumentParser(description='AI 引擎快速切換工具')
    group = parser.add_mutually_exclusive_group(required=True)
    
    group.add_argument('--engine', choices=['ollama', 'vllm'], 
                      help='切換到指定的 AI 引擎')
    group.add_argument('--status', action='store_true',
                      help='顯示當前引擎狀態')
    group.add_argument('--health', action='store_true',
                      help='檢查當前引擎健康狀態')
    group.add_argument('--models', action='store_true',
                      help='顯示可用模型')
    group.add_argument('--setup-vllm', action='store_true',
                      help='設置 vLLM 環境')
    
    args = parser.parse_args()
    
    if args.engine:
        success = switch_engine(args.engine)
        sys.exit(0 if success else 1)
    
    elif args.status:
        show_status()
    
    elif args.health:
        config = load_env_config()
        current_engine = config.get('AI_ENGINE', 'ollama')
        
        if current_engine == 'ollama':
            url = config.get('OLLAMA_URL', 'http://localhost:11434')
        else:
            url = config.get('VLLM_URL', 'http://localhost:8000')
        
        is_healthy, status = check_service_health(url, current_engine)
        
        print(f"🔍 {current_engine.upper()} 健康檢查:")
        print(f"   地址: {url}")
        print(f"   狀態: {'🟢 健康' if is_healthy else '🔴 異常'} ({status})")
        
        sys.exit(0 if is_healthy else 1)
    
    elif args.models:
        config = load_env_config()
        current_engine = config.get('AI_ENGINE', 'ollama')
        
        if current_engine == 'ollama':
            url = config.get('OLLAMA_URL', 'http://localhost:11434')
        else:
            url = config.get('VLLM_URL', 'http://localhost:8000')
        
        models = get_models(url, current_engine)
        
        if models:
            print(f"📋 {current_engine.upper()} 可用模型:")
            for model in models:
                print(f"   • {model}")
        else:
            print(f"❌ 無法獲取 {current_engine.upper()} 模型列表")
    
    elif args.setup_vllm:
        setup_vllm()

if __name__ == '__main__':
    main()