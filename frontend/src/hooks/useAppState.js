import { useState, useEffect, useLayoutEffect } from 'react';
import storageManager from '../utils/storage';
import { useModels } from './useModels';
import apiService from '../services/api';

export const useAppState = () => {
  // 基本狀態
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('voice_processor_theme') || 'light'; }
    catch { return 'light'; }
  });
  const [activeTab, setActiveTab] = useState('upload');

  // 包裝 setActiveTab 以防止訪問已移除的頁面
  const setActiveTabSafe = (tab) => {
    // 離開熱詞管理頁面時自動鎖定（清除密碼）
    if (activeTab === 'hotwords' && tab !== 'hotwords') {
      setAdminPassword(null);
    }

    setActiveTab(tab);
  };
  const [userId, setUserId] = useState('');

  // 文件和處理狀態
  const [files, setFiles] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadSpeed, setUploadSpeed] = useState(0); // 上傳速度 (bytes/sec)
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [currentTaskId, setCurrentTaskId] = useState(null);
  const [taskProgress, setTaskProgress] = useState(null);
  // shape: { stage: string, percentage: number, message: string }

  // 處理設置
  const [processingMode, setProcessingMode] = useState('default');
  const [whisperModel, setWhisperModel] = useState('breeze-asr-1.2g');
  const [aiModel, setAiModel] = useState('gpt-oss:120b');
  const [enableLLMProcessing, setEnableLLMProcessing] = useState(true);
  const [availableModels, setAvailableModels] = useState([]);
  const [availableAiModels, setAvailableAiModels] = useState([]);
  const [modelLoading, setModelLoading] = useState(false);
  const [ollamaStatus, setOllamaStatus] = useState({ status: 'checking', message: '檢查中...' });

  // 自定義模式狀態
  const [customModePrompt, setCustomModePrompt] = useState('');
  const [customDetailPrompt, setCustomDetailPrompt] = useState('');
  const [showCustomModal, setShowCustomModal] = useState(false);
  const [customModalType, setCustomModalType] = useState('');

  // 標籤狀態
  const [selectedTags, setSelectedTags] = useState([]);
  const [customTagPrompt, setCustomTagPrompt] = useState('');

  // Email 通知設定
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [emailAddress, setEmailAddress] = useState('');

  // 文字處理設定
  const [textInput, setTextInput] = useState('');
  const [enableCleanFiller, setEnableCleanFiller] = useState(true);
  const [sourceType, setSourceType] = useState('audio'); // 'audio' | 'text'

  // 系統配置
  const [systemConfig, setSystemConfig] = useState(null);
  const [emailFeatureEnabled, setEmailFeatureEnabled] = useState(false);

  // 管理員權限
  const [adminPassword, setAdminPassword] = useState(null);

  // 初始化
  useEffect(() => {
    const id = storageManager.getUserId() || `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    storageManager.setUserId(id);
    setUserId(id);

    const savedTheme = storageManager.getTheme() || 'light';
    setTheme(savedTheme);
  }, []);

  // 載入系統配置
  useEffect(() => {
    const loadSystemConfig = async () => {
      try {
        const response = await apiService.getSystemConfig();
        if (response.status === 'success') {
          setSystemConfig(response.data);
          setEmailFeatureEnabled(response.data.email_enabled || false);
        }
      } catch (error) {
        // 如果無法載入配置，預設不顯示 Email 功能
        setEmailFeatureEnabled(false);
      }
    };

    loadSystemConfig();
  }, []);

  // 主題切換
  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    storageManager.setTheme(newTheme);

    // 立即更新 DOM
    if (newTheme === 'dark') {
      document.documentElement.classList.remove('light');
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('light');
    }
  };

  // 監聽主題變更以確保 DOM 同步 (處理初始化情況)
  // useLayoutEffect 確保在瀏覽器繪製前套用 class，避免閃爍
  useLayoutEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.remove('light');
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('light');
    }
  }, [theme]);

  // 載入模型列表
  useModels({
    setAvailableModels,
    setAvailableAiModels,
    setModelLoading,
    setWhisperModel,
    setAiModel,
    setOllamaStatus
  });

  return {
    // 基本狀態
    theme,
    setTheme,
    toggleTheme,
    activeTab,
    setActiveTab: setActiveTabSafe,
    userId,

    // 文件和處理狀態
    files,
    setFiles,
    processing,
    setProcessing,
    uploading,
    setUploading,
    uploadProgress,
    setUploadProgress,
    uploadSpeed,
    setUploadSpeed,
    result,
    setResult,
    error,
    setError,
    currentTaskId,
    setCurrentTaskId,
    taskProgress,
    setTaskProgress,

    // 處理設置
    processingMode,
    setProcessingMode,
    whisperModel,
    setWhisperModel,
    aiModel,
    setAiModel,
    enableLLMProcessing,
    setEnableLLMProcessing,
    availableModels,
    setAvailableModels,
    availableAiModels,
    setAvailableAiModels,
    modelLoading,
    setModelLoading,
    ollamaStatus,
    setOllamaStatus,

    // 自定義模式狀態
    customModePrompt,
    setCustomModePrompt,
    customDetailPrompt,
    setCustomDetailPrompt,
    showCustomModal,
    setShowCustomModal,
    customModalType,
    setCustomModalType,

    // 標籤狀態
    selectedTags,
    setSelectedTags,
    customTagPrompt,
    setCustomTagPrompt,

    // Email 通知設定
    emailEnabled,
    setEmailEnabled,
    emailAddress,
    setEmailAddress,

    // 文字處理設定
    textInput,
    setTextInput,
    enableCleanFiller,
    setEnableCleanFiller,
    sourceType,
    setSourceType,

    // 系統配置
    systemConfig,
    emailFeatureEnabled,

    // 管理員權限
    adminPassword,
    setAdminPassword,
  };
};
