"""
GPU 緩存清理工具 - 統一的GPU記憶體管理
"""
import logging
import gc
from typing import Optional

logger = logging.getLogger(__name__)

class GPUCleaner:
    """GPU 記憶體清理器"""
    
    @staticmethod
    def cleanup_gpu_cache(force: bool = False, log_prefix: str = "") -> bool:
        """
        清理 GPU 緩存
        
        Args:
            force: 強制清理，即使沒有GPU也嘗試
            log_prefix: 日誌前綴
            
        Returns:
            bool: 清理是否成功
        """
        try:
            # 清理 Python 垃圾回收
            gc.collect()
            
            # 檢查並清理 GPU 記憶體
            try:
                import torch
                if torch.cuda.is_available():
                    # 記錄清理前的記憶體狀態
                    allocated_before = torch.cuda.memory_allocated() / 1024**3
                    reserved_before = torch.cuda.memory_reserved() / 1024**3
                    
                    # 執行清理
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    
                    # 記錄清理後的記憶體狀態
                    allocated_after = torch.cuda.memory_allocated() / 1024**3
                    reserved_after = torch.cuda.memory_reserved() / 1024**3
                    
                    freed_allocated = allocated_before - allocated_after
                    freed_reserved = reserved_before - reserved_after
                    
                    logger.info(f"✅ {log_prefix}GPU 緩存清理完成:")
                    logger.info(f"   已分配記憶體: {allocated_before:.2f}GB → {allocated_after:.2f}GB (釋放 {freed_allocated:.2f}GB)")
                    logger.info(f"   已預留記憶體: {reserved_before:.2f}GB → {reserved_after:.2f}GB (釋放 {freed_reserved:.2f}GB)")
                    
                    return True
                elif force:
                    logger.warning(f"⚠️ {log_prefix}GPU 不可用但強制清理模式")
                    return False
                else:
                    logger.debug(f"ℹ️ {log_prefix}GPU 不可用，跳過清理")
                    return False
                    
            except ImportError:
                if force:
                    logger.warning(f"⚠️ {log_prefix}PyTorch 未安裝，無法清理GPU記憶體")
                return False
                
        except Exception as e:
            logger.error(f"❌ {log_prefix}GPU 緩存清理失敗: {e}")
            return False
    
    @staticmethod
    def get_gpu_memory_info() -> Optional[dict]:
        """
        獲取 GPU 記憶體資訊
        
        Returns:
            dict: GPU記憶體資訊，包含總量、已用、可用等
        """
        try:
            import torch
            if not torch.cuda.is_available():
                return None
                
            device_count = torch.cuda.device_count()
            memory_info = []
            
            for i in range(device_count):
                with torch.cuda.device(i):
                    total = torch.cuda.get_device_properties(i).total_memory / 1024**3
                    allocated = torch.cuda.memory_allocated(i) / 1024**3
                    reserved = torch.cuda.memory_reserved(i) / 1024**3
                    free = total - reserved
                    # 🔧 修復：避免除零錯誤
                    utilization = (reserved / total) * 100 if total > 0 else 0.0

                    memory_info.append({
                        'device_id': i,
                        'device_name': torch.cuda.get_device_name(i),
                        'total_gb': total,
                        'allocated_gb': allocated,
                        'reserved_gb': reserved,
                        'free_gb': free,
                        'utilization_percent': utilization
                    })
            
            return {
                'device_count': device_count,
                'current_device': torch.cuda.current_device(),
                'devices': memory_info
            }
            
        except Exception as e:
            logger.error(f"❌ 獲取GPU記憶體資訊失敗: {e}")
            return None
    
    @staticmethod
    def force_cleanup_all():
        """強制清理所有可能的記憶體緩存"""
        try:
            logger.info("🧹 開始強制清理所有GPU緩存...")
            
            # 1. Python垃圾回收
            gc.collect()
            
            # 2. PyTorch GPU緩存
            try:
                import torch
                if torch.cuda.is_available():
                    for i in range(torch.cuda.device_count()):
                        with torch.cuda.device(i):
                            torch.cuda.empty_cache()
                            torch.cuda.synchronize()
                    logger.info("✅ PyTorch GPU緩存已清理")
            except ImportError:
                pass
            
            # 3. 其他可能的GPU記憶體清理
            try:
                # TensorFlow GPU記憶體清理（如果有）
                import tensorflow as tf
                if tf.config.list_physical_devices('GPU'):
                    tf.keras.backend.clear_session()
                    logger.info("✅ TensorFlow GPU緩存已清理")
            except ImportError:
                pass
            
            logger.info("🎉 強制清理完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 強制清理失敗: {e}")
            return False

# 創建全局清理器實例
gpu_cleaner = GPUCleaner()

# 便捷函數
def cleanup_gpu(force: bool = False, log_prefix: str = "") -> bool:
    """便捷的GPU清理函數"""
    return gpu_cleaner.cleanup_gpu_cache(force=force, log_prefix=log_prefix)

def get_gpu_info() -> Optional[dict]:
    """便捷的GPU資訊獲取函數"""
    return gpu_cleaner.get_gpu_memory_info()

def force_cleanup() -> bool:
    """便捷的強制清理函數"""
    return gpu_cleaner.force_cleanup_all()