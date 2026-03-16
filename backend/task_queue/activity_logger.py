"""
活動日誌記錄器 - 記錄使用者 IP 的操作日誌

功能：
- append-only 模式
- 每日一個日誌檔案
- 不儲存敏感內容（音檔、摘要結果、Email 等）
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from utils.timezone_utils import now_taipei

logger = logging.getLogger(__name__)


class ActivityLogger:
    """
    活動日誌記錄器

    記錄使用者操作行為，用於審計和統計分析。
    不儲存任何敏感資料（音檔內容、AI 摘要、Email 等）。
    """

    def __init__(self, log_dir: str = None):
        """
        初始化活動日誌記錄器

        Args:
            log_dir: 日誌目錄路徑，預設使用配置檔中的 ACTIVITY_LOG_DIR
        """
        if log_dir is None:
            from config import config
            log_dir = config.ACTIVITY_LOG_DIR
        self.log_dir = log_dir
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        """確保日誌目錄存在"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            logger.info(f"📁 創建活動日誌目錄: {self.log_dir}")

    def _get_log_file_path(self) -> str:
        """獲取今日日誌檔案路徑"""
        date_str = now_taipei().strftime('%Y-%m-%d')
        return os.path.join(self.log_dir, f"activity_{date_str}.log")

    def log_activity(
        self,
        ip_address: str,
        action: str,
        task_id: str,
        task_type: str = None,
        file_size: int = None,
        status: str = None,
        error: str = None,
        processing_time: float = None
    ):
        """
        記錄活動日誌

        Args:
            ip_address: 使用者 IP 地址
            action: 操作類型 (upload, start, complete, fail, cancel)
            task_id: 任務 ID
            task_type: 任務類型 (audio_processing, text_processing)
            file_size: 檔案大小（bytes，僅 upload 時記錄）
            status: 結果狀態 (success, failed, cancelled)
            error: 錯誤訊息（僅失敗時記錄，限 200 字元）
            processing_time: 處理時間（秒，僅完成時記錄）
        """
        log_entry = {
            'timestamp': now_taipei().isoformat(),
            'ip_address': ip_address or 'unknown',
            'action': action,
            'task_id': task_id
        }

        # 可選欄位
        if task_type:
            log_entry['task_type'] = task_type
        if file_size is not None:
            log_entry['file_size'] = file_size
        if status:
            log_entry['status'] = status
        if error:
            # 限制錯誤訊息長度，避免日誌過大
            log_entry['error'] = error[:200] if len(error) > 200 else error
        if processing_time is not None:
            log_entry['processing_time'] = round(processing_time, 2)

        # Append 寫入日誌
        try:
            log_file = self._get_log_file_path()
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            logger.debug(f"📝 活動已記錄: {action} - {task_id}")
        except Exception as e:
            logger.error(f"❌ 記錄活動失敗: {e}")

    def cleanup_old_logs(self, max_age_days: int = 30):
        """
        清理舊日誌檔案

        Args:
            max_age_days: 保留天數，預設 30 天
        """
        try:
            if not os.path.exists(self.log_dir):
                return

            current_time = now_taipei()
            cleanup_count = 0

            for filename in os.listdir(self.log_dir):
                if not filename.startswith('activity_') or not filename.endswith('.log'):
                    continue

                filepath = os.path.join(self.log_dir, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                age_days = (current_time.replace(tzinfo=None) - file_time).days

                if age_days > max_age_days:
                    os.remove(filepath)
                    cleanup_count += 1

            if cleanup_count > 0:
                logger.info(f"🧹 清理了 {cleanup_count} 個舊日誌檔案")

        except Exception as e:
            logger.error(f"❌ 清理舊日誌失敗: {e}")

    def get_log_stats(self) -> Dict:
        """
        獲取日誌統計資訊

        Returns:
            包含日誌檔案數量和總大小的字典
        """
        try:
            if not os.path.exists(self.log_dir):
                return {'total_files': 0, 'total_size': 0, 'log_dir': self.log_dir}

            total_files = 0
            total_size = 0

            for filename in os.listdir(self.log_dir):
                if filename.startswith('activity_') and filename.endswith('.log'):
                    filepath = os.path.join(self.log_dir, filename)
                    total_files += 1
                    total_size += os.path.getsize(filepath)

            return {
                'total_files': total_files,
                'total_size': total_size,
                'log_dir': self.log_dir
            }
        except Exception as e:
            logger.error(f"❌ 獲取日誌統計失敗: {e}")
            return {'total_files': 0, 'total_size': 0, 'log_dir': self.log_dir}
