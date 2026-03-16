"""
批次結果緩存服務 - 專門處理多檔案批次任務的結果緩存
當使用者上傳多個音頻檔案時，處理完成的結果會被緩存，直到整批任務完成後一併顯示

🔧 修復：避免在持有鎖時執行 I/O 操作
"""
import json
import os
import logging
import time
import tempfile
import shutil
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)


class BatchCacheService:
    """批次結果緩存服務 - 🔧 修復：I/O 操作在鎖外執行"""

    def __init__(self, cache_dir: str = "/tmp/batch_cache"):
        self.cache_dir = cache_dir
        self.lock = threading.Lock()  # 🔧 修復：改用普通 Lock，避免隱藏問題

        # 內存緩存，減少磁盤 I/O
        self._memory_cache: Dict[str, Dict] = {}
        self._cache_dirty: Dict[str, bool] = {}  # 標記哪些緩存需要寫入磁盤

        # 創建緩存目錄
        os.makedirs(cache_dir, exist_ok=True)

        # 緩存設定
        self.cache_ttl = 24 * 60 * 60  # 24小時過期
        self.cleanup_interval = 60 * 60  # 每小時清理一次

        # 啟動定期清理
        self._start_cleanup_timer()

        logger.info(f"批次緩存服務初始化完成，緩存目錄: {cache_dir}")
    
    def _get_cache_file_path(self, batch_id: str) -> str:
        """獲取緩存文件路徑"""
        return os.path.join(self.cache_dir, f"batch_{batch_id}.json")

    def _write_cache_file_atomic(self, batch_id: str, cache_data: Dict) -> bool:
        """
        🔧 新增：原子寫入緩存文件（在鎖外調用）

        使用臨時文件 + 重命名實現原子寫入，避免損壞
        """
        cache_file = self._get_cache_file_path(batch_id)
        try:
            # 寫入臨時文件
            fd, temp_path = tempfile.mkstemp(
                suffix='.json',
                prefix=f'batch_{batch_id}_',
                dir=self.cache_dir
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                # 原子重命名
                shutil.move(temp_path, cache_file)
                return True
            except Exception:
                # 清理臨時文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise
        except Exception as e:
            logger.error(f"❌ 寫入緩存文件失敗: {batch_id} - {e}")
            return False

    def _read_cache_file(self, batch_id: str) -> Optional[Dict]:
        """
        🔧 新增：讀取緩存文件（在鎖外調用）
        """
        cache_file = self._get_cache_file_path(batch_id)
        if not os.path.exists(cache_file):
            return None
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ 讀取緩存文件失敗: {batch_id} - {e}")
            return None

    def _start_cleanup_timer(self):
        """啟動定期清理過期緩存"""
        def cleanup_worker():
            while True:
                try:
                    self.cleanup_expired_cache()
                    time.sleep(self.cleanup_interval)
                except Exception as e:
                    logger.error(f"定期清理失敗: {e}")
                    time.sleep(self.cleanup_interval)

        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()

    def create_batch_cache(self, batch_id: str, user_id: str, total_files: int,
                          config: Dict[str, Any] = None) -> bool:
        """創建批次緩存條目 - 🔧 修復：I/O 在鎖外執行"""
        cache_data = {
            'batch_id': batch_id,
            'user_id': user_id,
            'total_files': total_files,
            'completed_files': 0,
            'failed_files': 0,
            'files': [],
            'config': config or {},
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'status': 'processing'
        }

        # 🔧 修復：先更新內存緩存（在鎖內），再寫入磁盤（在鎖外）
        with self.lock:
            self._memory_cache[batch_id] = cache_data.copy()

        # I/O 在鎖外執行
        success = self._write_cache_file_atomic(batch_id, cache_data)
        if success:
            logger.info(f"✅ 創建批次緩存: {batch_id}, 總檔案數: {total_files}")
        return success

    def add_file_result(self, batch_id: str, file_result: Dict[str, Any]) -> bool:
        """添加單個檔案的處理結果 - 🔧 修復：I/O 在鎖外執行"""
        cache_data = None
        total_processed = 0

        # 🔧 修復：在鎖內更新內存緩存
        with self.lock:
            # 優先從內存緩存獲取
            if batch_id in self._memory_cache:
                cache_data = self._memory_cache[batch_id]
            else:
                # 從磁盤載入到內存（這裡的 I/O 無法避免，但只在首次訪問時發生）
                cache_data = self._read_cache_file(batch_id)
                if cache_data:
                    self._memory_cache[batch_id] = cache_data

            if not cache_data:
                logger.error(f"❌ 批次緩存不存在: {batch_id}")
                return False

            # 添加檔案結果
            cache_data['files'].append(file_result)

            # 更新統計
            if 'error' in file_result:
                cache_data['failed_files'] += 1
            else:
                cache_data['completed_files'] += 1

            cache_data['updated_at'] = datetime.now().isoformat()

            # 檢查是否全部完成
            total_processed = cache_data['completed_files'] + cache_data['failed_files']
            if total_processed >= cache_data['total_files']:
                cache_data['status'] = 'completed'
                logger.info(f"🎉 批次處理完成: {batch_id}")

            # 複製一份用於寫入磁盤
            cache_data_copy = cache_data.copy()
            cache_data_copy['files'] = list(cache_data['files'])  # 深拷貝列表

        # 🔧 修復：I/O 在鎖外執行
        success = self._write_cache_file_atomic(batch_id, cache_data_copy)
        if success:
            logger.info(f"📁 添加檔案結果: {batch_id}, 進度: {total_processed}/{cache_data_copy['total_files']}")
        return success

    def get_batch_result(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """獲取批次處理結果 - 🔧 修復：優先從內存獲取"""
        with self.lock:
            # 優先從內存緩存獲取
            if batch_id in self._memory_cache:
                # 返回副本，避免外部修改
                return self._memory_cache[batch_id].copy()

        # 內存中沒有，從磁盤載入（在鎖外）
        cache_data = self._read_cache_file(batch_id)
        if cache_data:
            # 更新內存緩存
            with self.lock:
                self._memory_cache[batch_id] = cache_data
            return cache_data.copy()

        return None
    
    def is_batch_completed(self, batch_id: str) -> bool:
        """檢查批次是否已完成"""
        cache_data = self.get_batch_result(batch_id)
        return cache_data and cache_data.get('status') == 'completed'
    
    def get_batch_progress(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """獲取批次處理進度"""
        cache_data = self.get_batch_result(batch_id)
        if not cache_data:
            return None
        
        total_files = cache_data['total_files']
        completed_files = cache_data['completed_files']
        failed_files = cache_data['failed_files']
        processing_files = total_files - completed_files - failed_files
        
        return {
            'batch_id': batch_id,
            'total_files': total_files,
            'completed_files': completed_files,
            'failed_files': failed_files,
            'processing_files': processing_files,
            'progress_percentage': int((completed_files + failed_files) * 100 / total_files) if total_files > 0 else 0,
            'status': cache_data['status']
        }
    
    def cleanup_expired_cache(self):
        """清理過期的緩存條目 - 🔧 修復：I/O 在鎖外執行"""
        current_time = datetime.now()
        files_to_delete = []
        batch_ids_to_remove = []

        # 🔧 修復：收集要刪除的文件（不持有鎖時執行 I/O）
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.startswith('batch_') and filename.endswith('.json'):
                    cache_file = os.path.join(self.cache_dir, filename)
                    batch_id = filename[6:-5]  # 提取 batch_id

                    try:
                        cache_data = self._read_cache_file(batch_id)
                        if cache_data:
                            created_at = datetime.fromisoformat(cache_data['created_at'])
                            if current_time - created_at > timedelta(seconds=self.cache_ttl):
                                files_to_delete.append(cache_file)
                                batch_ids_to_remove.append(batch_id)
                        else:
                            # 文件損壞，也刪除
                            files_to_delete.append(cache_file)
                            batch_ids_to_remove.append(batch_id)

                    except Exception as e:
                        logger.warning(f"⚠️ 檢查緩存文件失敗: {filename} - {e}")
                        files_to_delete.append(cache_file)
                        batch_ids_to_remove.append(batch_id)

        except Exception as e:
            logger.error(f"❌ 列舉緩存目錄失敗: {e}")
            return

        # 🔧 修復：在鎖內更新內存緩存
        if batch_ids_to_remove:
            with self.lock:
                for batch_id in batch_ids_to_remove:
                    self._memory_cache.pop(batch_id, None)

        # 🔧 修復：在鎖外刪除文件
        cleaned_count = 0
        for cache_file in files_to_delete:
            try:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    cleaned_count += 1
                    logger.info(f"🗑️ 清理過期緩存: {os.path.basename(cache_file)}")
            except Exception as e:
                logger.warning(f"⚠️ 刪除緩存文件失敗: {cache_file} - {e}")

        if cleaned_count > 0:
            logger.info(f"🧹 批次緩存清理完成，清理了 {cleaned_count} 個過期條目")

    def delete_batch_cache(self, batch_id: str) -> bool:
        """刪除特定批次的緩存 - 🔧 修復：I/O 在鎖外執行"""
        # 🔧 修復：先從內存緩存移除
        with self.lock:
            self._memory_cache.pop(batch_id, None)

        # 🔧 修復：在鎖外刪除文件
        try:
            cache_file = self._get_cache_file_path(batch_id)
            if os.path.exists(cache_file):
                os.remove(cache_file)
                logger.info(f"🗑️ 刪除批次緩存: {batch_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ 刪除批次緩存失敗: {batch_id} - {e}")
            return False

    def list_user_batches(self, user_id: str) -> List[Dict[str, Any]]:
        """列出用戶的所有批次任務 - 🔧 修復：優先從內存獲取"""
        user_batches = []

        # 🔧 修復：先從內存緩存獲取
        with self.lock:
            for batch_id, cache_data in self._memory_cache.items():
                if cache_data.get('user_id') == user_id:
                    batch_summary = {
                        'batch_id': cache_data['batch_id'],
                        'total_files': cache_data['total_files'],
                        'completed_files': cache_data['completed_files'],
                        'failed_files': cache_data['failed_files'],
                        'status': cache_data['status'],
                        'created_at': cache_data['created_at'],
                        'updated_at': cache_data['updated_at']
                    }
                    user_batches.append(batch_summary)
            memory_batch_ids = set(self._memory_cache.keys())

        # 🔧 修復：補充磁盤上但不在內存中的批次（在鎖外）
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.startswith('batch_') and filename.endswith('.json'):
                    batch_id = filename[6:-5]

                    # 跳過已在內存中的
                    if batch_id in memory_batch_ids:
                        continue

                    try:
                        cache_data = self._read_cache_file(batch_id)
                        if cache_data and cache_data.get('user_id') == user_id:
                            batch_summary = {
                                'batch_id': cache_data['batch_id'],
                                'total_files': cache_data['total_files'],
                                'completed_files': cache_data['completed_files'],
                                'failed_files': cache_data['failed_files'],
                                'status': cache_data['status'],
                                'created_at': cache_data['created_at'],
                                'updated_at': cache_data['updated_at']
                            }
                            user_batches.append(batch_summary)

                    except Exception as e:
                        logger.warning(f"⚠️ 讀取批次緩存失敗: {filename} - {e}")

        except Exception as e:
            logger.error(f"❌ 列出用戶批次失敗: {user_id} - {e}")

        # 按創建時間排序（最新的在前）
        user_batches.sort(key=lambda x: x['created_at'], reverse=True)

        return user_batches

# 單例實例
batch_cache_service = BatchCacheService()