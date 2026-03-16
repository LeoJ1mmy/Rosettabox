/**
 * 優化版隊列管理頁面 - 實現局部更新，避免整體重載
 */
import React, { useState, useEffect, useCallback, useRef, memo } from 'react';
import { Clock, CheckCircle, AlertCircle, XCircle, Loader2, Users } from 'lucide-react';
import apiService from '../services/api';
import axios from 'axios';

// 任務項目組件 - 使用 memo 優化，只在數據真正改變時重新渲染
const TaskItem = memo(({ task, onCancel, isOwnTask, theme }) => {
  const getStatusIcon = useCallback((status) => {
    switch (status) {
      case 'pending':
      case 'queued':
        return <Clock className="status-icon pending" size={16} />;
      case 'processing':
      case 'running':
        return <Loader2 className="status-icon processing spinning" size={16} />;
      case 'completed':
        return <CheckCircle className="status-icon completed" size={16} />;
      case 'failed':
      case 'error':
        return <XCircle className="status-icon failed" size={16} />;
      default:
        return <AlertCircle className="status-icon unknown" size={16} />;
    }
  }, []);

  const getStatusText = useCallback((status) => {
    const statusMap = {
      'pending': '等待中',
      'queued': '已排隊',
      'processing': '處理中',
      'running': '執行中',
      'completed': '已完成',
      'failed': '失敗',
      'error': '錯誤'
    };
    return statusMap[status] || status;
  }, []);

  const formatTime = useCallback((timestamp) => {
    if (!timestamp) return '-';
    if (typeof timestamp === 'object') {
      if (timestamp.toISOString) {
        timestamp = timestamp.toISOString();
      } else {
        return '-';
      }
    }
    try {
      return new Date(timestamp).toLocaleString('zh-TW');
    } catch (error) {
      return '-';
    }
  }, []);

  return (
    <li className="task-item">
      <div className="task-content">
        <div className="task-info">
          <div className="task-status">
            {getStatusIcon(task.status)}
            <span className={`status-text ${task.status}`}>
              {getStatusText(task.status)}
            </span>
          </div>
          <div className="task-details">
            <span className="task-filename">
              {isOwnTask ? task.filename : '***私密文件***'}
            </span>
            <span className="task-time">
              {formatTime(task.created_at)}
            </span>
            {task.progress > 0 && task.progress < 100 && (
              <span className="task-progress">{task.progress}%</span>
            )}
            {isOwnTask && task.status === 'completed' && (
              <span className="task-completed-hint" style={{ fontSize: '0.75rem', color: '#10b981', marginLeft: '8px' }}>
                ✓ 完成！結果已顯示在主頁面
              </span>
            )}
          </div>
        </div>
        {isOwnTask && (task.status === 'pending' || task.status === 'processing') && (
          <button
            className="cancel-btn"
            onClick={() => onCancel(task.id)}
            title="取消任務"
          >
            取消
          </button>
        )}
      </div>
    </li>
  );
}, (prevProps, nextProps) => {
  // 自定義比較函數，只在關鍵數據改變時重新渲染
  return (
    prevProps.task.id === nextProps.task.id &&
    prevProps.task.status === nextProps.task.status &&
    prevProps.task.progress === nextProps.task.progress &&
    prevProps.isOwnTask === nextProps.isOwnTask &&
    prevProps.theme === nextProps.theme
  );
});

// 隊列統計組件 - 使用 memo 優化
const QueueStats = memo(({ stats, theme }) => {
  if (!stats) return null;
  
  return (
    <div className="queue-stats">
      <div className="stat-item">
        <span className="stat-label">總任務</span>
        <span className="stat-value">{stats.total_tasks || 0}</span>
      </div>
      <div className="stat-item">
        <span className="stat-label">處理中</span>
        <span className="stat-value">{stats.active_tasks || 0}</span>
      </div>
      <div className="stat-item">
        <span className="stat-label">等待中</span>
        <span className="stat-value">{stats.pending_tasks || 0}</span>
      </div>
    </div>
  );
});

const OptimizedQueuePage = ({ userId, theme }) => {
  const [userTasks, setUserTasks] = useState([]);
  const [otherTasks, setOtherTasks] = useState([]);
  const [queueStatus, setQueueStatus] = useState(null);
  const [currentProcessing, setCurrentProcessing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showOtherTasks, setShowOtherTasks] = useState(true);
  // 🔧 新增：任務持久化緩存
  const [taskCache, setTaskCache] = useState(new Map());

  // 使用 useRef 存儲上一次的數據，用於比較
  const previousDataRef = useRef({
    userTasks: [],
    otherTasks: [],
    queueStatus: null,
    currentProcessing: null
  });

  // 使用 useRef 存儲計時器
  const intervalRef = useRef(null);
  
  // 智能比較函數，判斷數據是否真的改變
  const hasDataChanged = useCallback((newData) => {
    const prev = previousDataRef.current;
    
    // 比較用戶任務
    if (newData.userTasks?.length !== prev.userTasks?.length) return true;
    
    // 比較任務狀態和進度
    for (let i = 0; i < newData.userTasks?.length; i++) {
      const newTask = newData.userTasks[i];
      const prevTask = prev.userTasks.find(t => t.id === newTask.id);
      if (!prevTask || 
          prevTask.status !== newTask.status || 
          prevTask.progress !== newTask.progress) {
        return true;
      }
    }
    
    // 比較其他任務數量
    if (newData.otherTasks?.length !== prev.otherTasks?.length) return true;
    
    // 比較隊列狀態
    if (JSON.stringify(newData.queueStatus) !== JSON.stringify(prev.queueStatus)) return true;
    
    // 比較當前處理任務
    if (newData.currentProcessing?.id !== prev.currentProcessing?.id) return true;
    
    return false;
  }, []);
  
  // 優化的數據加載函數 - 只更新改變的部分
  const loadGlobalStatus = useCallback(async () => {
    if (!userId) {
      setLoading(false);
      return;
    }

    try {
      const response = await axios.get(`/api/task/global/status?user_id=${userId}`);

      // 🔧 修復：使用持久化緩存確保任務不會閃爍消失
      const allUserTasks = response.data.user_tasks || [];

      // 更新任務緩存
      const updatedCache = new Map(taskCache);
      const now = Date.now();

      allUserTasks.forEach(task => {
        const taskId = task.task_id || task.id;
        if (taskId) {
          updatedCache.set(taskId, {
            ...task,
            lastSeen: now
          });
        }
      });

      // 清理超過10秒沒更新的已完成任務
      for (const [taskId, cachedTask] of updatedCache.entries()) {
        const age = now - cachedTask.lastSeen;
        const isCompleted = cachedTask.status === 'completed' || cachedTask.status === 'failed';
        if (isCompleted && age > 10000) {
          updatedCache.delete(taskId);
        }
      }

      setTaskCache(updatedCache);

      // 從緩存中獲取所有任務
      const cachedTasks = Array.from(updatedCache.values());

      // 先分組：活躍任務 vs 已完成任務
      const activeTasks = cachedTasks.filter(t =>
        t.status === 'pending' || t.status === 'queued' || t.status === 'processing' || t.status === 'running'
      );

      const completedTasks = cachedTasks.filter(t =>
        t.status === 'completed' || t.status === 'failed'
      );

      // 按時間排序完成的任務，取最新的1個
      const sortedCompleted = completedTasks.sort((a, b) => {
        const timeA = new Date(b.completed_at || b.created_at || 0);
        const timeB = new Date(a.completed_at || a.created_at || 0);
        return timeA - timeB;
      });

      // 組合：所有活躍任務 + 最多1個最近完成的任務
      const filteredTasks = [
        ...activeTasks,
        ...(sortedCompleted.length > 0 ? [sortedCompleted[0]] : [])
      ];

      // 按時間排序最終列表（最新的在前）
      filteredTasks.sort((a, b) => {
        // Processing tasks always on top
        if (a.status === 'processing' && b.status !== 'processing') return -1;
        if (b.status === 'processing' && a.status !== 'processing') return 1;

        // Then by time
        const timeA = new Date(b.started_at || b.created_at || 0);
        const timeB = new Date(a.started_at || a.created_at || 0);
        return timeA - timeB;
      });

      const newData = {
        userTasks: filteredTasks,
        otherTasks: response.data.other_tasks || [],
        queueStatus: response.data.queue_stats || {
          total_tasks: 0,
          active_tasks: 0,
          pending_tasks: 0,
          completed_tasks: 0,
          failed_tasks: 0
        },
        currentProcessing: response.data.current_processing || null
      };
      
      // 只在數據真正改變時更新狀態
      if (hasDataChanged(newData)) {
        // 使用函數式更新，避免不必要的重渲染
        setUserTasks(prev => {
          if (JSON.stringify(prev) !== JSON.stringify(newData.userTasks)) {
            return newData.userTasks;
          }
          return prev;
        });
        
        setOtherTasks(prev => {
          if (JSON.stringify(prev) !== JSON.stringify(newData.otherTasks)) {
            return newData.otherTasks;
          }
          return prev;
        });
        
        setQueueStatus(prev => {
          if (JSON.stringify(prev) !== JSON.stringify(newData.queueStatus)) {
            return newData.queueStatus;
          }
          return prev;
        });
        
        setCurrentProcessing(prev => {
          if (prev?.id !== newData.currentProcessing?.id) {
            return newData.currentProcessing;
          }
          return prev;
        });
        
        // 更新參考數據
        previousDataRef.current = newData;
      }
      
    } catch (error) {
      // 錯誤處理保持簡單，避免頻繁重試
    } finally {
      setLoading(false);
    }
  }, [userId, hasDataChanged]);
  
  // 🔧 修復：使用 useRef 追蹤活動任務狀態，避免 useEffect 循環依賴
  const hasActiveTasksRef = useRef(false);

  // 🔧 修復：單獨的 effect 來更新活動任務狀態（不觸發重新初始化）
  useEffect(() => {
    hasActiveTasksRef.current = userTasks.some(t =>
      t.status === 'processing' || t.status === 'pending'
    );
  }, [userTasks]);

  // 初始化和清理 - 🔧 修復：移除 userTasks 依賴，避免循環刷新
  useEffect(() => {
    if (!userId) {
      setLoading(false);
      return;
    }

    // 初始加載
    loadGlobalStatus();

    // 🔧 修復：使用固定間隔 + 動態檢查，而非重建 interval
    // 基礎刷新頻率：5秒
    const baseInterval = 5000;

    intervalRef.current = setInterval(() => {
      loadGlobalStatus();
    }, baseInterval);

    // 清理函數
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [userId, loadGlobalStatus]);  // 🔧 修復：移除 userTasks 依賴
  
  // 取消任務處理
  const handleCancelTask = useCallback(async (taskId) => {
    try {
      await apiService.cancelTask(taskId, userId);
      // 只更新受影響的任務，不重載整個列表
      setUserTasks(prev => prev.filter(t => t.id !== taskId));
    } catch (error) {
      alert('取消任務失敗');
    }
  }, [userId]);
  
  // 渲染優化 - 避免不必要的 DOM 操作
  if (!userId) {
    return (
      <div className="empty-state">
        <AlertCircle size={48} />
        <p>請先設置用戶 ID</p>
        <p className="empty-hint">需要用戶 ID 才能查看任務狀態</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="loading-state">
        <Loader2 className="spinning" size={48} />
        <p>載入中...</p>
      </div>
    );
  }

  return (
    <div className="queue-page">
      {/* 隊列統計 */}
      <QueueStats stats={queueStatus} theme={theme} />
      
      {/* 用戶任務列表 */}
      <div className="user-tasks-section">
        <h3>我的任務</h3>
        {userTasks.length === 0 ? (
          <div className="empty-hint">目前沒有任務</div>
        ) : (
          <ul className="task-list">
            {userTasks.map(task => (
              <TaskItem
                key={task.id}
                task={task}
                onCancel={handleCancelTask}
                isOwnTask={true}
                theme={theme}
              />
            ))}
          </ul>
        )}
      </div>
      
      {/* 系統隊列狀態 */}
      {showOtherTasks && (
        <div className="other-tasks-section">
          <div className="section-header">
            <h3>系統隊列狀態</h3>
            <button
              className="toggle-btn"
              onClick={() => setShowOtherTasks(false)}
            >
              隱藏
            </button>
          </div>
          {currentProcessing ? (
            <p>當前正在處理其他 {otherTasks.length} 個任務</p>
          ) : (
            <p>系統空閒</p>
          )}
          {otherTasks.length > 0 && (
            <ul className="task-list other-tasks">
              {otherTasks.map((task, index) => (
                <TaskItem
                  key={`other-${index}`}
                  task={task}
                  onCancel={() => {}}
                  isOwnTask={false}
                  theme={theme}
                />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

export default OptimizedQueuePage;