/**
 * 統一的存儲管理模組
 * 簡化和規範化 localStorage 使用
 */

const STORAGE_KEYS = {
  USER_ID: 'voice_processor_user_id',
  THEME: 'voice_processor_theme',
  USER_EMAIL: 'voice_processor_user_email',
  TASK_PREFIX: 'task_',
  RESULT_PREFIX: 'result_',
  RESULT_META_PREFIX: 'result_meta_',
  PROCESSING_TASK_PREFIX: 'processing_task_',
  TASK_PROGRESS_PREFIX: 'task_progress_',
  TEXT_PROCESSING_SETTINGS: 'text_processing_settings'
};

class StorageManager {
  /**
   * 獲取用戶ID
   */
  getUserId() {
    return localStorage.getItem(STORAGE_KEYS.USER_ID);
  }

  /**
   * 設置用戶ID
   */
  setUserId(userId) {
    localStorage.setItem(STORAGE_KEYS.USER_ID, userId);
  }

  /**
   * 獲取主題
   */
  getTheme() {
    return localStorage.getItem(STORAGE_KEYS.THEME) || 'light';
  }

  /**
   * 設置主題
   */
  setTheme(theme) {
    localStorage.setItem(STORAGE_KEYS.THEME, theme);
  }

  /**
   * 獲取用戶Email
   */
  getUserEmail() {
    return localStorage.getItem(STORAGE_KEYS.USER_EMAIL) || '';
  }

  /**
   * 設置用戶Email
   */
  setUserEmail(email) {
    localStorage.setItem(STORAGE_KEYS.USER_EMAIL, email);
  }

  /**
   * 獲取任務ID
   */
  getTaskId(userId) {
    return localStorage.getItem(`${STORAGE_KEYS.TASK_PREFIX}${userId}`);
  }

  /**
   * 設置任務ID
   */
  setTaskId(userId, taskId) {
    localStorage.setItem(`${STORAGE_KEYS.TASK_PREFIX}${userId}`, taskId);
  }

  /**
   * 清除任務ID
   */
  clearTaskId(userId) {
    localStorage.removeItem(`${STORAGE_KEYS.TASK_PREFIX}${userId}`);
  }

  /**
   * 保存任務結果
   */
  saveResult(userId, taskId, result, metadata = {}) {
    try {
      const resultData = {
        taskId,
        result,
        timestamp: Date.now(),
        userId
      };
      
      const metaData = {
        taskId,
        timestamp: Date.now(),
        filename: metadata.filename,
        processingMode: metadata.processingMode,
        size: JSON.stringify(result).length
      };
      
      localStorage.setItem(`${STORAGE_KEYS.RESULT_PREFIX}${userId}`, JSON.stringify(resultData));
      localStorage.setItem(`${STORAGE_KEYS.RESULT_META_PREFIX}${userId}`, JSON.stringify(metaData));
    } catch (error) {
      // 保存結果失敗，靜默處理
    }
  }

  /**
   * 獲取保存的結果
   */
  getSavedResult(userId) {
    try {
      const resultData = localStorage.getItem(`${STORAGE_KEYS.RESULT_PREFIX}${userId}`);
      return resultData ? JSON.parse(resultData) : null;
    } catch (error) {
      return null;
    }
  }

  /**
   * 獲取結果元數據
   */
  getResultMetadata(userId) {
    try {
      const metaData = localStorage.getItem(`${STORAGE_KEYS.RESULT_META_PREFIX}${userId}`);
      return metaData ? JSON.parse(metaData) : null;
    } catch (error) {
      return null;
    }
  }

  /**
   * 清除保存的結果
   */
  clearResult(userId) {
    localStorage.removeItem(`${STORAGE_KEYS.RESULT_PREFIX}${userId}`);
    localStorage.removeItem(`${STORAGE_KEYS.RESULT_META_PREFIX}${userId}`);
  }

  /**
   * 清理超過指定天數的結果數據
   */
  cleanupOldResults(maxAgeDays = 7) {
    try {
      const maxAge = maxAgeDays * 24 * 60 * 60 * 1000; // 轉換為毫秒
      const now = Date.now();
      
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.startsWith(STORAGE_KEYS.RESULT_PREFIX) || key.startsWith(STORAGE_KEYS.RESULT_META_PREFIX))) {
          try {
            const data = JSON.parse(localStorage.getItem(key));
            if (data && data.timestamp && (now - data.timestamp) > maxAge) {
              localStorage.removeItem(key);
            }
          } catch (e) {
            // 如果解析失敗，直接刪除損壞的數據
            localStorage.removeItem(key);
          }
        }
      }
    } catch (error) {
      // 清理舊結果失敗，靜默處理
    }
  }

  /**
   * 生成新的用戶ID
   */
  generateUserId() {
    return `user_${Date.now()}_${Math.random().toString(36).substr(2, 8)}`;
  }

  /**
   * 清理過期的存儲數據
   */
  cleanup() {
    try {
      const keysToRemove = [];
      
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('voice_processor_')) {
          // 清理舊版本的備份和時間戳
          if (key.includes('_backup_') || key.includes('_timestamp_')) {
            keysToRemove.push(key);
          }
        }
      }
      
      keysToRemove.forEach(key => {
        localStorage.removeItem(key);
      });

      // 清理超過7天的結果數據
      this.cleanupOldResults();
    } catch (error) {
      // 存儲清理失敗，靜默處理
    }
  }

  /**
   * 保存處理中的任務狀態
   */
  saveProcessingTask(userId, taskData) {
    try {
      const data = {
        ...taskData,
        savedAt: Date.now(),
        userId
      };
      localStorage.setItem(`${STORAGE_KEYS.PROCESSING_TASK_PREFIX}${userId}`, JSON.stringify(data));
    } catch (error) {
      // 保存處理中任務失敗，靜默處理
    }
  }

  /**
   * 獲取處理中的任務狀態
   */
  getProcessingTask(userId) {
    try {
      const data = localStorage.getItem(`${STORAGE_KEYS.PROCESSING_TASK_PREFIX}${userId}`);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      return null;
    }
  }

  /**
   * 清除處理中的任務狀態
   */
  clearProcessingTask(userId) {
    localStorage.removeItem(`${STORAGE_KEYS.PROCESSING_TASK_PREFIX}${userId}`);
    localStorage.removeItem(`${STORAGE_KEYS.TASK_PROGRESS_PREFIX}${userId}`);
  }

  /**
   * 保存任務進度
   */
  saveTaskProgress(userId, progress) {
    try {
      const data = {
        ...progress,
        updatedAt: Date.now()
      };
      localStorage.setItem(`${STORAGE_KEYS.TASK_PROGRESS_PREFIX}${userId}`, JSON.stringify(data));
    } catch (error) {
      // 保存任務進度失敗，靜默處理
    }
  }

  /**
   * 獲取任務進度
   */
  getTaskProgress(userId) {
    try {
      const data = localStorage.getItem(`${STORAGE_KEYS.TASK_PROGRESS_PREFIX}${userId}`);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      return null;
    }
  }

  /**
   * 獲取文字處理設定
   */
  getTextProcessingSettings() {
    try {
      const settings = localStorage.getItem(STORAGE_KEYS.TEXT_PROCESSING_SETTINGS);
      return settings ? JSON.parse(settings) : null;
    } catch (error) {
      return null;
    }
  }

  /**
   * 保存文字處理設定
   */
  setTextProcessingSettings(settings) {
    try {
      localStorage.setItem(STORAGE_KEYS.TEXT_PROCESSING_SETTINGS, JSON.stringify(settings));
    } catch (error) {
      // 保存文字處理設定失敗，靜默處理
    }
  }

  /**
   * 清除文字處理設定
   */
  clearTextProcessingSettings() {
    localStorage.removeItem(STORAGE_KEYS.TEXT_PROCESSING_SETTINGS);
  }

  /**
   * 獲取存儲使用情況
   */
  getStorageInfo() {
    try {
      const info = {
        total: 0,
        keys: []
      };
      
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('voice_processor_')) {
          const value = localStorage.getItem(key);
          const size = (key.length + (value ? value.length : 0)) * 2; // 估算大小（字節）
          info.total += size;
          info.keys.push({
            key,
            size,
            valueLength: value ? value.length : 0
          });
        }
      }
      
      return info;
    } catch (error) {
      return { total: 0, keys: [] };
    }
  }
}

// 導出單例
export default new StorageManager();
