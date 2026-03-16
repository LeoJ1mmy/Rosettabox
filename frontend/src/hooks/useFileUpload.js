import { useCallback } from 'react';
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

export const useFileUpload = (appState) => {
  const {
    files,
    setProcessing,
    setUploading,
    setUploadProgress,
    setUploadSpeed,
    setError,
    setResult,
    currentTaskId,
    setCurrentTaskId,
    setTaskProgress,
    processingMode,
    enableLLMProcessing,
    whisperModel,
    aiModel,
    userId,
    customModePrompt,
    customDetailPrompt,
    customFormatTemplate,
    emailEnabled,
    emailAddress,
    selectedTags,
    customTagPrompt,
    estimatedSpeakers
  } = appState;

  // 🔧 優化：輪詢任務狀態的函數 - 使用指數退避減少請求數
  const pollTaskStatus = useCallback(async (taskId) => {
    const maxAttempts = 600; // 🔧 優化：減少最大嘗試次數（從1800降到600）
    let attempts = 0;
    let pollInterval = 2000; // 🔧 優化：初始間隔改為2秒（從1秒增加到2秒）
    const maxInterval = 10000; // 最大間隔10秒

    const checkStatus = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/task/${taskId}/status?user_id=${userId}`);
        const taskData = response.data;

        if (taskData.status === 'completed') {
          setTaskProgress(null);
          // 任務完成，先嘗試從狀態響應中獲取結果
          if (taskData.result) {
            setResult(taskData.result);
            setProcessing(false);
            // 延遲3秒再清除任務ID，讓用戶看到完成狀態
            setTimeout(() => {
              setCurrentTaskId(null);
            }, 3000);
          } else {
            // 如果狀態響應中沒有結果，嘗試獲取結果
            try {
              const resultResponse = await axios.get(`${API_BASE_URL}/task/${taskId}/result?user_id=${userId}`);
              setResult(resultResponse.data);
              setProcessing(false);
              // 延遲3秒再清除任務ID，讓用戶看到完成狀態
              setTimeout(() => {
                setCurrentTaskId(null);
              }, 3000);
            } catch (resultErr) {
              // 如果獲取結果失敗，但任務已完成，至少顯示完成狀態
              setResult({ message: '任務已完成，但無法獲取詳細結果' });
              setProcessing(false);
              // 延遲3秒再清除任務ID，讓用戶看到完成狀態
              setTimeout(() => {
                setCurrentTaskId(null);
              }, 3000);
            }
          }
        } else if (taskData.status === 'failed' || taskData.status === 'error') {
          // 任務失敗
          setTaskProgress(null);
          setError(taskData.error || '任務處理失敗');
          setProcessing(false);
          setCurrentTaskId(null); // 清除任務ID
        } else if (taskData.status === 'cancelled') {
          // 任務被取消 - 停止輪詢並更新 UI
          setTaskProgress(null);
          setError('任務已被取消');
          setProcessing(false);
          setCurrentTaskId(null); // 清除任務ID
        } else if (taskData.status === 'processing' || taskData.status === 'pending' || taskData.status === 'queued') {
          // 提取進度數據
          if (taskData.progress) {
            setTaskProgress(prev => {
              const newPct = taskData.progress.percentage || 0;
              // 防止進度倒退
              if (prev && prev.percentage > newPct) {
                return prev;
              }
              return {
                stage: taskData.progress.stage || '',
                percentage: newPct,
                message: taskData.progress.message || '',
              };
            });
          }
          // 任務仍在進行中，繼續輪詢
          attempts++;
          if (attempts < maxAttempts) {
            // 🔧 優化：指數退避策略
            // 前5次：2秒間隔（快速反馈）
            // 5-20次：3秒間隔（正常處理）
            // 20-50次：5秒間隔（長時處理）
            // 50+次：10秒間隔（超長處理）
            if (attempts > 50) {
              pollInterval = 10000;
            } else if (attempts > 20) {
              pollInterval = 5000;
            } else if (attempts > 5) {
              pollInterval = 3000;
            } else {
              pollInterval = 2000;
            }

            setTimeout(checkStatus, pollInterval);
          } else {
            setError('任務處理超時');
            setProcessing(false);
          }
        }
      } catch (err) {
        attempts++;
        if (attempts < maxAttempts) {
          // 錯誤重試也使用動態間隔
          const retryInterval = Math.min(pollInterval * 1.5, maxInterval);
          setTimeout(checkStatus, retryInterval);
        } else {
          setError('無法檢查任務狀態');
          setProcessing(false);
        }
      }
    };

    checkStatus();
  }, [userId, setResult, setError, setProcessing]);

  const handleFileUpload = useCallback(async () => {
    if (!files || files.length === 0) {
      setError('請選擇文件');
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setUploadSpeed(0);
    setError(null);
    setResult(null);

    // 追蹤上傳速度
    let startTime = Date.now();
    let lastLoaded = 0;
    let lastTime = startTime;

    try {
      const formData = new FormData();
      // 添加多個音頻文件
      files.forEach((file, index) => {
        formData.append(`audio_${index}`, file);
      });
      formData.append('file_count', files.length.toString());
      formData.append('mode', processingMode);
      formData.append('enable_llm', enableLLMProcessing.toString());
      formData.append('whisper_model', whisperModel);
      formData.append('ai_model', aiModel);
      formData.append('user_id', userId);

      // 添加自定義參數
      if (processingMode === 'custom' && customModePrompt) {
        formData.append('custom_mode_prompt', customModePrompt);
      }
      if (customDetailPrompt) {
        formData.append('custom_detail_prompt', customDetailPrompt);
      }

      // 添加 Email 通知參數
      if (emailEnabled && emailAddress) {
        formData.append('email_enabled', 'true');
        formData.append('email_address', emailAddress);
      }

      // 添加標籤參數
      if (selectedTags && selectedTags.length > 0) {
        formData.append('selected_tags', JSON.stringify(selectedTags));
      }

      // 添加自定義標籤 Prompt（當選擇了 custom 標籤時）
      if (selectedTags && selectedTags.includes('custom') && customTagPrompt) {
        formData.append('custom_tag_prompt', customTagPrompt);
      }

      const response = await axios.post(`${API_BASE_URL}/audio/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 3600000, // 60分鐘超時（用於超大文件上傳，例如2小時音頻文件）
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percentCompleted);

          // 計算上傳速度
          const currentTime = Date.now();
          const timeDiff = (currentTime - lastTime) / 1000; // 秒

          if (timeDiff > 0.5) { // 每0.5秒更新一次速度
            const bytesDiff = progressEvent.loaded - lastLoaded;
            const speed = bytesDiff / timeDiff; // bytes/sec
            setUploadSpeed(speed);
            lastLoaded = progressEvent.loaded;
            lastTime = currentTime;
          }
        }
      });

      setUploadProgress(100);
      setUploading(false);
      setProcessing(true);
      
      // 檢查返回的響應是否包含任務ID
      if (response.data && response.data.task_id) {
        // 保存任務ID並開始輪詢任務狀態
        setCurrentTaskId(response.data.task_id);
        pollTaskStatus(response.data.task_id);
      } else {
        // 如果沒有任務ID，說明是同步處理，直接設置結果
        setResult(response.data);
        setProcessing(false);
        setCurrentTaskId(null);
      }
    } catch (err) {
      if (err.response?.status === 413) {
        const totalMB = (files.reduce((sum, f) => sum + f.size, 0) / 1024 / 1024).toFixed(1);
        const isCloudflare = window.location.protocol === 'https:';
        if (isCloudflare) {
          setError(`檔案大小 (${totalMB}MB) 超出 Cloudflare Tunnel 的 100MB 上傳限制。請改用區域網路 (LAN) 直連方式上傳大檔案。`);
        } else {
          setError(`檔案上傳失敗：伺服器拒絕了 ${totalMB}MB 的請求 (413)。`);
        }
      } else {
        setError(err.response?.data?.error || err.message);
      }
      setUploading(false);
      setUploadProgress(0);
    } finally {
      // 注意：processing 狀態由處理完成時設置為 false
      // setProcessing(false); 在處理完成時才設置
    }
  }, [
    files,
    processingMode,
    enableLLMProcessing,
    whisperModel,
    aiModel,
    userId,
    customModePrompt,
    customDetailPrompt,
    customFormatTemplate,
    emailEnabled,
    emailAddress,
    selectedTags,
    customTagPrompt,
    estimatedSpeakers,
    setProcessing,
    setUploading,
    setUploadProgress,
    setCurrentTaskId,
    setError,
    setResult,
    pollTaskStatus
  ]);

  return {
    handleFileUpload
  };
};