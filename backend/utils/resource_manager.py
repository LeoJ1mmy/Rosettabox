"""
資源管理器 - 優化的資源清理和管理
"""
import gc
import os
import torch
import psutil
import logging
import tempfile
from typing import Dict, Any
from functools import lru_cache
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class ResourceManager:
    """統一的資源管理器"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._cache = {}
        
    def cleanup_memory(self) -> Dict[str, Any]:
        """優化的記憶體清理 - 避免過度清理"""
        stats = {}
        
        # 1. 單次垃圾回收（而非3次）
        collected = gc.collect()
        stats['gc_collected'] = collected
        
        # 2. GPU 記憶體清理（如果可用）
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            stats['gpu_memory'] = {
                'allocated_gb': torch.cuda.memory_allocated() / 1024**3,
                'reserved_gb': torch.cuda.memory_reserved() / 1024**3
            }
        
        # 3. 系統記憶體統計
        process = psutil.Process()
        stats['system_memory_gb'] = process.memory_info().rss / 1024**3
        
        logger.info(f"記憶體清理完成: {stats}")
        return stats
    
    async def cleanup_temp_files_async(self, extensions=None) -> Dict[str, Any]:
        """異步清理臨時文件"""
        if extensions is None:
            extensions = ['.wav', '.mp3', '.m4a', '.flac', '.ogg', '.tmp']
        
        temp_dirs = ['/tmp', tempfile.gettempdir(), 'uploads', 'backend/uploads']
        stats = {'files_removed': 0, 'space_freed_mb': 0}
        
        tasks = []
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                task = self._cleanup_directory_async(temp_dir, extensions)
                tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        for result in results:
            stats['files_removed'] += result['files']
            stats['space_freed_mb'] += result['size_mb']
        
        logger.info(f"臨時文件清理: {stats}")
        return stats
    
    async def _cleanup_directory_async(self, directory, extensions):
        """異步清理單個目錄"""
        files_removed = 0
        space_freed = 0
        
        def cleanup():
            nonlocal files_removed, space_freed
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if any(file.endswith(ext) for ext in extensions):
                        file_path = os.path.join(root, file)
                        try:
                            size = os.path.getsize(file_path)
                            os.unlink(file_path)
                            files_removed += 1
                            space_freed += size
                        except:
                            pass
            return {'files': files_removed, 'size_mb': space_freed / (1024 * 1024)}
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, cleanup)
    
    def get_system_stats(self) -> Dict[str, Any]:
        """獲取系統資源統計"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        stats = {
            'cpu_percent': cpu_percent,
            'memory': {
                'total_gb': memory.total / 1024**3,
                'available_gb': memory.available / 1024**3,
                'percent': memory.percent
            }
        }
        
        if torch.cuda.is_available():
            stats['gpu'] = {
                'available': True,
                'memory_allocated_gb': torch.cuda.memory_allocated() / 1024**3,
                'memory_reserved_gb': torch.cuda.memory_reserved() / 1024**3
            }
        else:
            stats['gpu'] = {'available': False}
        
        return stats

# 單例模式
resource_manager = ResourceManager()