"""
文件清理工具 - 自動刪除處理完成的音視頻文件
"""
import os
import logging
import time
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class FileCleanupManager:
    """文件清理管理器"""
    
    # 支援的音視頻文件格式
    AUDIO_VIDEO_EXTENSIONS = {
        '.mp3', '.mp4', '.wav', '.m4a', '.aac', '.ogg', '.flac', 
        '.wma', '.avi', '.mov', '.mkv', '.webm', '.3gp', '.amr'
    }
    
    def __init__(self, upload_folder: str):
        """
        初始化文件清理管理器
        
        Args:
            upload_folder: 上傳文件夾路徑
        """
        self.upload_folder = upload_folder
        self.cleanup_enabled = True  # 預設啟用清理功能
        
    def is_audio_video_file(self, filename: str) -> bool:
        """
        檢查是否為音視頻文件
        
        Args:
            filename: 文件名
            
        Returns:
            bool: 是否為音視頻文件
        """
        if not filename:
            return False
            
        file_ext = Path(filename).suffix.lower()
        return file_ext in self.AUDIO_VIDEO_EXTENSIONS
    
    def get_file_path(self, filename: str) -> Optional[str]:
        """
        獲取文件的完整路徑
        
        Args:
            filename: 文件名（可能是相對或絕對路徑）
            
        Returns:
            str or None: 文件的完整路徑，如果文件不存在返回 None
        """
        if not filename:
            return None
            
        # 如果是絕對路徑，直接使用
        if os.path.isabs(filename):
            filepath = filename
        else:
            # 如果是相對路徑，從上傳目錄開始
            filepath = os.path.join(self.upload_folder, filename)
        
        # 檢查文件是否存在
        if os.path.exists(filepath):
            return filepath
        else:
            logger.warning(f"文件不存在: {filepath}")
            return None
    
    def cleanup_file(self, filename: str, task_id: str = None) -> bool:
        """
        清理單個文件
        
        Args:
            filename: 要清理的文件名
            task_id: 任務ID（用於日誌記錄）
            
        Returns:
            bool: 清理是否成功
        """
        if not self.cleanup_enabled:
            logger.debug("文件清理功能已禁用，跳過清理")
            return False
            
        if not filename:
            logger.warning("文件名為空，無法清理")
            return False
        
        # 檢查是否為音視頻文件
        if not self.is_audio_video_file(filename):
            logger.debug(f"非音視頻文件，跳過清理: {filename}")
            return False
        
        # 獲取文件路徑
        filepath = self.get_file_path(filename)
        if not filepath:
            return False
        
        try:
            # 獲取文件信息（用於日誌）
            file_size = os.path.getsize(filepath)
            file_size_mb = file_size / (1024 * 1024)
            
            # 刪除文件
            os.remove(filepath)
            
            log_prefix = f"任務 {task_id}: " if task_id else ""
            logger.info(f"🗑️ {log_prefix}已清理音視頻文件: {filename} ({file_size_mb:.2f} MB)")
            return True
            
        except OSError as e:
            logger.error(f"❌ 清理文件失敗: {filename} - {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ 清理文件時發生未知錯誤: {filename} - {str(e)}")
            return False
    
    def cleanup_task_files(self, task: Dict) -> Dict[str, bool]:
        """
        清理任務相關的所有文件
        
        Args:
            task: 任務字典，包含文件信息
            
        Returns:
            Dict[str, bool]: 清理結果，key為文件名，value為是否清理成功
        """
        cleanup_results = {}
        task_id = task.get('task_id', 'unknown')
        
        # 獲取主要文件
        filename = task.get('filename')
        if filename:
            cleanup_results[filename] = self.cleanup_file(filename, task_id)
        
        # 獲取任務數據中的其他文件
        task_data = task.get('task_data', {})
        if isinstance(task_data, dict):
            # 檢查是否有其他文件字段
            for key in ['file_path', 'filePath', 'additional_files']:
                if key in task_data:
                    additional_file = task_data[key]
                    if isinstance(additional_file, str):
                        cleanup_results[additional_file] = self.cleanup_file(additional_file, task_id)
                    elif isinstance(additional_file, list):
                        for file in additional_file:
                            if isinstance(file, str):
                                cleanup_results[file] = self.cleanup_file(file, task_id)
        
        return cleanup_results
    
    def enable_cleanup(self):
        """啟用文件清理功能"""
        self.cleanup_enabled = True
        logger.info("✅ 文件清理功能已啟用")
    
    def disable_cleanup(self):
        """禁用文件清理功能"""
        self.cleanup_enabled = False
        logger.info("⚠️ 文件清理功能已禁用")
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> Dict:
        """
        清理超過指定時間的舊文件

        Args:
            max_age_hours: 文件最大保留時間（小時），默認 24 小時

        Returns:
            Dict: 清理結果統計
        """
        if not self.cleanup_enabled:
            logger.debug("文件清理功能已禁用，跳過舊文件清理")
            return {'cleaned_count': 0, 'cleaned_size_mb': 0, 'errors': 0}

        if not os.path.exists(self.upload_folder):
            logger.warning(f"上傳目錄不存在: {self.upload_folder}")
            return {'cleaned_count': 0, 'cleaned_size_mb': 0, 'errors': 0}

        cleaned_count = 0
        cleaned_size = 0
        errors = 0
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        try:
            for filename in os.listdir(self.upload_folder):
                filepath = os.path.join(self.upload_folder, filename)

                if not os.path.isfile(filepath):
                    continue

                # 檢查文件年齡
                file_mtime = os.path.getmtime(filepath)
                file_age = current_time - file_mtime

                if file_age > max_age_seconds:
                    try:
                        file_size = os.path.getsize(filepath)
                        os.remove(filepath)
                        cleaned_count += 1
                        cleaned_size += file_size
                        logger.info(f"🗑️ 清理過期文件: {filename} (年齡: {file_age/3600:.1f}小時)")
                    except OSError as e:
                        logger.error(f"❌ 清理文件失敗: {filename} - {e}")
                        errors += 1

        except Exception as e:
            logger.error(f"❌ 清理舊文件時發生錯誤: {e}")
            errors += 1

        result = {
            'cleaned_count': cleaned_count,
            'cleaned_size_mb': cleaned_size / (1024 * 1024),
            'errors': errors
        }

        if cleaned_count > 0:
            logger.info(f"🧹 舊文件清理完成: 刪除 {cleaned_count} 個文件，釋放 {result['cleaned_size_mb']:.2f} MB")

        return result

    def get_cleanup_stats(self, upload_folder: str = None) -> Dict:
        """
        獲取清理統計信息
        
        Args:
            upload_folder: 要統計的文件夾（可選，默認使用實例的上傳文件夾）
            
        Returns:
            Dict: 統計信息
        """
        folder = upload_folder or self.upload_folder
        
        if not os.path.exists(folder):
            return {
                'total_files': 0,
                'audio_video_files': 0,
                'total_size_mb': 0,
                'audio_video_size_mb': 0
            }
        
        total_files = 0
        audio_video_files = 0
        total_size = 0
        audio_video_size = 0
        
        try:
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.isfile(filepath):
                    total_files += 1
                    file_size = os.path.getsize(filepath)
                    total_size += file_size
                    
                    if self.is_audio_video_file(filename):
                        audio_video_files += 1
                        audio_video_size += file_size
        
        except Exception as e:
            logger.error(f"❌ 獲取清理統計信息失敗: {str(e)}")
        
        return {
            'total_files': total_files,
            'audio_video_files': audio_video_files,
            'total_size_mb': total_size / (1024 * 1024),
            'audio_video_size_mb': audio_video_size / (1024 * 1024)
        }


def cleanup_after_email(task: Dict, email_success: bool) -> Dict[str, bool]:
    """
    在Email發送後清理文件的便捷函數
    
    Args:
        task: 任務字典
        email_success: Email是否發送成功
        
    Returns:
        Dict[str, bool]: 清理結果
    """
    from config import config
    
    # 只有在Email發送成功後才清理文件
    if not email_success:
        logger.info("Email發送失敗，跳過文件清理")
        return {}
    
    # 創建文件清理管理器並執行清理
    cleaner = FileCleanupManager(config.UPLOAD_FOLDER)
    cleanup_results = cleaner.cleanup_task_files(task)
    
    # 記錄清理統計
    successful_cleanups = sum(1 for success in cleanup_results.values() if success)
    total_files = len(cleanup_results)
    
    if total_files > 0:
        task_id = task.get('task_id', 'unknown')
        logger.info(f"📊 任務 {task_id} 文件清理完成: {successful_cleanups}/{total_files} 個文件成功清理")
    
    return cleanup_results