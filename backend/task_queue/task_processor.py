"""
任務處理器 - 處理任務的執行和狀態管理
"""
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable
import logging
from utils.timezone_utils import now_taipei, to_taipei_isoformat

logger = logging.getLogger(__name__)

class TaskProcessor:
    """任務處理器"""

    def __init__(self):
        self.processing_task: Optional[Dict] = None
        self.cancelled_tasks: set = set()
        self.task_events: Dict[str, threading.Event] = {}
        self.task_results: Dict[str, Dict] = {}
        self.lock = threading.Lock()

        # 處理器配置 - 從 config 讀取
        try:
            from config import config
            self.max_concurrent_tasks = config.MAX_CONCURRENT_TASKS
            self.task_timeout = config.TASK_TIMEOUT
            logger.info(f"⚙️ 任務處理器配置: 最大並發={self.max_concurrent_tasks}, 超時={self.task_timeout}s")
        except Exception as e:
            logger.warning(f"讀取配置失敗，使用默認值: {e}")
            self.max_concurrent_tasks = 1  # 降級到單任務處理
            self.task_timeout = 1800  # 30分鐘超時
        
    def start_processing(self, task: Dict) -> bool:
        """開始處理任務"""
        with self.lock:
            if self.processing_task is not None:
                logger.warning(f"處理器忙碌中，無法處理新任務: {task.get('task_id')}")
                return False
                
            task_id = task.get('task_id') or task.get('id')
            if task_id in self.cancelled_tasks:
                logger.info(f"任務已被取消，跳過處理: {task_id}")
                return False
                
            self.processing_task = task
            task['status'] = 'processing'
            task['started_at'] = now_taipei()
            
            logger.info(f"▶️ 開始處理任務: {task_id}")
            return True
            
    def complete_processing(self, task_id: str, result: Dict):
        """完成任務處理"""
        with self.lock:
            if (self.processing_task and
                (self.processing_task.get('task_id') == task_id or
                 self.processing_task.get('id') == task_id)):

                self.processing_task['status'] = 'completed'
                self.processing_task['completed_at'] = now_taipei()
                self.processing_task['result'] = result
                self.processing_task['progress'] = {
                    'stage': '處理完成',
                    'percentage': 100,
                    'message': '任務已成功完成'
                }

                # 保存結果供後續查詢
                self.task_results[task_id] = result

                # 🔧 修復：清除所有快取以避免重複任務時的數據污染
                try:
                    from utils.cache_manager import cache_manager
                    cache_manager.clear_all()
                    logger.info(f"🧹 Task {task_id}: 所有快取已清除（防止重複任務數據污染）")
                except Exception as e:
                    logger.warning(f"⚠️ Task {task_id}: 清除快取失敗: {e}")

                # 觸發等待事件
                if task_id in self.task_events:
                    self.task_events[task_id].set()

                # 清理處理狀態
                completed_task = self.processing_task
                self.processing_task = None

                logger.info(f"✅ 任務處理完成: {task_id}")
                return completed_task

        return None
        
    def fail_processing(self, task_id: str, error_message: str):
        """任務處理失敗"""
        with self.lock:
            if (self.processing_task and
                (self.processing_task.get('task_id') == task_id or
                 self.processing_task.get('id') == task_id)):

                self.processing_task['status'] = 'failed'
                self.processing_task['completed_at'] = now_taipei()
                self.processing_task['error'] = error_message
                self.processing_task['progress'] = {
                    'stage': '處理失敗',
                    'percentage': 0,
                    'message': f'錯誤: {error_message}'
                }

                # 🔧 修復：即使任務失敗也清除快取，防止下次任務受污染
                try:
                    from utils.cache_manager import cache_manager
                    cache_manager.clear_all()
                    logger.info(f"🧹 Task {task_id}: 失敗任務快取已清除")
                except Exception as e:
                    logger.warning(f"⚠️ Task {task_id}: 清除快取失敗: {e}")

                # 觸發等待事件
                if task_id in self.task_events:
                    self.task_events[task_id].set()

                # 清理處理狀態
                failed_task = self.processing_task
                self.processing_task = None

                logger.error(f"❌ 任務處理失敗: {task_id} - {error_message}")
                return failed_task

        return None
        
    def update_progress(self, task_id: str, stage: str, percentage: int, message: str = None):
        """更新任務進度"""
        with self.lock:
            if (self.processing_task and 
                (self.processing_task.get('task_id') == task_id or 
                 self.processing_task.get('id') == task_id)):
                
                self.processing_task['progress'] = {
                    'stage': stage,
                    'percentage': max(0, min(100, percentage)),
                    'message': message or stage,
                    'updated_at': to_taipei_isoformat()
                }
                
                logger.debug(f"📊 任務進度更新: {task_id} - {stage} ({percentage}%)")
                
    def cancel_task(self, task_id: str) -> bool:
        """取消任務"""
        with self.lock:
            # 標記為已取消
            self.cancelled_tasks.add(task_id)
            
            # 如果正在處理，停止處理
            if (self.processing_task and 
                (self.processing_task.get('task_id') == task_id or 
                 self.processing_task.get('id') == task_id)):
                
                self.processing_task['status'] = 'cancelled'
                self.processing_task['completed_at'] = now_taipei()
                self.processing_task['progress'] = {
                    'stage': '已取消',
                    'percentage': 0,
                    'message': '任務已被用戶取消'
                }
                
                # 觸發等待事件
                if task_id in self.task_events:
                    self.task_events[task_id].set()
                    
                self.processing_task = None
                
            logger.info(f"🚫 任務已取消: {task_id}")
            return True
            
    def is_task_cancelled(self, task_id: str) -> bool:
        """檢查任務是否已取消"""
        return task_id in self.cancelled_tasks
        
    def is_processing(self) -> bool:
        """檢查是否正在處理任務"""
        with self.lock:
            return self.processing_task is not None
            
    def get_current_task(self) -> Optional[Dict]:
        """獲取當前處理的任務"""
        with self.lock:
            return self.processing_task.copy() if self.processing_task else None
            
    def get_task_progress(self, task_id: str) -> Dict:
        """獲取任務進度"""
        with self.lock:
            if (self.processing_task and 
                (self.processing_task.get('task_id') == task_id or 
                 self.processing_task.get('id') == task_id)):
                return self.processing_task.get('progress', {})
                
            # 檢查已完成的結果
            if task_id in self.task_results:
                return {
                    'stage': '處理完成',
                    'percentage': 100,
                    'message': '任務已完成'
                }
                
            return {}
            
    def wait_for_completion(self, task_id: str, timeout: int = None) -> Optional[Dict]:
        """等待任務完成"""
        if timeout is None:
            timeout = self.task_timeout
            
        # 創建等待事件
        if task_id not in self.task_events:
            self.task_events[task_id] = threading.Event()
            
        # 等待完成
        completed = self.task_events[task_id].wait(timeout)
        
        # 清理事件
        if task_id in self.task_events:
            del self.task_events[task_id]
            
        if not completed:
            logger.warning(f"⏰ 任務等待超時: {task_id}")
            return None
            
        # 返回結果
        return self.task_results.get(task_id)
        
    def cleanup_completed_tasks(self):
        """清理已完成任務的結果"""
        with self.lock:
            # 清理舊的結果（保留最近50個）
            if len(self.task_results) > 50:
                items = list(self.task_results.items())
                # 簡單的清理策略：保留最新的50個
                self.task_results = dict(items[-50:])
                
            # 清理舊的取消任務記錄（保留最近100個）
            if len(self.cancelled_tasks) > 100:
                # 轉換為列表，保留最新的100個
                cancelled_list = list(self.cancelled_tasks)
                self.cancelled_tasks = set(cancelled_list[-100:])
                
    def get_processor_stats(self) -> Dict:
        """獲取處理器統計"""
        with self.lock:
            current_task = self.processing_task
            return {
                'is_processing': current_task is not None,
                'current_task_id': current_task.get('task_id') if current_task else None,
                'cancelled_count': len(self.cancelled_tasks),
                'result_cache_size': len(self.task_results),
                'pending_events': len(self.task_events)
            }