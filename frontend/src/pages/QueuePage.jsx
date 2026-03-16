/**
 * 隊列管理頁面 - 任務狀態監控和管理
 */
import React, { useState, useEffect } from 'react';
import { Clock, CheckCircle, AlertCircle, XCircle, Loader2, Users, Activity, List, Play } from 'lucide-react';
import apiService from '../services/api';
import axios from 'axios';

// 🔧 修復：動態 API 基礎 URL - 支持 LAN 訪問和 Cloudflare Tunnel
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

// 錯誤邊界組件 - 🔧 修復：使用 React 狀態重置代替頁面刷新
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // 錯誤已被捕獲
  }

  // 🔧 修復：優雅重置狀態，不刷新整個頁面
  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  }

  render() {
    if (this.state.hasError) {
      // 🔧 修復：從 props 獲取 theme，而非全局變量
      const theme = this.props.theme || 'dark';
      return (
        <div className="glass-panel p-8 flex flex-col items-center justify-center text-center">
          <div className="p-4 rounded-full bg-red-500/10 text-red-400 mb-4">
            <AlertCircle size={48} />
          </div>
          <h3 className={`text-xl font-semibold mb-2 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>頁面載入錯誤</h3>
          <p className={`mb-6 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>{this.state.error?.message || '發生未知錯誤'}</p>
          <button
            onClick={this.handleRetry}
            className="glass-button px-6 py-2"
          >
            重試
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

// 🔧 修復：使用 useReducer 進行原子批量更新，防止閃爍和統計顯示問題
const queueReducer = (state, action) => {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload, loading: false };
    case 'SET_SHOW_OTHER_TASKS':
      return { ...state, showOtherTasks: action.payload };
    case 'UPDATE_ALL':
      // 🔧 關鍵：所有狀態在單次更新中同步變更，防止統計數據不顯示和閃爍
      return {
        ...state,
        userTasks: action.payload.userTasks,
        otherTasks: action.payload.otherTasks,
        currentProcessing: action.payload.currentProcessing,
        queuePositionInfo: action.payload.queuePositionInfo,
        queueStatus: action.payload.queueStatus,
        taskCache: action.payload.taskCache,
        loading: false,
        error: null
      };
    default:
      return state;
  }
};

const QueuePage = ({ userId, theme }) => {
  // 🔧 修復：使用 useReducer 替代多個 useState，實現原子批量更新
  const [state, dispatch] = React.useReducer(queueReducer, {
    userTasks: [],
    otherTasks: [],
    queueStatus: null,
    currentProcessing: null,
    queuePositionInfo: [],
    loading: true,
    refreshInterval: null,
    error: null,
    showOtherTasks: true,
    taskCache: new Map()
  });

  const { userTasks, otherTasks, queueStatus, currentProcessing, queuePositionInfo, loading, error, showOtherTasks, taskCache } = state;

  // 🔧 修復：使用 useRef 追蹤是否正在加載，防止並發請求
  const isLoadingRef = React.useRef(false);
  const loadingTimeoutRef = React.useRef(null);

  useEffect(() => {
    if (!userId) {
      dispatch({ type: 'SET_LOADING', payload: false });
      return;
    }

    loadGlobalStatus();

    // 設置自動刷新
    const interval = setInterval(() => {
      loadGlobalStatus();
    }, 3000);

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [userId]);

  const loadGlobalStatus = async () => {
    if (!userId) {
      dispatch({ type: 'SET_LOADING', payload: false });
      return;
    }

    // 防止並發請求
    if (isLoadingRef.current) {
      return;
    }

    isLoadingRef.current = true;

    // 🔧 修復：清除之前的超時
    if (loadingTimeoutRef.current) {
      clearTimeout(loadingTimeoutRef.current);
    }

    try {
      const response = await axios.get(`${API_BASE_URL}/task/global/status?user_id=${userId}`);

      // 🔧 修復：使用持久化緩存確保任務不會閃爍消失
      const allUserTasks = response.data.user_tasks || [];

      // 🔧 關鍵修復：在本地變量中處理所有數據，最後一次性更新狀態
      const newCache = new Map(taskCache);
      const now = Date.now();

      // 添加/更新所有收到的任務，保留舊的進度數據以防止閃爍
      allUserTasks.forEach(task => {
        const taskId = task.task_id || task.id;
        if (taskId) {
          const existingTask = newCache.get(taskId);

          // 智能合併策略
          const mergedTask = {
            ...existingTask, // 保留舊數據
            ...task, // 用新數據覆蓋
            // 智能進度合併：只在新數據有進度或狀態改變時更新
            progress: task.progress ||
              (existingTask?.status === task.status ? existingTask?.progress : null) ||
              null,
            lastSeen: now,
            lastUpdate: task.progress ? now : (existingTask?.lastUpdate || now)
          };

          newCache.set(taskId, mergedTask);
        }
      });

      // 清理超過30秒沒更新的已完成任務（增加延遲防止過早清除）
      for (const [taskId, cachedTask] of newCache.entries()) {
        const age = now - cachedTask.lastSeen;
        const isCompleted = cachedTask.status === 'completed' || cachedTask.status === 'failed' || cachedTask.status === 'cancelled';
        // 增加清理時間到30秒，讓用戶有足夠時間看到完成狀態
        if (isCompleted && age > 30000) {
          newCache.delete(taskId);
        }
      }

      // 從更新後的緩存中獲取所有任務
      const cachedTasks = Array.from(newCache.values());

      // 先分組：活躍任務 vs 已完成任務
      const activeTasks = cachedTasks.filter(t =>
        t.status === 'pending' || t.status === 'queued' || t.status === 'processing' || t.status === 'running'
      );

      const completedTasks = cachedTasks.filter(t =>
        t.status === 'completed' || t.status === 'failed' || t.status === 'cancelled'
      );

      // 按時間排序完成的任務，取最新的3個（增加顯示數量）
      const sortedCompleted = completedTasks.sort((a, b) => {
        const timeA = new Date(b.completed_at || b.created_at || 0);
        const timeB = new Date(a.completed_at || a.created_at || 0);
        return timeA - timeB;
      });

      // 組合：所有活躍任務 + 最多3個最近完成的任務（增加可見性）
      const filteredTasks = [
        ...activeTasks,
        ...(sortedCompleted.length > 0 ? sortedCompleted.slice(0, 3) : [])
      ];

      // 按時間排序最終列表（最新的在前）
      filteredTasks.sort((a, b) => {
        // Processing/running tasks always on top
        const aIsActive = a.status === 'processing' || a.status === 'running';
        const bIsActive = b.status === 'processing' || b.status === 'running';

        if (aIsActive && !bIsActive) return -1;
        if (bIsActive && !aIsActive) return 1;

        // Then pending/queued tasks
        const aIsPending = a.status === 'pending' || a.status === 'queued';
        const bIsPending = b.status === 'pending' || b.status === 'queued';

        if (aIsPending && !bIsPending) return -1;
        if (bIsPending && !aIsPending) return 1;

        // Finally by time (most recent first)
        const timeA = new Date(b.started_at || b.created_at || 0);
        const timeB = new Date(a.started_at || a.created_at || 0);
        return timeA - timeB;
      });

      // 一次性更新所有狀態，防止閃爍和統計數據不顯示
      dispatch({
        type: 'UPDATE_ALL',
        payload: {
          userTasks: filteredTasks,
          otherTasks: response.data.other_tasks || [],
          currentProcessing: response.data.current_processing || null,
          queuePositionInfo: response.data.queue_position_info || [],
          queueStatus: response.data.queue_stats || {
            total_tasks: 0,
            active_tasks: 0,
            pending_tasks: 0,
            completed_tasks: 0,
            failed_tasks: 0
          },
          taskCache: newCache
        }
      });

    } catch (error) {
      // 降級處理：嘗試載入用戶任務
      try {
        const userResponse = await axios.get(`${API_BASE_URL}/task/user/${userId}/tasks?user_id=${userId}`);
        let tasks = [];
        if (Array.isArray(userResponse.data)) {
          tasks = userResponse.data;
        } else if (userResponse.data.tasks) {
          tasks = userResponse.data.tasks;
        }

        // 嘗試載入基本隊列狀態
        const statusResponse = await axios.get(`${API_BASE_URL}/task/queue/status?user_id=${userId}`);

        // 🔧 修復：降級處理也使用批量更新
        dispatch({
          type: 'UPDATE_ALL',
          payload: {
            userTasks: tasks,
            otherTasks: [],
            currentProcessing: null,
            queuePositionInfo: [],
            queueStatus: statusResponse.data || {
              total_tasks: 0,
              active_tasks: 0,
              pending_tasks: 0,
              completed_tasks: 0,
              failed_tasks: 0
            },
            taskCache: taskCache
          }
        });
      } catch (fallbackError) {
        dispatch({
          type: 'SET_ERROR',
          payload: `Failed to load tasks: ${error.message}`
        });
      }
    } finally {
      // 🔧 修復：重置加載標記
      isLoadingRef.current = false;
    }
  };

  const handleCancelTask = async (taskId) => {
    try {
      await apiService.cancelTask(taskId, userId);
      loadGlobalStatus(); // 刷新任務列表
    } catch (error) {
      alert('Failed to cancel task');
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending':
      case 'queued':
        return <Clock className="text-amber-400" size={18} />;
      case 'processing':
      case 'running':
        return <Loader2 className="text-blue-400 animate-spin" size={18} />;
      case 'completed':
        return <CheckCircle className="text-emerald-400" size={18} />;
      case 'failed':
      case 'error':
        return <XCircle className="text-red-400" size={18} />;
      case 'cancelled':
        return <XCircle className="text-slate-300" size={18} />;
      default:
        return <AlertCircle className="text-slate-300" size={18} />;
    }
  };

  const getStatusText = (status) => {
    const statusMap = {
      'pending': '等待中',
      'queued': '排隊中',
      'processing': '處理中',
      'running': '執行中',
      'completed': '已完成',
      'failed': '失敗',
      'error': '錯誤',
      'cancelled': '已取消'
    };
    return statusMap[status] || status;
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending':
      case 'queued':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'processing':
      case 'running':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      case 'completed':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'failed':
      case 'error':
        return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'cancelled':
        return 'bg-slate-500/10 text-slate-300 border-slate-500/20';
      default:
        return 'bg-slate-500/10 text-slate-300 border-slate-500/20';
    }
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return '-';
    if (typeof timestamp === 'object') {
      if (timestamp.toISOString) {
        timestamp = timestamp.toISOString();
      } else {
        return '-';
      }
    }
    try {
      return new Date(timestamp).toLocaleString();
    } catch (error) {
      return '-';
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '-';
    if (typeof seconds === 'object') return '-';
    try {
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return `${mins}:${secs.toString().padStart(2, '0')}`;
    } catch (error) {
      return '-';
    }
  };

  return (
    <ErrorBoundary>
      <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        {/* Header Section */}
        <div className={`glass-panel p-4 mt-4 mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 ${theme === 'dark' ? '' : 'border-slate-300'
          }`}>
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-xl text-brand-primary ${theme === 'dark' ? 'bg-brand-primary/20' : 'bg-brand-primary/15 border border-brand-primary/30'
              }`}>
              <List size={26} />
            </div>
            <div>
              <h2 className={`text-xl font-display font-bold ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>任務隊列</h2>
              <p className={`text-sm mt-1 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>監控與管理您的處理任務</p>
            </div>
          </div>

          {queueStatus && (
            <div className="flex flex-wrap gap-3 text-sm">
              <div className={`px-4 py-2 rounded-lg flex flex-col items-center min-w-[75px] ${theme === 'dark' ? 'bg-white/5 border border-white/10' : 'bg-slate-100 border-2 border-slate-300'
                }`}>
                <span className={`text-xs uppercase tracking-wider ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>總計</span>
                <span className={`font-bold text-base ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>{queueStatus.total_tasks || 0}</span>
              </div>
              <div className={`px-4 py-2 rounded-lg flex flex-col items-center min-w-[75px] ${theme === 'dark'
                ? 'bg-blue-500/10 border border-blue-500/20'
                : 'bg-blue-50 border-2 border-blue-400'
                }`}>
                <span className={`text-xs uppercase tracking-wider ${theme === 'dark' ? 'text-blue-400/70' : 'text-blue-600/70'
                  }`}>進行中</span>
                <span className={`font-bold text-base ${theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
                  }`}>{queueStatus.active_tasks || 0}</span>
              </div>
              <div className={`px-4 py-2 rounded-lg flex flex-col items-center min-w-[75px] ${theme === 'dark'
                ? 'bg-amber-500/10 border border-amber-500/20'
                : 'bg-amber-50 border-2 border-amber-400'
                }`}>
                <span className={`text-xs uppercase tracking-wider ${theme === 'dark' ? 'text-amber-400/70' : 'text-amber-600/70'
                  }`}>等待中</span>
                <span className={`font-bold text-base ${theme === 'dark' ? 'text-amber-400' : 'text-amber-600'
                  }`}>{queueStatus.pending_tasks || 0}</span>
              </div>
            </div>
          )}
        </div>

        {/* Content Area */}
        {loading ? (
          <div className={`glass-panel p-12 mt-6 mb-6 flex flex-col items-center justify-center ${theme === 'dark' ? '' : 'border-slate-300'
            }`}>
            <Loader2 className="text-brand-primary animate-spin mb-4" size={32} />
            <p className={theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}>載入任務中...</p>
          </div>
        ) : error ? (
          <div className={`glass-panel p-8 mt-6 mb-6 flex flex-col items-center justify-center text-center ${theme === 'dark'
            ? 'border-red-500/30 bg-red-500/5'
            : 'border-2 border-red-400 bg-red-50'
            }`}>
            <div className={`p-4 rounded-full mb-4 ${theme === 'dark' ? 'bg-red-500/10 text-red-400' : 'bg-red-100 text-red-600'
              }`}>
              <AlertCircle size={48} />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">載入任務失敗</h3>
            <p className="text-slate-300 mb-6">{error}</p>
            <button
              onClick={() => {
                dispatch({ type: 'SET_ERROR', payload: null });
                dispatch({ type: 'SET_LOADING', payload: true });
                loadGlobalStatus();
              }}
              className="glass-button px-6 py-2"
            >
              重試
            </button>
          </div>
        ) : !userId ? (
          <div className={`glass-panel p-12 mt-6 mb-6 flex flex-col items-center justify-center text-center ${theme === 'dark' ? '' : 'border-slate-300'
            }`}>
            <Users size={48} className={`mb-4 ${theme === 'dark' ? 'text-slate-600' : 'text-slate-500'
              }`} />
            <p className={`text-lg mb-2 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              }`}>找不到使用者身分</p>
            <p className={theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}>請重新整理頁面以初始化使用者工作階段。</p>
          </div>
        ) : (
          <>
            {/* Two Column Layout: My Tasks | System Queue Status */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6 mb-4">

              {/* Left Column: My Tasks Section */}
              <div className={`glass-panel p-4 ${theme === 'dark' ? '' : 'border-slate-300'}`}>
                <h3 className={`text-base font-semibold mb-4 flex items-center gap-2 ${theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>
                  <Users className="text-brand-primary" size={20} />
                  我的任務
                  {userTasks && userTasks.length > 0 && (
                    <span className="ml-auto px-2 py-1 rounded-full text-xs font-semibold bg-brand-primary/20 text-brand-primary border border-brand-primary/30">
                      {userTasks.length}
                    </span>
                  )}
                </h3>

                {!userTasks || userTasks.length === 0 ? (
                  <div className={`text-center py-12 border-2 border-dashed rounded-xl ${theme === 'dark'
                    ? 'border-white/5 bg-white/5'
                    : 'border-slate-300 bg-slate-50'
                    }`}>
                    <List size={48} className={`mx-auto mb-4 ${theme === 'dark' ? 'text-slate-600' : 'text-slate-400'
                      }`} />
                    <p className={`font-medium mb-1 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                      }`}>目前無進行中任務</p>
                    <p className={`text-sm ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                      }`}>
                      前往 <span className="text-brand-primary">上傳</span> 或 <span className="text-brand-primary">文字處理</span> 以開始新任務。
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {userTasks.map((task, index) => {
                      const safeTask = {
                        ...task,
                        processing_mode: task.processing_mode ? String(task.processing_mode) : '',
                        whisper_model: task.whisper_model ? String(task.whisper_model) : '',
                        file_name: task.file_name ? String(task.file_name) : (task.filename ? String(task.filename) : ''),
                        status: task.status ? String(task.status) : 'unknown'
                      };

                      return (
                        <div key={task.task_id || task.id || index} className={`queue-task-card status-${safeTask.status} p-4 relative group mt-2 mb-2`}>
                          <div className="flex flex-col sm:flex-row items-start justify-between gap-3">
                            <div className="flex items-start gap-3 w-full">
                              <div className={`task-status-icon ${safeTask.status} shrink-0`}>
                                {getStatusIcon(safeTask.status)}
                              </div>

                              <div className="flex-1 min-w-0">
                                <h4 className={`font-medium text-base mb-1 truncate pr-2 ${theme === 'dark' ? 'text-white' : 'text-slate-900'
                                  }`}>
                                  {safeTask.type === 'upload' ? '檔案處理' : '文字處理'}
                                  {safeTask.file_name && <span className={`mx-2 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-500'}`}>-</span>}
                                  {safeTask.file_name}
                                </h4>

                                <div className="flex flex-wrap gap-1.5 mb-2">
                                  {safeTask.processing_mode && (
                                    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${theme === 'dark'
                                      ? 'bg-white/10 text-slate-300 border border-white/10'
                                      : 'bg-slate-100 text-slate-700 border border-slate-300'
                                      }`}>
                                      {safeTask.processing_mode}
                                    </span>
                                  )}
                                  {safeTask.whisper_model && (
                                    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${theme === 'dark'
                                      ? 'bg-white/10 text-slate-300 border border-white/10'
                                      : 'bg-slate-100 text-slate-700 border border-slate-300'
                                      }`}>
                                      {safeTask.whisper_model}
                                    </span>
                                  )}
                                </div>

                                <div className={`grid grid-cols-2 sm:grid-cols-4 gap-x-3 sm:gap-x-6 gap-y-1 text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                                  }`}>
                                  <div>
                                    <span className={`block mb-0.5 ${theme === 'dark' ? 'text-slate-600' : 'text-slate-500'
                                      }`}>建立時間</span>
                                    {formatTime(task.created_at)}
                                  </div>
                                  {task.started_at && (
                                    <div>
                                      <span className={`block mb-0.5 ${theme === 'dark' ? 'text-slate-600' : 'text-slate-500'
                                        }`}>開始時間</span>
                                      {formatTime(task.started_at)}
                                    </div>
                                  )}
                                  {task.completed_at && (
                                    <div>
                                      <span className={`block mb-0.5 ${theme === 'dark' ? 'text-slate-600' : 'text-slate-500'
                                        }`}>完成時間</span>
                                      {formatTime(task.completed_at)}
                                    </div>
                                  )}
                                  {task.duration && (
                                    <div>
                                      <span className="block text-slate-600 mb-0.5">耗時</span>
                                      {formatDuration(task.duration)}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>

                            <div className="flex flex-row items-center gap-2 shrink-0">
                              <span className={`status-badge ${safeTask.status}`}>
                                {getStatusText(safeTask.status)}
                              </span>

                              {(safeTask.status === 'pending' || safeTask.status === 'queued' || safeTask.status === 'processing') && (
                                <button
                                  className="p-1.5 rounded-lg text-slate-300 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                                  onClick={() => handleCancelTask(task.task_id || task.id)}
                                  title="取消任務"
                                >
                                  <XCircle size={16} />
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Progress Bar - Show for all active states */}
                          {task.progress && (safeTask.status === 'processing' || safeTask.status === 'running' || safeTask.status === 'queued' || safeTask.status === 'pending') && (
                            <div className={`mt-3 pt-3 border-t ${theme === 'dark' ? 'border-white/10' : 'border-slate-300'
                              }`}>
                              <div className="flex justify-between text-xs mb-2">
                                <span className={`font-semibold ${theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
                                  }`}>{task.progress.stage || task.progress.current_step || '處理中...'}</span>
                                <span className={`font-medium ${theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                                  }`}>{task.progress.percentage || 0}%</span>
                              </div>
                              <div className="task-progress-bar">
                                <div
                                  className="task-progress-fill"
                                  style={{ width: `${task.progress.percentage || 0}%` }}
                                />
                              </div>
                              {/* Additional progress details if available */}
                              {task.progress.current_step && task.progress.total_steps && (
                                <div className={`text-xs mt-1 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                                  }`}>
                                  步驟 {task.progress.current_step} / {task.progress.total_steps}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Error Message */}
                          {task.error && (
                            <div className="mt-3 p-2 rounded-lg bg-red-500/10 border border-red-500/20 flex items-start gap-2 text-xs text-red-300">
                              <AlertCircle size={14} className="mt-0.5 shrink-0" />
                              <span>{typeof task.error === 'object' ? JSON.stringify(task.error) : task.error}</span>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Right Column: System Queue Status Section */}
              <div className={`glass-panel p-4 ${theme === 'dark' ? '' : 'border-slate-300'}`}>
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className={`text-base font-semibold flex items-center gap-2 ${theme === 'dark' ? 'text-white' : 'text-slate-900'
                      }`}>
                      <Activity className="text-brand-secondary" size={20} />
                      系統隊列狀態
                    </h3>
                    <p className={`text-xs mt-1 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'
                      }`}>
                      {currentProcessing ? '目前正在處理 1 個任務' : '系統閒置'}
                      {queuePositionInfo && queuePositionInfo.length > 0 &&
                        ` • ${queuePositionInfo.length} 個任務在隊列中`
                      }
                    </p>
                  </div>
                  <button
                    onClick={() => dispatch({ type: 'SET_SHOW_OTHER_TASKS', payload: !showOtherTasks })}
                    className={`glass-button-secondary px-4 py-2 text-xs ${theme === 'dark' ? 'text-gray-300 hover:text-white' : 'text-gray-700 hover:text-black font-medium'}`}
                  >
                    {showOtherTasks ? '隱藏' : '顯示'} 系統狀態
                  </button>
                </div>

                {showOtherTasks && (
                  <div className="space-y-8 mt-6">
                    {/* Currently Processing Task */}
                    {currentProcessing && (
                      <div>
                        <h4 className={`text-sm font-semibold mb-4 uppercase tracking-wider ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'
                          }`}>
                          目前處理中
                        </h4>
                        <div className={`queue-task-card status-processing p-4 mt-2 mb-3 ${currentProcessing.is_own_task ? 'border-l-emerald-500' : 'border-l-blue-500'}`}>
                          <div className="flex items-start gap-3">
                            <div className="task-status-icon processing">
                              <Loader2 size={18} className="animate-spin" />
                            </div>
                            <div className="flex-1">
                              <div className="flex justify-between items-start">
                                <div>
                                  <h4 className={`font-medium text-base mb-1 ${theme === 'dark' ? 'text-white' : 'text-slate-900'
                                    }`}>
                                    {currentProcessing.type === 'upload' ? '檔案處理' : '文字處理'}
                                    {currentProcessing.file_name && <span className={`mx-2 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-500'}`}>-</span>}
                                    {currentProcessing.file_name}
                                  </h4>
                                  <div className={`flex items-center gap-2 text-xs mb-2 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                                    }`}>
                                    {currentProcessing.processing_mode && <span>{currentProcessing.processing_mode}</span>}
                                    <span className={`font-medium ${currentProcessing.is_own_task
                                      ? theme === 'dark' ? 'text-emerald-400' : 'text-emerald-600'
                                      : theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
                                      }`}>
                                      [{currentProcessing.is_own_task ? '您的' : '其他'}]
                                    </span>
                                  </div>
                                </div>
                                <span className="status-badge processing">
                                  處理中
                                </span>
                              </div>

                              {currentProcessing.progress && (
                                <div className="space-y-2 mt-3">
                                  <div className="flex justify-between text-xs">
                                    <span className={`font-semibold ${theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
                                      }`}>{currentProcessing.progress.stage || currentProcessing.progress.current_step || '處理中...'}</span>
                                    <span className={`font-medium ${theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                                      }`}>{currentProcessing.progress.percentage || 0}%</span>
                                  </div>
                                  <div className="task-progress-bar">
                                    <div
                                      className="task-progress-fill"
                                      style={{ width: `${currentProcessing.progress.percentage || 0}%` }}
                                    />
                                  </div>
                                  {/* Additional progress details if available */}
                                  {currentProcessing.progress.current_step && currentProcessing.progress.total_steps && (
                                    <div className={`text-xs mt-1 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                                      }`}>
                                      步驟 {currentProcessing.progress.current_step} / {currentProcessing.progress.total_steps}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Queue Position Info */}
                    {queuePositionInfo && queuePositionInfo.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-slate-300 mb-4 uppercase tracking-wider">
                          隊列進度
                        </h4>
                        <div className="glass-card p-4 mt-2 mb-3 text-center">
                          {(() => {
                            const userTasksInQueue = queuePositionInfo.filter(task => task.is_own_task);
                            const totalTasksAhead = queuePositionInfo.filter(task =>
                              !task.is_own_task && userTasksInQueue.length > 0 &&
                              task.position < Math.min(...userTasksInQueue.map(t => t.position))
                            );

                            if (userTasksInQueue.length > 0) {
                              const nextUserTaskPosition = Math.min(...userTasksInQueue.map(t => t.position));
                              const tasksAheadCount = totalTasksAhead.length;

                              return (
                                <div>
                                  <div className="text-2xl font-bold text-emerald-400 mb-2">
                                    您的任務排在第 #{nextUserTaskPosition} 位
                                  </div>
                                  <p className="text-slate-300">
                                    {tasksAheadCount > 0
                                      ? `${tasksAheadCount} 個任務在您前面`
                                      : '您的任務即將開始！'
                                    }
                                  </p>
                                </div>
                              );
                            } else {
                              return (
                                <div>
                                  <div className="text-lg text-slate-300">
                                    {queuePositionInfo.length} 個任務在隊列中等待
                                  </div>
                                </div>
                              );
                            }
                          })()}
                        </div>
                      </div>
                    )}

                    {/* Empty State for System Queue */}
                    {!currentProcessing && (!queuePositionInfo || queuePositionInfo.length === 0) && (
                      <div className="text-center py-8 border border-dashed border-white/5 rounded-xl bg-white/5">
                        <p className="text-slate-300 font-medium">系統閒置</p>
                        <p className="text-slate-400 text-sm mt-1">
                          目前沒有其他任務正在處理。
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </ErrorBoundary>
  );
};

export default QueuePage;
