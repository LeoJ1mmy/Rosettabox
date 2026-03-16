"""
快取管理器 - LRU 快取實現（執行緒安全）
"""
import hashlib
import json
# 🔒 安全修復：移除 pickle 導入（不安全的序列化）
# import pickle  # 已移除 - 使用 JSON 替代
import time
import threading
from typing import Any, Optional, Union
from functools import wraps
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)

class LRUCache:
    """最近最少使用（LRU）快取實現"""
    
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        """
        Args:
            max_size: 最大快取項目數
            ttl: 快取存活時間（秒）
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache = OrderedDict()
        self.timestamps = {}
        self._lock = threading.Lock()
        
    def get(self, key: str) -> Optional[Any]:
        """獲取快取值（執行緒安全）"""
        with self._lock:
            if key not in self.cache:
                return None
            
            # 檢查是否過期
            if time.time() - self.timestamps[key] > self.ttl:
                del self.cache[key]
                del self.timestamps[key]
                return None
            
            # 移到最後（最近使用）
            self.cache.move_to_end(key)
            return self.cache[key]
    
    def set(self, key: str, value: Any):
        """設置快取值（執行緒安全）"""
        with self._lock:
            # 如果已存在，先刪除
            if key in self.cache:
                del self.cache[key]
            
            # 檢查大小限制
            if len(self.cache) >= self.max_size:
                # 刪除最舊的項目
                oldest = next(iter(self.cache))
                del self.cache[oldest]
                del self.timestamps[oldest]
            
            # 添加新項目
            self.cache[key] = value
            self.timestamps[key] = time.time()
    
    def clear(self):
        """清空快取（執行緒安全）"""
        with self._lock:
            self.cache.clear()
            self.timestamps.clear()
    
    def size(self) -> int:
        """獲取快取大小"""
        with self._lock:
            return len(self.cache)
    
    def stats(self) -> dict:
        """獲取快取統計"""
        with self._lock:
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'ttl': self.ttl
            }

class CacheManager:
    """統一的快取管理器"""
    
    def __init__(self):
        # 不同類型的快取
        self.audio_cache = LRUCache(max_size=50, ttl=3600)  # 音頻處理結果
        self.text_cache = LRUCache(max_size=100, ttl=7200)  # 文字處理結果
        self.model_cache = LRUCache(max_size=10, ttl=1800)  # 模型推理結果
        
    def get_cache_key(self, *args, **kwargs) -> str:
        """生成快取鍵"""
        # 將參數轉換為字符串並生成 hash
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def cache_audio_result(self, func):
        """音頻處理結果快取裝飾器"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = self.get_cache_key(func.__name__, *args, **kwargs)
            
            # 嘗試從快取獲取
            cached = self.audio_cache.get(cache_key)
            if cached is not None:
                logger.info(f"音頻快取命中: {func.__name__}")
                return cached
            
            # 執行函數
            result = func(*args, **kwargs)
            
            # 存入快取
            self.audio_cache.set(cache_key, result)
            return result
        
        return wrapper
    
    def cache_text_result(self, func):
        """文字處理結果快取裝飾器"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = self.get_cache_key(func.__name__, *args, **kwargs)
            
            # 嘗試從快取獲取
            cached = self.text_cache.get(cache_key)
            if cached is not None:
                logger.info(f"文字快取命中: {func.__name__}")
                return cached
            
            # 執行函數
            result = func(*args, **kwargs)
            
            # 存入快取
            self.text_cache.set(cache_key, result)
            return result
        
        return wrapper
    
    def clear_all(self):
        """清空所有快取"""
        self.audio_cache.clear()
        self.text_cache.clear()
        self.model_cache.clear()
        logger.info("所有快取已清空")
    
    def get_stats(self) -> dict:
        """獲取快取統計信息"""
        return {
            'audio_cache': self.audio_cache.stats(),
            'text_cache': self.text_cache.stats(),
            'model_cache': self.model_cache.stats()
        }

# 單例模式
cache_manager = CacheManager()