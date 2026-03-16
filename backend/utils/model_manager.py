"""
模型管理器 - 懶加載和快取機制（執行緒安全）
"""
import logging
import threading
from typing import Dict, Any, Optional
from functools import lru_cache
import torch
import gc

logger = logging.getLogger(__name__)

class ModelManager:
    """統一的模型管理器 - 實現懶加載和快取"""
    
    def __init__(self):
        self._models = {}
        self._model_configs = {}
        self._max_cache_size = 3  # 最多同時快取3個模型
        self._lock = threading.Lock()
        
    def register_model(self, name: str, loader_func, config: Optional[Dict] = None):
        """註冊模型加載器（執行緒安全）"""
        with self._lock:
            self._model_configs[name] = {
                'loader': loader_func,
                'config': config or {},
                'loaded': False
            }
        logger.info(f"註冊模型: {name}")
    
    def get_model(self, name: str):
        """懶加載獲取模型（執行緒安全）"""
        with self._lock:
            if name not in self._model_configs:
                raise ValueError(f"模型 {name} 未註冊")
            
            # 檢查是否已加載
            if name in self._models:
                logger.debug(f"從快取返回模型: {name}")
                return self._models[name]
            
            # 檢查快取大小，必要時清理
            if len(self._models) >= self._max_cache_size:
                self._cleanup_least_used_unlocked()
            
            # 加載模型
            logger.info(f"加載模型: {name}")
            cfg = self._model_configs[name]
            model = cfg['loader'](**cfg['config'])
            
            self._models[name] = model
            self._model_configs[name]['loaded'] = True
            
            return model
    
    def unload_model(self, name: str):
        """卸載特定模型（執行緒安全）"""
        with self._lock:
            self._unload_model_unlocked(name)

    def _unload_model_unlocked(self, name: str):
        """卸載特定模型（內部使用，呼叫者需持有 _lock）"""
        if name in self._models:
            logger.info(f"卸載模型: {name}")
            model = self._models.pop(name)
            
            # 清理模型資源
            if hasattr(model, 'cleanup'):
                model.cleanup()
            elif hasattr(model, 'close'):
                model.close()
            
            del model
            
            # 觸發垃圾回收
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            if name in self._model_configs:
                self._model_configs[name]['loaded'] = False
    
    def _cleanup_least_used_unlocked(self):
        """清理最少使用的模型（內部使用，呼叫者需持有 _lock）"""
        if self._models:
            # 獲取第一個模型並卸載
            first_model = next(iter(self._models))
            logger.info(f"快取已滿，卸載模型: {first_model}")
            self._unload_model_unlocked(first_model)
    
    def unload_all(self):
        """卸載所有模型（執行緒安全）"""
        with self._lock:
            model_names = list(self._models.keys())
            for name in model_names:
                self._unload_model_unlocked(name)
    
    def get_loaded_models(self) -> list:
        """獲取已加載的模型列表（執行緒安全）"""
        with self._lock:
            return list(self._models.keys())
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """獲取模型記憶體使用情況（執行緒安全）"""
        with self._lock:
            usage = {}
            for name, model in self._models.items():
                model_size = 0
                if hasattr(model, 'parameters'):
                    # PyTorch 模型
                    for param in model.parameters():
                        model_size += param.numel() * param.element_size()
                usage[name] = model_size / (1024 * 1024)  # MB
            return usage

# 單例模式
model_manager = ModelManager()