"""
Email 重試管理器 - 記憶體中的 email 任務暫存和重試機制

功能：
- 記憶體中暫存 email 任務（不持久化，符合隱私要求）
- 指數退避重試（最多 3 次，間隔 5s, 15s）
- 5 分鐘自動清理過期任務
- 重試全部失敗後發送「發送失敗通知」
- 線程安全
"""
import threading
import time
import uuid
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EmailTaskStatus(Enum):
    """Email 任務狀態"""
    PENDING = "pending"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class EmailTask:
    """Email 任務數據結構"""
    task_id: str
    email_type: str  # 'processing_result', 'error', 'batch', 'notification', 'delivery_failure'
    to_email: str
    send_func: Callable  # 實際發送函數
    send_args: Dict[str, Any]  # 發送函數的參數
    created_at: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: float = 0
    status: EmailTaskStatus = EmailTaskStatus.PENDING
    last_error: str = ""
    original_task_info: Dict = field(default_factory=dict)  # 保存原始任務信息用於失敗通知


class EmailRetryManager:
    """
    Email 重試管理器

    功能：
    - 記憶體中暫存 email 任務
    - 指數退避重試（2次重試，間隔 5s, 15s）
    - 5 分鐘自動清理過期任務
    - 重試全部失敗後發送「發送失敗通知」
    - 線程安全
    """

    # 配置常數
    SMTP_TIMEOUT = 30  # 秒
    MAX_RETRIES = 3  # 首次 + 2次重試
    BASE_DELAY = 5  # 基礎延遲秒數
    MAX_TASK_AGE = 300  # 5 分鐘 = 300 秒
    CLEANUP_INTERVAL = 60  # 清理檢查間隔

    def __init__(self):
        self._tasks: Dict[str, EmailTask] = {}
        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()

        # 啟動背景清理線程
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="EmailCleanupThread",
            daemon=True
        )
        self._cleanup_thread.start()

        logger.info("📧 Email 重試管理器已初始化")

    def submit_email(
        self,
        email_type: str,
        to_email: str,
        send_func: Callable,
        send_args: Dict[str, Any],
        original_task_info: Dict = None
    ) -> str:
        """
        提交 email 任務

        Args:
            email_type: email 類型
            to_email: 收件人
            send_func: 發送函數
            send_args: 發送參數
            original_task_info: 原始任務信息（用於失敗通知）

        Returns:
            email_task_id
        """
        task_id = str(uuid.uuid4())[:8]

        task = EmailTask(
            task_id=task_id,
            email_type=email_type,
            to_email=to_email,
            send_func=send_func,
            send_args=send_args,
            original_task_info=original_task_info or {}
        )

        with self._lock:
            self._tasks[task_id] = task

        logger.info(f"📧 Email 任務已暫存: {task_id} ({email_type} -> {to_email})")
        return task_id

    def execute_with_retry(self, task_id: str) -> bool:
        """
        執行 email 發送（帶重試）

        Returns:
            True = 最終成功, False = 最終失敗
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                logger.warning(f"📧 找不到 email 任務: {task_id}")
                return False

        while task.retry_count < task.max_retries:
            # 檢查是否需要等待重試時間
            if task.next_retry_at > 0:
                wait_time = task.next_retry_at - time.time()
                if wait_time > 0:
                    logger.debug(f"📧 等待重試: {task_id}, {wait_time:.1f}s")
                    time.sleep(wait_time)

            # 嘗試發送
            try:
                task.status = EmailTaskStatus.RETRYING if task.retry_count > 0 else EmailTaskStatus.PENDING

                logger.info(f"📧 嘗試發送 email: {task_id} (第 {task.retry_count + 1}/{task.max_retries} 次)")
                success = task.send_func(**task.send_args)

                if success:
                    task.status = EmailTaskStatus.SUCCESS
                    logger.info(f"📧 Email 發送成功: {task_id} (嘗試 {task.retry_count + 1}/{task.max_retries})")
                    self._remove_task(task_id)
                    return True
                else:
                    raise Exception("發送函數返回 False")

            except Exception as e:
                task.retry_count += 1
                task.last_error = str(e)

                if task.retry_count < task.max_retries:
                    # 指數退避：5s, 15s (5 * 3^0, 5 * 3^1)
                    delay = self.BASE_DELAY * (3 ** (task.retry_count - 1))
                    task.next_retry_at = time.time() + delay
                    logger.warning(
                        f"📧 Email 發送失敗，將在 {delay}s 後重試: "
                        f"{task_id} (嘗試 {task.retry_count}/{task.max_retries}) - {e}"
                    )
                else:
                    task.status = EmailTaskStatus.FAILED
                    logger.error(
                        f"📧 Email 發送最終失敗: {task_id} "
                        f"(已嘗試 {task.retry_count} 次) - {e}"
                    )

        # 所有重試失敗，發送失敗通知
        self._send_delivery_failure_notification(task)
        self._remove_task(task_id)
        return False

    def _send_delivery_failure_notification(self, failed_task: EmailTask):
        """發送「郵件發送失敗」通知"""
        # 防止無限循環：不對「發送失敗通知」類型再發失敗通知
        if failed_task.email_type == 'delivery_failure':
            logger.warning(f"📧 跳過發送失敗通知的失敗通知（防止循環）")
            return

        try:
            from email_service import get_email_service
            service = get_email_service()

            if not service.is_enabled():
                logger.warning("📧 Email 服務未啟用，無法發送失敗通知")
                return

            # 構建失敗通知內容
            original_info = failed_task.original_task_info
            task_id = original_info.get('task_id', 'N/A')
            filename = original_info.get('filename', 'N/A')

            # 根據原始 email 類型決定描述
            type_descriptions = {
                'processing_result': '處理結果通知',
                'batch_processing_result': '批次處理結果通知',
                'error_notification': '錯誤通知',
                'notification': '通知郵件'
            }
            email_type_desc = type_descriptions.get(failed_task.email_type, failed_task.email_type)

            subject = f"郵件發送失敗通知 - {filename}"

            body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; padding: 24px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 20px; }}
        .content {{ padding: 24px; }}
        .info-box {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 16px; margin: 16px 0; }}
        .info-row {{ display: flex; margin: 8px 0; }}
        .info-label {{ font-weight: 600; color: #374151; min-width: 100px; }}
        .info-value {{ color: #6b7280; }}
        .error-box {{ background: #fee2e2; border-left: 4px solid #ef4444; padding: 12px 16px; margin: 16px 0; font-family: monospace; font-size: 13px; color: #991b1b; }}
        .footer {{ background: #f9fafb; padding: 16px 24px; text-align: center; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>郵件發送失敗通知</h1>
        </div>
        <div class="content">
            <p>您的 <strong>{email_type_desc}</strong> 未能成功發送，系統已嘗試 {failed_task.max_retries} 次。</p>

            <div class="info-box">
                <div class="info-row">
                    <span class="info-label">郵件類型：</span>
                    <span class="info-value">{email_type_desc}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">收件人：</span>
                    <span class="info-value">{failed_task.to_email}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">任務 ID：</span>
                    <span class="info-value">{task_id}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">檔案名稱：</span>
                    <span class="info-value">{filename}</span>
                </div>
            </div>

            <h3>錯誤詳情</h3>
            <div class="error-box">
                {failed_task.last_error}
            </div>

            <p>您的任務處理結果仍然保存在系統中。請檢查網路連接或稍後重新嘗試。如問題持續，請聯繫系統管理員。</p>
        </div>
        <div class="footer">
            RosettaBix 語音處理系統
        </div>
    </div>
</body>
</html>
"""

            # 直接發送（不走重試機制，避免循環）
            success = service.send_notification(
                to_email=failed_task.to_email,
                subject=subject,
                message=body
            )

            if success:
                logger.info(f"📧 已發送郵件發送失敗通知: {failed_task.to_email}")
            else:
                logger.error(f"📧 發送失敗通知也失敗了: {failed_task.to_email}")

        except Exception as e:
            logger.error(f"📧 發送失敗通知時出錯: {e}")

    def _remove_task(self, task_id: str):
        """從暫存中移除任務"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                logger.debug(f"📧 已移除 email 任務: {task_id}")

    def _cleanup_loop(self):
        """背景清理過期任務"""
        while not self._shutdown_event.is_set():
            try:
                self._cleanup_expired_tasks()
            except Exception as e:
                logger.error(f"📧 清理過期任務時出錯: {e}")

            self._shutdown_event.wait(self.CLEANUP_INTERVAL)

    def _cleanup_expired_tasks(self):
        """清理超過 5 分鐘的任務"""
        now = time.time()
        expired_tasks = []

        with self._lock:
            for task_id, task in list(self._tasks.items()):
                age = now - task.created_at
                if age > self.MAX_TASK_AGE:
                    expired_tasks.append((task_id, task))

        for task_id, task in expired_tasks:
            with self._lock:
                self._tasks.pop(task_id, None)
            logger.warning(
                f"📧 清理過期 email 任務: {task_id} "
                f"(類型: {task.email_type}, 存活: {self.MAX_TASK_AGE}s)"
            )

    def get_status(self) -> Dict:
        """獲取管理器狀態"""
        with self._lock:
            pending = sum(1 for t in self._tasks.values() if t.status == EmailTaskStatus.PENDING)
            retrying = sum(1 for t in self._tasks.values() if t.status == EmailTaskStatus.RETRYING)

            return {
                'total_tasks': len(self._tasks),
                'pending': pending,
                'retrying': retrying,
                'config': {
                    'smtp_timeout': self.SMTP_TIMEOUT,
                    'max_retries': self.MAX_RETRIES,
                    'base_delay': self.BASE_DELAY,
                    'max_task_age': self.MAX_TASK_AGE
                }
            }

    def shutdown(self):
        """關閉管理器"""
        logger.info("📧 正在關閉 Email 重試管理器...")
        self._shutdown_event.set()
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        logger.info("📧 Email 重試管理器已關閉")


# 全局單例
_email_retry_manager: Optional[EmailRetryManager] = None
_manager_lock = threading.Lock()


def get_email_retry_manager() -> EmailRetryManager:
    """獲取 Email 重試管理器單例"""
    global _email_retry_manager
    if _email_retry_manager is None:
        with _manager_lock:
            if _email_retry_manager is None:
                _email_retry_manager = EmailRetryManager()
    return _email_retry_manager
