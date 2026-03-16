import { useCallback } from 'react';
import axios from 'axios';

// 動態 API 基礎 URL - 與 useFileUpload 保持一致
const getApiBaseUrl = () => {
  const hostname = window.location.hostname;
  const protocol = window.location.protocol;
  const port = window.location.port;

  if (protocol === 'https:' || !port || port === '80' || port === '443') {
    return '/api';
  }

  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return '/api';
  }

  return `${protocol}//${hostname}:3080/api`;
};

const API_BASE_URL = getApiBaseUrl();

export const useTextProcessing = (appState) => {
  const {
    textInput,
    setProcessing,
    setError,
    setResult,
    setCurrentTaskId,
    setTaskProgress,
    processingMode,
    enableLLMProcessing,
    aiModel,
    userId,
    customModePrompt,
    customDetailPrompt,
    emailEnabled,
    emailAddress,
    selectedTags,
    customTagPrompt,
    enableCleanFiller,
  } = appState;

  // 輪詢任務狀態 - 與 useFileUpload 邏輯一致
  const pollTaskStatus = useCallback(async (taskId) => {
    const maxAttempts = 600;
    let attempts = 0;
    let pollInterval = 2000;

    const checkStatus = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/task/${taskId}/status?user_id=${userId}`);
        const taskData = response.data;

        if (taskData.status === 'completed') {
          setTaskProgress(null);
          if (taskData.result) {
            setResult(taskData.result);
            setProcessing(false);
            setTimeout(() => setCurrentTaskId(null), 3000);
          } else {
            try {
              const resultResponse = await axios.get(`${API_BASE_URL}/task/${taskId}/result?user_id=${userId}`);
              setResult(resultResponse.data);
            } catch {
              setResult({ message: '任務已完成，但無法獲取詳細結果' });
            }
            setProcessing(false);
            setTimeout(() => setCurrentTaskId(null), 3000);
          }
        } else if (taskData.status === 'failed' || taskData.status === 'error') {
          setTaskProgress(null);
          setError(taskData.error || '任務處理失敗');
          setProcessing(false);
          setCurrentTaskId(null);
        } else if (taskData.status === 'cancelled') {
          setTaskProgress(null);
          setError('任務已被取消');
          setProcessing(false);
          setCurrentTaskId(null);
        } else if (taskData.status === 'processing' || taskData.status === 'pending' || taskData.status === 'queued') {
          if (taskData.progress) {
            setTaskProgress(prev => {
              const newPct = taskData.progress.percentage || 0;
              if (prev && prev.percentage > newPct) return prev;
              return {
                stage: taskData.progress.stage || '',
                percentage: newPct,
                message: taskData.progress.message || '',
              };
            });
          }
          attempts++;
          if (attempts < maxAttempts) {
            if (attempts > 50) pollInterval = 10000;
            else if (attempts > 20) pollInterval = 5000;
            else if (attempts > 5) pollInterval = 3000;
            else pollInterval = 2000;
            setTimeout(checkStatus, pollInterval);
          } else {
            setError('任務處理超時');
            setProcessing(false);
          }
        }
      } catch {
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(checkStatus, Math.min(pollInterval * 1.5, 10000));
        } else {
          setError('無法檢查任務狀態');
          setProcessing(false);
        }
      }
    };

    checkStatus();
  }, [userId, setResult, setError, setProcessing, setCurrentTaskId, setTaskProgress]);

  const handleTextProcess = useCallback(async () => {
    if (!textInput || textInput.trim().length < 10) {
      setError('文字內容至少需要 10 個字元');
      return;
    }

    setProcessing(true);
    setError(null);
    setResult(null);
    // 同步路徑無輪詢，先給一個模擬進度讓 UI 有回饋
    setTaskProgress({ stage: 'AI 處理中', percentage: 30, message: '正在進行 AI 智能整理...' });

    try {
      const payload = {
        text: textInput.trim(),
        user_id: userId,
        processing_mode: processingMode,
        detail_level: 'normal',
        ai_model: aiModel,
        enable_clean_filler: enableCleanFiller,
      };

      if (processingMode === 'custom' && customModePrompt) {
        payload.custom_mode_prompt = customModePrompt;
      }
      if (customDetailPrompt) {
        payload.custom_detail_prompt = customDetailPrompt;
      }

      if (emailEnabled && emailAddress) {
        payload.email_enabled = true;
        payload.email_address = emailAddress;
      }

      if (selectedTags && selectedTags.length > 0) {
        payload.selected_tags = selectedTags;
      }

      if (selectedTags && selectedTags.includes('custom') && customTagPrompt) {
        payload.custom_prompt = customTagPrompt;
      }

      const response = await axios.post(`${API_BASE_URL}/text/process`, payload);

      const data = response.data?.data || response.data;

      if (data.task_id) {
        // 長文字走佇列，開始輪詢
        setCurrentTaskId(data.task_id);
        pollTaskStatus(data.task_id);
      } else {
        // 短文字同步回傳結果
        setTaskProgress(null);
        const result = {
          whisper_result: data.original_text || textInput.trim(),
          ai_summary: data.processed_text || data.summary,
          original_text: data.original_text || textInput.trim(),
          processed_text: data.processed_text || data.summary,
          processing_mode: data.processing_mode || processingMode,
          enable_llm_processing: true,
          source_type: 'text',
          status: 'completed',
        };
        setResult(result);
        setProcessing(false);
        setCurrentTaskId(null);
      }
    } catch (err) {
      setTaskProgress(null);
      const errData = err.response?.data;
      // 優先提取 validation_errors 詳細資訊
      const validationErrors = errData?.error?.details?.validation_errors;
      const errorMsg = (validationErrors
          ? (Array.isArray(validationErrors) ? validationErrors.join('; ') : String(validationErrors))
          : null)
        || (typeof errData?.error === 'string' ? errData.error : errData?.error?.message)
        || errData?.message
        || err.message
        || '文字處理失敗';
      setError(errorMsg);
      setProcessing(false);
    }
  }, [
    textInput,
    processingMode,
    enableLLMProcessing,
    aiModel,
    userId,
    customModePrompt,
    customDetailPrompt,
    emailEnabled,
    emailAddress,
    selectedTags,
    customTagPrompt,
    enableCleanFiller,
    setProcessing,
    setError,
    setResult,
    setCurrentTaskId,
    setTaskProgress,
    pollTaskStatus,
  ]);

  return {
    handleTextProcess,
  };
};
