"""
隊列管理器 - 重構後的簡化版本
"""
import threading
import copy
import atexit
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from utils.timezone_utils import now_taipei, to_taipei_isoformat

from .activity_logger import ActivityLogger
from .task_processor import TaskProcessor
from .file_lock_manager import FileLockManager

logger = logging.getLogger(__name__)


def _deep_copy_task(task: Dict) -> Dict:
    """
    深拷貝任務字典，確保嵌套結構完全獨立

    Args:
        task: 任務字典

    Returns:
        完全獨立的任務副本
    """
    return copy.deepcopy(task)

class QueueManager:
    """重構後的隊列管理器 - 模組化設計"""

    # 🔧 修復：定義鎖獲取順序，避免死鎖
    # 鎖順序: queue_lock -> status_lock -> progress_lock -> cache_lock
    # 所有代碼必須按此順序獲取鎖

    def __init__(self, log_dir: str = None):
        # 初始化子模組
        self.activity_logger = ActivityLogger(log_dir)
        self.processor = TaskProcessor()
        self.file_lock = FileLockManager()

        # 隊列狀態
        self.queue: List[Dict] = []
        self.completed: List[Dict] = []
        self.failed: List[Dict] = []

        # 🔧 優化：使用細粒度鎖減少競爭
        # 鎖獲取順序: queue_lock -> status_lock -> progress_lock -> cache_lock
        self.queue_lock = threading.Lock()  # 隊列修改鎖 (順序: 1)
        self.status_lock = threading.Lock()  # 狀態查詢鎖 (順序: 2) - 改為普通Lock避免隱藏問題
        self.progress_lock = threading.Lock()  # 進度更新鎖 (順序: 3)

        # 任務狀態緩存（減少磁盤讀取）
        # 🔒 安全修復：添加緩存大小限制，防止記憶體洩漏
        self._task_cache: Dict[str, Dict] = {}
        self._cache_lock = threading.Lock()  # 緩存鎖 (順序: 4)
        self._max_cache_size = 200  # 最多緩存 200 個任務

        # 🔧 修復：使用線程池管理後台任務，支持優雅關閉
        self._notification_executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="NotificationWorker"
        )
        self._shutdown_event = threading.Event()

        # 註冊關閉處理器
        atexit.register(self._shutdown)

        # 任務只在記憶體中運行，重啟後不恢復
        logger.debug("🚀 模組化隊列管理器已初始化（記憶體模式）")

    def _shutdown(self):
        """優雅關閉線程池和 Email 重試管理器"""
        logger.info("🛑 正在關閉通知線程池...")
        self._shutdown_event.set()
        self._notification_executor.shutdown(wait=True, cancel_futures=False)
        logger.info("✅ 通知線程池已關閉")

        # 關閉 Email 重試管理器
        try:
            from email_retry_manager import get_email_retry_manager
            get_email_retry_manager().shutdown()
        except Exception as e:
            logger.error(f"關閉 Email 重試管理器時出錯: {e}")
        
    def _create_task_template(self, user_id: str, task_type: str = 'audio_processing') -> Dict:
        """
        創建任務模板（純記憶體版本）

        Args:
            user_id: 用戶 ID
            task_type: 任務類型

        Returns:
            任務模板字典
        """
        task_id = str(uuid.uuid4())
        now = now_taipei()

        return {
            'task_id': task_id,
            'id': task_id,  # 兼容性
            'user_id': user_id,
            'task_type': task_type,
            'status': 'pending',
            'created_at': now,
            'started_at': None,
            'completed_at': None,
            'progress': {
                'stage': '等待處理',
                'percentage': 0,
                'message': '任務已加入隊列'
            },
            'result': None,
            'error': None,
            'retry_count': 0
        }
            
    def add_to_queue(self, user_id: str, filename: str, file_size: int, task_data: Dict, ip_address: str = None) -> str:
        """添加任務到隊列"""
        with self.queue_lock:
            # 創建新任務
            task_type = task_data.get('type') or task_data.get('task_data', {}).get('task_type', 'audio_processing')
            task = self._create_task_template(user_id, task_type)
            task.update({
                'filename': filename,
                'file_size': file_size,
                'task_data': task_data,
                'processing_config': task_data.get('processing_config', {}),
                'ip_address': ip_address  # 保存 IP 供後續日誌使用
            })

            task_id = task['task_id']
            success, conflicting_task = self.file_lock.check_and_acquire_file_lock(filename, task_id)

            if not success:
                # 文件被其他任務鎖定
                if conflicting_task and self.file_lock.can_retry_task(conflicting_task):
                    self.file_lock.schedule_retry(conflicting_task)
                    logger.warning(f"⚠️ 文件衝突，安排重試: {filename}")
                raise ValueError(f"文件 {filename} 正在處理中，請稍後再試")

            # 添加到隊列
            self.queue.append(task)

            # 使用深拷貝加入緩存
            with self._cache_lock:
                if len(self._task_cache) >= self._max_cache_size:
                    keys_to_remove = list(self._task_cache.keys())[:self._max_cache_size // 5]
                    for key in keys_to_remove:
                        del self._task_cache[key]
                    logger.debug(f"🧹 清理緩存: 移除 {len(keys_to_remove)} 個舊項目")
                self._task_cache[task_id] = _deep_copy_task(task)

            # 記錄活動日誌
            self.activity_logger.log_activity(
                ip_address=ip_address or 'unknown',
                action='upload',
                task_id=task_id,
                task_type=task_type,
                file_size=file_size
            )

            logger.info(f"📋 任務已添加到隊列: {task_id}")
            return task_id
            
    def get_next_task(self) -> Optional[Dict]:
        """獲取下一個待處理的任務"""
        with self.queue_lock:
            if self.processor.is_processing():
                return None

            # 檢查重試任務
            for task in self.queue:
                task_id = task.get('task_id')
                if (task.get('status') == 'failed' and
                    self.file_lock.can_retry_task(task_id) and
                    self.file_lock.is_ready_for_retry(task_id)):

                    task['status'] = 'pending'
                    task['retry_count'] = task.get('retry_count', 0) + 1
                    logger.info(f"🔄 重試任務: {task_id}")
                    return task

            # 獲取普通待處理任務
            for task in self.queue:
                if task.get('status') == 'pending':
                    if self.processor.start_processing(task):
                        # 記錄開始處理日誌
                        self.activity_logger.log_activity(
                            ip_address=task.get('ip_address', 'unknown'),
                            action='start',
                            task_id=task.get('task_id')
                        )
                        return task

            return None
            
    def complete_task(self, task_id: str, result: Dict):
        """完成任務"""
        with self.queue_lock:
            completed_task = self.processor.complete_processing(task_id, result)
            if completed_task:
                # 從隊列移到已完成
                self.queue = [t for t in self.queue if t.get('task_id') != task_id]
                self.completed.append(completed_task)

                # 保持已完成列表大小
                if len(self.completed) > 50:
                    self.completed = self.completed[-50:]

                # 釋放文件鎖
                filename = completed_task.get('filename')
                if filename:
                    self.file_lock.release_file_lock(filename, task_id)

                # 清理重試信息
                self.file_lock.clear_retry_info(task_id)

                # 使用深拷貝更新緩存
                with self._cache_lock:
                    self._task_cache[task_id] = _deep_copy_task(completed_task)
                    logger.debug(f"✅ 已更新任務 {task_id} 的緩存（狀態：completed）")

                # 記錄活動日誌
                processing_time = None
                if completed_task.get('started_at') and completed_task.get('completed_at'):
                    start = completed_task['started_at']
                    end = completed_task['completed_at']
                    if hasattr(start, 'timestamp') and hasattr(end, 'timestamp'):
                        processing_time = end.timestamp() - start.timestamp()

                self.activity_logger.log_activity(
                    ip_address=completed_task.get('ip_address', 'unknown'),
                    action='complete',
                    task_id=task_id,
                    status='success',
                    processing_time=processing_time
                )

                # 使用線程池發送 Email 通知
                task_copy = _deep_copy_task(completed_task)
                self._notification_executor.submit(
                    self._send_completion_notification,
                    task_copy
                )
                logger.debug(f"📧 Email 通知已提交到線程池")

                logger.info(f"✅ 任務完成: {task_id}")
                
    def fail_task(self, task_id: str, error_message: str):
        """任務失敗"""
        with self.queue_lock:
            failed_task = self.processor.fail_processing(task_id, error_message)
            if failed_task:
                # 更新隊列中的任務狀態
                for task in self.queue:
                    if task.get('task_id') == task_id:
                        task.update(failed_task)
                        break

                # 如果無法重試，移到失敗列表
                if not self.file_lock.can_retry_task(task_id):
                    self.queue = [t for t in self.queue if t.get('task_id') != task_id]
                    self.failed.append(failed_task)

                    # 保持失敗列表大小
                    if len(self.failed) > 20:
                        self.failed = self.failed[-20:]

                    # 釋放文件鎖
                    filename = failed_task.get('filename')
                    if filename:
                        self.file_lock.release_file_lock(filename, task_id)
                else:
                    # 安排重試
                    self.file_lock.schedule_retry(task_id)

                # 使用深拷貝更新緩存
                with self._cache_lock:
                    self._task_cache[task_id] = _deep_copy_task(failed_task)
                    logger.debug(f"❌ 已更新任務 {task_id} 的緩存（狀態：failed）")

                # 記錄活動日誌
                self.activity_logger.log_activity(
                    ip_address=failed_task.get('ip_address', 'unknown'),
                    action='fail',
                    task_id=task_id,
                    status='failed',
                    error=error_message
                )

                # 使用線程池發送失敗 Email 通知
                task_copy = _deep_copy_task(failed_task)
                self._notification_executor.submit(
                    self._send_failure_notification,
                    task_copy,
                    error_message
                )
                logger.debug(f"📧 失敗 Email 通知已提交到線程池")

                logger.error(f"❌ 任務失敗: {task_id} - {error_message}")
                
    def get_queue_status(self) -> Dict:
        """獲取隊列狀態 - 🔧 優化：使用細粒度鎖，返回穩定的統計數據"""
        with self.status_lock:
            current_task = self.processor.get_current_task()
            pending_tasks = [t for t in self.queue if t.get('status') == 'pending']
            active_tasks = 1 if self.processor.is_processing() else 0
            completed_count = len(self.completed)
            failed_count = len(self.failed)

            # 🔧 修復：total_tasks 應包含所有任務（活躍+已完成+失敗）
            # 這樣統計數字才會與用戶看到的任務列表匹配
            return {
                # 兼容前端期望的字段名 - 包含所有任務
                'total_tasks': len(self.queue) + active_tasks + completed_count + failed_count,
                'active_tasks': active_tasks,
                'pending_tasks': len(pending_tasks),
                'completed_tasks': completed_count,
                'failed_tasks': failed_count,

                # 原有字段保持兼容性
                'queue_length': len(pending_tasks),
                'is_processing': self.processor.is_processing(),
                'current_task': current_task,
                'waiting_tasks': [
                    {
                        'task_id': t.get('task_id'),
                        'filename': t.get('filename'),
                        'user_id': t.get('user_id'),
                        'created_at': t.get('created_at').isoformat() if t.get('created_at') else None
                    }
                    for t in pending_tasks
                ],
                'completed_count': completed_count,
                'failed_count': failed_count,
                'stats': {
                    **self.processor.get_processor_stats(),
                    **self.file_lock.get_lock_status(),
                    **self.activity_logger.get_log_stats()
                }
            }
            
    def get_task_status(self, task_id: str, user_id: str = None) -> Optional[Dict]:
        """獲取任務狀態（僅從記憶體）"""
        # 首先檢查處理中的任務
        current_task = self.processor.get_current_task()
        if current_task and current_task.get('task_id') == task_id:
            if user_id and current_task.get('user_id') != user_id:
                return None
            task_copy = _deep_copy_task(current_task)
            with self._cache_lock:
                self._task_cache[task_id] = task_copy
            return _deep_copy_task(current_task)

        # 從隊列中查找
        found_task = None
        with self.status_lock:
            for task_list in [self.queue, self.completed, self.failed]:
                for task in task_list:
                    if task.get('task_id') == task_id:
                        if user_id and task.get('user_id') != user_id:
                            return None
                        found_task = _deep_copy_task(task)
                        break
                if found_task:
                    break

        if found_task:
            with self._cache_lock:
                self._task_cache[task_id] = _deep_copy_task(found_task)
            return found_task

        # 檢查緩存
        with self._cache_lock:
            if task_id in self._task_cache:
                cached_task = _deep_copy_task(self._task_cache[task_id])
                if user_id and cached_task.get('user_id') != user_id:
                    return None
                logger.debug(f"從緩存返回任務: {task_id}")
                return cached_task

        # 任務不存在於記憶體中（已過期或重啟後遺失）
        return None
        
    def cancel_task(self, task_id: str, user_id: str) -> bool:
        """取消任務"""
        with self.queue_lock:
            # 驗證所有權
            task = self.get_task_status(task_id, user_id)
            if not task:
                return False

            # 取消處理
            if self.processor.cancel_task(task_id):
                # 從隊列移除
                self.queue = [t for t in self.queue if t.get('task_id') != task_id]

                # 將取消的任務添加到 completed 列表
                task['status'] = 'cancelled'
                task['completed_at'] = now_taipei()
                self.completed.append(task)

                # 保持已完成列表大小
                if len(self.completed) > 50:
                    self.completed = self.completed[-50:]

                # 使用深拷貝更新緩存
                with self._cache_lock:
                    self._task_cache[task_id] = _deep_copy_task(task)
                    logger.debug(f"✅ 已更新任務 {task_id} 的緩存（狀態：cancelled）")

                # 釋放文件鎖
                filename = task.get('filename')
                if filename:
                    self.file_lock.release_file_lock(filename, task_id)

                # 清理重試信息
                self.file_lock.clear_retry_info(task_id)

                # 記錄活動日誌
                self.activity_logger.log_activity(
                    ip_address=task.get('ip_address', 'unknown'),
                    action='cancel',
                    task_id=task_id,
                    status='cancelled'
                )

                logger.info(f"🚫 任務已取消: {task_id}")
                return True

        return False
        
    def update_task_progress(self, task_id: str, stage: str, percentage: int, message: str = None):
        """更新任務進度（僅記憶體）"""
        self.processor.update_progress(task_id, stage, percentage, message)

        # 獲取進度數據
        progress_data = self.processor.get_task_progress(task_id)

        # 更新緩存
        with self._cache_lock:
            if task_id in self._task_cache:
                self._task_cache[task_id]['progress'] = copy.deepcopy(progress_data)

        # 更新隊列中的任務進度
        with self.progress_lock:
            for task in self.queue:
                if task.get('task_id') == task_id:
                    task['progress'] = copy.deepcopy(progress_data)
                    break
                    
    def get_task_progress(self, task_id: str) -> Dict:
        """獲取任務進度"""
        return self.processor.get_task_progress(task_id)
        
    def is_task_cancelled(self, task_id: str) -> bool:
        """檢查任務是否已取消"""
        return self.processor.is_task_cancelled(task_id)
        
    def verify_task_ownership(self, task_id: str, user_id: str) -> bool:
        """驗證任務所有權"""
        task = self.get_task_status(task_id)
        return task is not None and task.get('user_id') == user_id
        
    def get_user_tasks(self, user_id: str) -> List[Dict]:
        """獲取用戶的所有任務"""
        user_tasks = []
        seen_task_ids = set()  # 避免重複任務
        
        # 檢查當前處理中的任務
        current_task = self.processor.get_current_task()
        if current_task and current_task.get('user_id') == user_id:
            task_id = current_task.get('task_id')
            if task_id and task_id not in seen_task_ids:
                user_tasks.append(current_task)
                seen_task_ids.add(task_id)

        with self.status_lock:
            for task_list in [self.queue, self.completed, self.failed]:
                for task in task_list:
                    if task.get('user_id') == user_id:
                        task_id = task.get('task_id')
                        if task_id and task_id not in seen_task_ids:
                            user_tasks.append(task)
                            seen_task_ids.add(task_id)
                        
        return user_tasks
        
    def get_global_queue_status(self, current_user_id: str) -> Dict:
        """獲取全局隊列狀態，包含他人任務但保護隱私"""
        result = {
            'user_tasks': [],
            'other_tasks': [],
            'queue_stats': {
                'total_tasks': 0,
                'active_tasks': 0,
                'pending_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0
            },
            'current_processing': None,
            'queue_position_info': []
        }
        
        # 調試信息
        logger.debug(f"🔍 Getting global queue status for user: {current_user_id}")
        logger.debug(f"   Queue size: {len(self.queue)}, Completed: {len(self.completed)}, Failed: {len(self.failed)}")

        current_task = self.processor.get_current_task()
        if current_task:
            logger.debug(f"   Current task: {current_task.get('task_id')} - user: {current_task.get('user_id')}")
        
        seen_task_ids = set()
        all_tasks = []
        
        # 🔧 修復：獲取當前處理中的任務 - 從多個來源檢查
        current_task = self.processor.get_current_task()

        # 🔍 Debug: Log processor state
        logger.debug(f"🔍 Processor state: is_processing={self.processor.is_processing()}, current_task={'Yes' if current_task else 'No'}")

        # 🔧 修復：如果processor沒有當前任務，嘗試從queue中找status=processing的任務
        if not current_task:
            with self.status_lock:
                for task in self.queue:
                    if task.get('status') == 'processing':
                        logger.info(f"🔍 Found processing task in queue: {task.get('task_id')}")
                        current_task = task
                        break

        if current_task:
            logger.debug(f"🔍 Current task details: id={current_task.get('task_id')}, status={current_task.get('status')}")

        if current_task:
            # 🔧 修復：深拷貝防止race condition
            current_task_copy = current_task.copy()
            task_id = current_task_copy.get('task_id')
            if task_id and task_id not in seen_task_ids:
                all_tasks.append(current_task_copy)
                seen_task_ids.add(task_id)
                
                # 設置當前處理任務信息（匿名化）
                is_current_user = current_task_copy.get('user_id') == current_user_id
                result['current_processing'] = {
                    'task_id': task_id,
                    'type': current_task_copy.get('type', 'unknown'),
                    'status': current_task_copy.get('status', 'processing'),
                    'progress': current_task_copy.get('progress', {}).copy() if current_task_copy.get('progress') else {},
                    'processing_mode': current_task_copy.get('processing_mode', 'unknown'),
                    'detail_level': current_task_copy.get('detail_level', 'unknown'),
                    'started_at': current_task_copy.get('started_at'),
                    'file_name': current_task_copy.get('file_name') if is_current_user else '***私密文件***',
                    'user_id': current_task_copy.get('user_id') if is_current_user else '***匿名用戶***',
                    'is_own_task': is_current_user
                }
        
        # 收集隊列中等待的任務並計算位置
        pending_tasks = []
        with self.status_lock:
            for i, task in enumerate(self.queue):
                task_id = task.get('task_id')
                if task_id and task_id not in seen_task_ids:
                    # 🔧 修復：拷貝task防止並發修改
                    task_copy = task.copy()
                    all_tasks.append(task_copy)
                    seen_task_ids.add(task_id)
                    
                    # 計算排隊位置信息
                    is_current_user = task_copy.get('user_id') == current_user_id
                    queue_info = {
                        'task_id': task_id,
                        'position': i + 1,  # 在隊列中的位置（1開始）
                        'user_id': task_copy.get('user_id') if is_current_user else '***匿名用戶***',
                        'type': task_copy.get('type', 'unknown'),
                        'processing_mode': task_copy.get('processing_mode', 'unknown'),
                        'file_name': task_copy.get('file_name') if is_current_user else '***私密文件***',
                        'created_at': task_copy.get('created_at'),
                        'is_own_task': is_current_user
                    }
                    result['queue_position_info'].append(queue_info)
                    pending_tasks.append(task_copy)

        # 收集已完成和失敗的任務 - 🔧 優化：僅返回最近5個已完成任務，避免大payload
        with self.status_lock:
            # 合併completed和failed列表，按完成時間排序
            all_finished = []
            for task in self.completed + self.failed:
                task_id = task.get('task_id')
                if task_id and task_id not in seen_task_ids:
                    all_finished.append(task)

            # 按完成時間排序（最新的在前）
            all_finished.sort(
                key=lambda t: t.get('completed_at') or t.get('created_at') or '',
                reverse=True
            )

            # 只取前5個
            for task in all_finished[:5]:
                task_copy = task.copy()
                all_tasks.append(task_copy)
                seen_task_ids.add(task.get('task_id'))
        
        # 🔧 修復：使用穩定的統計數據，計算所有任務
        active_task_count = 1 if self.processor.is_processing() else 0
        pending_count = len([t for t in self.queue if t.get('status') == 'pending'])
        completed_count = len(self.completed)
        failed_count = len(self.failed)

        # 🔧 關鍵修復：total_tasks 應包含所有任務（活躍+已完成+失敗）
        # 這樣用戶看到已完成任務時，統計數字才會匹配
        result['queue_stats'] = {
            'total_tasks': len(self.queue) + active_task_count + completed_count + failed_count,
            'active_tasks': active_task_count,
            'pending_tasks': pending_count,
            'completed_tasks': completed_count,
            'failed_tasks': failed_count
        }

        # 🔍 Debug: Log statistics calculation
        logger.debug(f"📊 Statistics: queue={len(self.queue)}, active={active_task_count}, "
                    f"pending={pending_count}, completed={completed_count}, failed={failed_count}, "
                    f"total={result['queue_stats']['total_tasks']}")

        # 分類任務到user_tasks和other_tasks
        for task in all_tasks:
            task_user_id = task.get('user_id')
            task_status = task.get('status', 'unknown')

            if task_user_id == current_user_id:
                # 用戶自己的任務 - 🔧 修復：移除result欄位以減少payload大小
                # 前端只需要狀態信息，不需要完整的處理結果（AI摘要等）
                task_summary = {
                    'task_id': task.get('task_id'),
                    'id': task.get('task_id'),  # For compatibility
                    'type': task.get('type', 'unknown'),
                    'status': task_status,
                    'created_at': task.get('created_at'),
                    'started_at': task.get('started_at'),
                    'completed_at': task.get('completed_at'),
                    'processing_mode': task.get('processing_mode', 'unknown'),
                    'detail_level': task.get('detail_level', 'unknown'),
                    'progress': task.get('progress', {}),
                    'file_name': task.get('file_name'),
                    'filename': task.get('filename'),
                    'user_id': task.get('user_id'),
                    # 不包含 'result' 欄位，前端從 /api/task/{task_id}/result 獲取
                }
                result['user_tasks'].append(task_summary)
            else:
                # 他人任務，只顯示匿名化信息
                anonymous_task = {
                    'task_id': task.get('task_id'),
                    'type': task.get('type', 'unknown'),
                    'status': task_status,
                    'created_at': task.get('created_at'),
                    'started_at': task.get('started_at'),
                    'completed_at': task.get('completed_at'),
                    'processing_mode': task.get('processing_mode', 'unknown'),
                    'detail_level': task.get('detail_level', 'unknown'),
                    'progress': task.get('progress', {}),
                    # 隱私保護：不顯示文件名、內容、用戶信息
                    'file_name': '***私密文件***',
                    'filename': '***私密文件***',
                    'user_id': '***匿名用戶***'
                }
                result['other_tasks'].append(anonymous_task)
        
        return result
        
    def wait_for_task_completion(self, task_id: str, user_id: str, timeout: int = 30) -> Optional[Dict]:
        """等待任務完成"""
        # 可以添加額外的用戶驗證邏輯
        return self.processor.wait_for_completion(task_id, timeout)
        
    def cleanup(self):
        """清理操作"""
        # 清理處理器
        self.processor.cleanup_completed_tasks()

        # 清理舊日誌
        from config import config
        self.activity_logger.cleanup_old_logs(config.ACTIVITY_LOG_RETENTION_DAYS)

        logger.info("🧹 隊列清理完成")
        
    def get_user_position(self, task_id: str) -> Dict:
        """獲取用戶在隊列中的位置信息 - 🔧 優化：使用細粒度鎖"""
        with self.status_lock:
            # 如果是當前處理的任務
            current_task = self.processor.get_current_task()
            if current_task and current_task.get('task_id') == task_id:
                return {
                    'status': 'processing',
                    'position': 0,
                    'estimated_wait_time': 0,
                    'message': '正在處理中...'
                }
            
            # 在等待隊列中
            for i, task in enumerate(self.queue):
                if task.get('task_id') == task_id:
                    position = i + 1
                    # 估算等待時間（假設每個任務平均3分鐘）
                    estimated_wait = position * 3
                    
                    return {
                        'status': 'waiting',
                        'position': position,
                        'estimated_wait_time': estimated_wait,
                        'message': f'排隊中，前面還有 {position} 個任務'
                    }
            
            # 檢查是否已完成
            for task in self.completed:
                if task.get('task_id') == task_id:
                    return {
                        'status': task.get('status'),
                        'position': 0,
                        'estimated_wait_time': 0,
                        'message': '任務已完成' if task.get('status') == 'completed' else '任務失敗'
                    }
            
            return {
                'status': 'not_found',
                'position': -1,
                'estimated_wait_time': 0,
                'message': '找不到該任務'
            }
    
    def remove_task(self, task_id: str) -> bool:
        """從隊列中移除任務（僅限等待中的任務） - 🔧 優化：使用細粒度鎖"""
        with self.queue_lock:
            for i, task in enumerate(self.queue):
                if task.get('task_id') == task_id:
                    self.queue.pop(i)
                    
                    # 更新剩餘任務的位置
                    for j, remaining_task in enumerate(self.queue):
                        remaining_task['position'] = j + 1
                    
                    logger.info(f"任務已從隊列移除: {task_id}")
                    return True
            
            return False
    
    def clear_all_tasks(self, user_id: str = None) -> Dict:
        """清除所有任務（可選按用戶過濾） - 🔧 優化：使用細粒度鎖"""
        try:
            with self.queue_lock:
                cleared_count = 0
                cleared_tasks = []
                
                # 清除等待隊列中的任務
                if user_id:
                    # 只清除指定用戶的任務
                    tasks_to_remove = [task for task in self.queue if task.get('user_id') == user_id]
                    for task in tasks_to_remove:
                        self.queue.remove(task)
                        cleared_tasks.append({
                            'task_id': task.get('task_id'),
                            'filename': task.get('filename'),
                            'status': 'pending'
                        })
                        cleared_count += 1
                else:
                    # 清除所有等待任務
                    cleared_tasks.extend([{
                        'task_id': task.get('task_id'),
                        'filename': task.get('filename'),
                        'status': 'pending'
                    } for task in self.queue])
                    cleared_count += len(self.queue)
                    self.queue.clear()
                
                # 清除已完成和失敗的任務
                if user_id:
                    # 只清除指定用戶的已完成任務
                    completed_to_remove = [task for task in self.completed if task.get('user_id') == user_id]
                    for task in completed_to_remove:
                        self.completed.remove(task)
                        cleared_tasks.append({
                            'task_id': task.get('task_id'),
                            'filename': task.get('filename'),
                            'status': 'completed'
                        })
                        cleared_count += 1
                    
                    # 只清除指定用戶的失敗任務
                    failed_to_remove = [task for task in self.failed if task.get('user_id') == user_id]
                    for task in failed_to_remove:
                        self.failed.remove(task)
                        cleared_tasks.append({
                            'task_id': task.get('task_id'),
                            'filename': task.get('filename'),
                            'status': 'failed'
                        })
                        cleared_count += 1
                else:
                    # 清除所有已完成和失敗任務
                    cleared_tasks.extend([{
                        'task_id': task.get('task_id'),
                        'filename': task.get('filename'),
                        'status': 'completed'
                    } for task in self.completed])
                    cleared_tasks.extend([{
                        'task_id': task.get('task_id'),
                        'filename': task.get('filename'),
                        'status': 'failed'
                    } for task in self.failed])
                    cleared_count += len(self.completed) + len(self.failed)
                    self.completed.clear()
                    self.failed.clear()
                
                # 如果當前有正在處理的任務且是該用戶的，也標記為取消
                current_task = self.processor.get_current_task()
                if current_task and (not user_id or current_task.get('user_id') == user_id):
                    self.processor.cancel_task(current_task.get('task_id'))
                    cleared_tasks.append({
                        'task_id': current_task.get('task_id'),
                        'filename': current_task.get('filename'),
                        'status': 'cancelled'
                    })
                    cleared_count += 1
                
                # 清除緩存
                with self._cache_lock:
                    for task_info in cleared_tasks:
                        task_id = task_info['task_id']
                        if task_id in self._task_cache:
                            del self._task_cache[task_id]

                logger.info(f"已清除 {cleared_count} 個任務，用戶: {user_id or '全部'}")
                
                return {
                    'success': True,
                    'cleared_count': cleared_count,
                    'cleared_tasks': cleared_tasks,
                    'message': f'已清除 {cleared_count} 個任務'
                }
                
        except Exception as e:
            logger.error(f"清除任務錯誤: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'cleared_count': 0
            }

    def health_check(self) -> Dict:
        """健康檢查"""
        return {
            'status': 'healthy',
            'queue_stats': self.get_queue_status(),
            'processor_stats': self.processor.get_processor_stats(),
            'lock_stats': self.file_lock.get_lock_status(),
            'log_stats': self.activity_logger.get_log_stats()
        }
    
    def _send_completion_notification(self, task: Dict):
        """
        發送任務完成的 Email 通知並清理上傳文件

        使用 EmailRetryManager 實現：
        - SMTP 30 秒超時
        - 最多 3 次重試（間隔 5s, 15s）
        - 重試全部失敗後發送「發送失敗通知」
        """
        task_id = task.get('task_id', 'unknown')
        logger.debug(f"📧 [後台線程] 開始處理任務 {task_id} 的 Email 通知")

        try:
            from email_service import is_email_enabled, send_processing_result, send_batch_processing_result
            from email_retry_manager import get_email_retry_manager

            # 檢查系統 Email 服務是否啟用
            if not is_email_enabled():
                logger.debug("Email 服務未啟用，跳過通知")
            else:
                processing_config = task.get('processing_config', {})
                task_email_enabled = processing_config.get('email_enabled', False)
                task_email_address = processing_config.get('email_address')

                if not task_email_enabled:
                    logger.debug("任務未啟用 Email 通知，跳過通知")
                elif not task_email_address:
                    logger.warning("任務啟用了 Email 通知但缺少 Email 地址，跳過通知")
                else:
                    task_id = task.get('task_id')
                    result = task.get('result', {})

                    if task_id:
                        logger.info(f"📧 準備發送 Email 通知:")
                        logger.info(f"  - task_id: {task_id}")
                        logger.info(f"  - email_address: {task_email_address}")

                        # 獲取重試管理器
                        retry_manager = get_email_retry_manager()

                        # 準備原始任務信息（用於失敗通知）
                        is_batch = result.get('files') or result.get('batch_info')
                        filename = task.get('filename', '未知文件')

                        original_info = {
                            'task_id': task_id,
                            'filename': filename,
                            'email_type': 'batch' if is_batch else 'single'
                        }

                        if is_batch:
                            # 批次處理結果
                            logger.info(f"  - 類型: 批次處理 ({result.get('batch_info', {}).get('total_files', 0)} 個檔案)")

                            email_task_id = retry_manager.submit_email(
                                email_type='batch_processing_result',
                                to_email=task_email_address,
                                send_func=send_batch_processing_result,
                                send_args={
                                    'to_email': task_email_address,
                                    'task_id': task_id,
                                    'batch_result': result,
                                    'processing_config': processing_config
                                },
                                original_task_info=original_info
                            )
                        else:
                            # 單檔案結果
                            logger.info(f"  - 類型: 單檔案")
                            logger.info(f"  - filename: {filename}")

                            email_result = {
                                'processing_mode': processing_config.get('processing_mode', 'default'),
                                'detail_level': processing_config.get('detail_level', 'normal'),
                                'processing_time': result.get('processing_time', 0),
                                'original_text': result.get('original_text', '') or result.get('whisper_result', ''),
                                'organized_text': result.get('processed_text', '') or result.get('ai_summary', ''),
                                'ai_model': processing_config.get('ai_model', 'unknown'),
                            }

                            email_task_id = retry_manager.submit_email(
                                email_type='processing_result',
                                to_email=task_email_address,
                                send_func=send_processing_result,
                                send_args={
                                    'to_email': task_email_address,
                                    'task_id': task_id,
                                    'filename': filename,
                                    'result': email_result,
                                    'processing_config': processing_config
                                },
                                original_task_info=original_info
                            )

                        # 執行發送（帶重試）
                        success = retry_manager.execute_with_retry(email_task_id)

                        if success:
                            logger.info(f"📧 Email 通知發送成功: {task_id} -> {task_email_address}")
                        else:
                            logger.warning(f"📧 Email 通知最終失敗（已發送失敗通知）: {task_id} -> {task_email_address}")
                    else:
                        logger.warning("任務缺少 task_id，無法發送 email 通知")

        except Exception as e:
            logger.error(f"❌ 發送 Email 通知時出錯: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

        # 無論 Email 發送成功與否，都立即清理上傳的文件
        self._cleanup_uploaded_files(task)
    
    def _cleanup_uploaded_files(self, task: Dict):
        """
        清理任務完成後的上傳文件

        Args:
            task: 任務字典
        """
        try:
            from utils.file_cleaner import FileCleanupManager
            from config import config

            task_id = task.get('task_id', 'unknown')

            # 創建文件清理管理器
            cleaner = FileCleanupManager(config.UPLOAD_FOLDER)

            # 執行音視頻文件清理
            cleanup_results = cleaner.cleanup_task_files(task)

            if cleanup_results:
                successful_cleanups = sum(1 for success in cleanup_results.values() if success)
                total_files = len(cleanup_results)
                logger.info(f"🗑️ 任務 {task_id} 音檔清理結果: {successful_cleanups}/{total_files} 個文件成功清理")
            else:
                logger.debug(f"任務 {task_id} 沒有音檔需要清理")

        except Exception as cleanup_error:
            logger.error(f"❌ 處理文件清理時出錯: {str(cleanup_error)}")
    
    def _send_failure_notification(self, task: Dict, error_message: str):
        """
        發送任務失敗的 Email 通知

        使用 EmailRetryManager 實現：
        - SMTP 30 秒超時
        - 最多 3 次重試（間隔 5s, 15s）
        - 重試全部失敗後發送「發送失敗通知」
        """
        task_id = task.get('task_id', 'unknown')
        logger.debug(f"📧 [後台線程] 開始處理任務 {task_id} 的失敗 Email 通知")

        try:
            from email_service import is_email_enabled, send_error_notification
            from email_retry_manager import get_email_retry_manager

            # 檢查系統 Email 服務是否啟用
            if not is_email_enabled():
                logger.debug("Email 服務未啟用，跳過失敗通知")
                self._cleanup_uploaded_files(task)
                return

            processing_config = task.get('processing_config', {})
            task_email_enabled = processing_config.get('email_enabled', False)
            task_email_address = processing_config.get('email_address')

            if not task_email_enabled:
                logger.debug("任務未啟用 Email 通知，跳過失敗通知")
                self._cleanup_uploaded_files(task)
                return

            if not task_email_address:
                logger.warning("任務啟用了 Email 通知但缺少 Email 地址，跳過失敗通知")
                self._cleanup_uploaded_files(task)
                return

            task_id = task.get('task_id')
            filename = task.get('filename', '未知文件')

            if not task_id:
                logger.warning("任務缺少 task_id，無法發送失敗 email 通知")
                self._cleanup_uploaded_files(task)
                return

            logger.info(f"📧 準備發送失敗 Email 通知:")
            logger.info(f"  - task_id: {task_id}")
            logger.info(f"  - email_address: {task_email_address}")
            logger.info(f"  - filename: {filename}")
            logger.info(f"  - error: {error_message}")

            # 準備原始任務信息
            original_info = {
                'task_id': task_id,
                'filename': filename,
                'email_type': 'error'
            }

            # 獲取重試管理器
            retry_manager = get_email_retry_manager()

            email_task_id = retry_manager.submit_email(
                email_type='error_notification',
                to_email=task_email_address,
                send_func=send_error_notification,
                send_args={
                    'to_email': task_email_address,
                    'task_id': task_id,
                    'filename': filename,
                    'error_message': error_message,
                    'processing_config': processing_config
                },
                original_task_info=original_info
            )

            # 執行發送（帶重試）
            success = retry_manager.execute_with_retry(email_task_id)

            if success:
                logger.info(f"📧 失敗 Email 通知發送成功: {task_id} -> {task_email_address}")
            else:
                logger.warning(f"📧 失敗 Email 通知最終失敗（已發送失敗通知）: {task_id} -> {task_email_address}")

        except Exception as e:
            logger.error(f"❌ 發送失敗 Email 通知時出錯: {str(e)}")

        # 無論 Email 發送成功與否，都立即清理上傳的文件
        self._cleanup_uploaded_files(task)
