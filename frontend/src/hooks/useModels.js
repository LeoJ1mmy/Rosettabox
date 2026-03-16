import { useEffect } from 'react';
import axios from 'axios';

// 動態 API 基礎 URL - 支持 LAN 訪問和 Cloudflare Tunnel
const getApiBaseUrl = () => {
  const hostname = window.location.hostname;
  const protocol = window.location.protocol;
  const port = window.location.port;

  // HTTPS（Cloudflare Tunnel）或標準端口：使用相對路徑
  if (protocol === 'https:' || !port || port === '80' || port === '443') {
    return '/api';
  }

  // 本地開發：localhost 或 127.0.0.1 使用 Vite proxy
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return '/api';
  }

  // LAN 訪問（非隧道）：使用同協議直連後端
  // 🔧 使用生產環境端口 3080
  return `${protocol}//${hostname}:3080/api`;
};

const API_BASE_URL = getApiBaseUrl();

export const useModels = ({
  setAvailableModels,
  setAvailableAiModels,
  setModelLoading,
  setWhisperModel,
  setAiModel,
  setOllamaStatus
}) => {
  useEffect(() => {
    const fetchModels = async () => {
      // 檢查環境變數是否啟用動態模型載入
      const enableDynamic = import.meta.env.VITE_ENABLE_DYNAMIC_MODELS === 'true';

      if (!enableDynamic) {
        // 使用靜態預設模型列表
        setAvailableModels([
          { id: 'breeze-asr-1.2g', name: 'Breeze ASR-1.2G (推薦)', size: '1.2GB', speed: '快', accuracy: '優秀' },
          { id: 'tiny', name: 'Whisper Tiny', size: '39MB', speed: '極快', accuracy: '一般' },
          { id: 'base', name: 'Whisper Base', size: '74MB', speed: '快', accuracy: '良好' },
          { id: 'small', name: 'Whisper Small', size: '244MB', speed: '中等', accuracy: '很好' },
          { id: 'medium', name: 'Whisper Medium', size: '769MB', speed: '慢', accuracy: '優秀' },
          { id: 'large', name: 'Whisper Large', size: '1550MB', speed: '很慢', accuracy: '最佳' }
        ]);

        setAvailableAiModels([
          { id: 'gpt-oss:120b', name: 'GPT-OSS 120B', size: '65GB', recommended: true },
          { id: 'gemma3:27b', name: 'Gemma 3 27B', size: '17GB' },
          { id: 'qwen2.5-coder:14b', name: 'Qwen 2.5 Coder 14B', size: '9.0GB' },
          { id: 'deepseek-r1:14b', name: 'DeepSeek R1 14B', size: '9.0GB' },
          { id: 'phi4:14b', name: 'Phi-4 14B', size: '9.1GB' },
          { id: 'qwq:32b', name: 'QwQ 32B', size: '19GB' },
          { id: 'llama3.1:8b', name: 'Llama 3.1 8B', size: '4.7GB' }
        ]);

        // 模擬檢查 Ollama 狀態
        if (setOllamaStatus) {
           setOllamaStatus({ status: 'connected', message: '已連線 (靜態模式)' });
        }
        return;
      }

      setModelLoading(true);
      try {
        // 獲取 Whisper 模型
        try {
          const whisperResponse = await axios.get(`${API_BASE_URL}/whisper/models`);
          if (whisperResponse.data && whisperResponse.data.models) {
            setAvailableModels(whisperResponse.data.models);

            // 如果是固定模型，設置為預設選擇
            if (whisperResponse.data.fixed_model && setWhisperModel) {
              setWhisperModel(whisperResponse.data.fixed_model);
            }
          }
        } catch (err) {
          // Whisper 模型獲取失敗，使用預設列表
        }

        // 獲取 AI 模型
        try {
          const aiResponse = await axios.get(`${API_BASE_URL}/ai/models`);
          if (aiResponse.data && aiResponse.data.models) {
            setAvailableAiModels(aiResponse.data.models);

            // 如果是固定模型，設置為預設選擇
            if (aiResponse.data.fixed_model && setAiModel) {
              setAiModel(aiResponse.data.fixed_model);
            }
          }
        } catch (err) {
          // AI 模型獲取失敗，使用預設列表
        }

        // 检查 Ollama 状态
        try {
          const ollamaResponse = await axios.get(`${API_BASE_URL}/ollama/status`);
          if (setOllamaStatus && ollamaResponse.data) {
            setOllamaStatus(ollamaResponse.data);
          }
        } catch (err) {
          if (setOllamaStatus) {
            setOllamaStatus({ status: 'error', message: '連接失敗' });
          }
        }

      } catch (err) {
        // 獲取模型列表失敗，使用靜態預設列表
      } finally {
        setModelLoading(false);
      }
    };

    fetchModels();
  }, [setAvailableModels, setAvailableAiModels, setModelLoading, setWhisperModel, setAiModel, setOllamaStatus]);
};
