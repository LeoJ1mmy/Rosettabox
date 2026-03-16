"""
文件鎖管理器 - 處理文件衝突和重試邏輯
🔧 修復：解決 TOCTOU 競態條件
"""
import threading
import time
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class FileLockManager:
    """文件鎖管理器 - 🔧 修復：所有操作都在鎖內執行，避免 TOCTOU"""

    def __init__(self):
        self.file_locks: Dict[str, str] = {}  # filename -> task_id
        self.retry_info: Dict[str, Dict] = {}  # task_id -> retry info
        self.lock = threading.Lock()

    def check_file_conflict(self, filename: str) -> Optional[str]:
        """
        檢查文件是否有衝突 - 🔧 修復：在鎖內執行

        Args:
            filename: 文件名

        Returns:
            如果有衝突，返回持有鎖的 task_id；否則返回 None
        """
        with self.lock:
            return self.file_locks.get(filename)

    def check_and_acquire_file_lock(self, filename: str, task_id: str) -> Tuple[bool, Optional[str]]:
        """
        🔧 新增：原子操作 - 檢查並獲取文件鎖（避免 TOCTOU）

        Args:
            filename: 文件名
            task_id: 任務ID

        Returns:
            Tuple[bool, Optional[str]]: (是否成功獲取, 衝突的task_id或None)
        """
        with self.lock:
            existing_task = self.file_locks.get(filename)
            if existing_task is not None and existing_task != task_id:
                # 文件被其他任務鎖定
                return False, existing_task

            # 獲取鎖
            self.file_locks[filename] = task_id
            logger.info(f"🔒 文件鎖已獲取: {filename} -> {task_id}")
            return True, None

    def acquire_file_lock(self, filename: str, task_id: str) -> bool:
        """
        嘗試獲取文件鎖 - 🔧 修復：使用原子操作

        Args:
            filename: 文件名
            task_id: 任務ID

        Returns:
            是否成功獲取鎖
        """
        success, _ = self.check_and_acquire_file_lock(filename, task_id)
        return success
            
    def release_file_lock(self, filename: str, task_id: str):
        """釋放文件鎖 - 線程安全"""
        with self.lock:
            if self.file_locks.get(filename) == task_id:
                del self.file_locks[filename]
                logger.info(f"🔓 文件鎖已釋放: {filename}")

    def can_retry_task(self, task_id: str) -> bool:
        """檢查任務是否可以重試 - 🔧 修復：線程安全"""
        with self.lock:
            return self.retry_info.get(task_id, {}).get('count', 0) < 3

    def schedule_retry(self, task_id: str, delay_seconds: float = None):
        """安排任務重試 - 🔧 修復：線程安全"""
        with self.lock:
            if delay_seconds is None:
                # 指數回退策略
                retry_count = self.retry_info.get(task_id, {}).get('count', 0)
                delay_seconds = min(2 ** retry_count, 30)  # 最多30秒

            retry_info = self.retry_info.get(task_id, {'count': 0})
            retry_info['count'] += 1
            retry_info['next_retry'] = time.time() + delay_seconds
            retry_info['delay'] = delay_seconds
            self.retry_info[task_id] = retry_info

            logger.info(f"⏰ 任務 {task_id} 安排重試，延遲 {delay_seconds} 秒")

    def is_ready_for_retry(self, task_id: str) -> bool:
        """檢查任務是否準備好重試 - 🔧 修復：線程安全"""
        with self.lock:
            retry_info = self.retry_info.get(task_id)
            if not retry_info:
                return False

            return time.time() >= retry_info.get('next_retry', 0)

    def clear_retry_info(self, task_id: str):
        """清除重試信息 - 🔧 修復：線程安全"""
        with self.lock:
            if task_id in self.retry_info:
                del self.retry_info[task_id]

    def get_lock_status(self) -> Dict:
        """獲取鎖狀態 - 線程安全"""
        with self.lock:
            return {
                'active_locks': len(self.file_locks),
                'locked_files': list(self.file_locks.keys()),
                'retry_tasks': len(self.retry_info)
            }