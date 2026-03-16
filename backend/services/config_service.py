"""
配置管理服務 - 集中管理所有處理設置
提供持久化配置存儲和API接口
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import threading

logger = logging.getLogger(__name__)

@dataclass
class ProcessingConfig:
    """處理配置數據類"""
    # 語音處理設置
    whisper_model: str = "base"
    speaker_count_mode: str = "auto"  # auto, manual
    estimated_speakers: int = 3
    enable_timestamps: bool = True
    
    # AI 文字處理設置
    ai_model: str = "gpt-oss:20b"
    enable_llm_processing: bool = True
    processing_mode: str = "default"  # default, meeting, lecture
    detail_level: str = "detailed"  # 固定使用詳細模式
    
    # 系統設置
    theme: str = "light"  # light, dark
    upload_mode: str = "single"  # single, dual
    auto_save_results: bool = True
    max_file_size_mb: int = 500
    
    # 高級設置
    gpu_acceleration: bool = True
    batch_processing: bool = False
    cache_models: bool = True
    debug_mode: bool = False

class ConfigService:
    """配置管理服務"""
    
    def __init__(self, config_dir: str = "/tmp/voice_processor_config"):
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, "config.json")
        self.user_configs_dir = os.path.join(config_dir, "users")
        self.lock = threading.RLock()
        
        # 創建配置目錄
        os.makedirs(config_dir, exist_ok=True)
        os.makedirs(self.user_configs_dir, exist_ok=True)
        
        # 加載默認配置
        self.default_config = ProcessingConfig()
        self._ensure_default_config_exists()
        
        logger.info(f"配置服務初始化完成，配置目錄: {config_dir}")
    
    def _ensure_default_config_exists(self):
        """確保默認配置文件存在"""
        if not os.path.exists(self.config_file):
            self.save_global_config(self.default_config)
            logger.info("創建默認配置文件")
    
    def get_user_config_path(self, user_id: str) -> str:
        """獲取用戶配置文件路徑"""
        return os.path.join(self.user_configs_dir, f"{user_id}.json")
    
    def get_global_config(self) -> ProcessingConfig:
        """獲取全局配置"""
        with self.lock:
            try:
                if os.path.exists(self.config_file):
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        return ProcessingConfig(**data)
                else:
                    return self.default_config
            except Exception as e:
                logger.error(f"讀取全局配置失敗: {e}")
                return self.default_config
    
    def save_global_config(self, config: ProcessingConfig) -> bool:
        """保存全局配置"""
        with self.lock:
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(asdict(config), f, ensure_ascii=False, indent=2)
                logger.info("全局配置保存成功")
                return True
            except Exception as e:
                logger.error(f"保存全局配置失敗: {e}")
                return False
    
    def get_user_config(self, user_id: str) -> ProcessingConfig:
        """獲取用戶配置，如果不存在則使用全局配置"""
        if not user_id:
            return self.get_global_config()
            
        user_config_path = self.get_user_config_path(user_id)
        
        with self.lock:
            try:
                if os.path.exists(user_config_path):
                    with open(user_config_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        return ProcessingConfig(**data)
                else:
                    # 用戶配置不存在，使用全局配置並創建用戶配置文件
                    global_config = self.get_global_config()
                    self.save_user_config(user_id, global_config)
                    return global_config
            except Exception as e:
                logger.error(f"讀取用戶配置失敗 (user_id: {user_id}): {e}")
                return self.get_global_config()
    
    def save_user_config(self, user_id: str, config: ProcessingConfig) -> bool:
        """保存用戶配置"""
        if not user_id:
            return self.save_global_config(config)
            
        user_config_path = self.get_user_config_path(user_id)
        
        with self.lock:
            try:
                with open(user_config_path, 'w', encoding='utf-8') as f:
                    json.dump(asdict(config), f, ensure_ascii=False, indent=2)
                logger.info(f"用戶配置保存成功 (user_id: {user_id})")
                return True
            except Exception as e:
                logger.error(f"保存用戶配置失敗 (user_id: {user_id}): {e}")
                return False
    
    def update_config_field(self, user_id: str, field: str, value: Any) -> bool:
        """更新單個配置字段"""
        try:
            config = self.get_user_config(user_id)
            if hasattr(config, field):
                setattr(config, field, value)
                return self.save_user_config(user_id, config)
            else:
                logger.error(f"配置字段不存在: {field}")
                return False
        except Exception as e:
            logger.error(f"更新配置字段失敗: {e}")
            return False
    
    def update_multiple_fields(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """批量更新配置字段"""
        try:
            config = self.get_user_config(user_id)
            
            for field, value in updates.items():
                if hasattr(config, field):
                    setattr(config, field, value)
                else:
                    logger.warning(f"忽略不存在的配置字段: {field}")
            
            return self.save_user_config(user_id, config)
        except Exception as e:
            logger.error(f"批量更新配置失敗: {e}")
            return False
    
    def reset_user_config(self, user_id: str) -> bool:
        """重置用戶配置為默認值"""
        try:
            return self.save_user_config(user_id, self.default_config)
        except Exception as e:
            logger.error(f"重置用戶配置失敗: {e}")
            return False
    
    def delete_user_config(self, user_id: str) -> bool:
        """刪除用戶配置文件"""
        if not user_id:
            return False
            
        user_config_path = self.get_user_config_path(user_id)
        
        with self.lock:
            try:
                if os.path.exists(user_config_path):
                    os.remove(user_config_path)
                    logger.info(f"用戶配置文件已刪除 (user_id: {user_id})")
                return True
            except Exception as e:
                logger.error(f"刪除用戶配置失敗: {e}")
                return False
    
    def export_config(self, user_id: str = None) -> Dict[str, Any]:
        """導出配置為字典格式"""
        if user_id:
            config = self.get_user_config(user_id)
        else:
            config = self.get_global_config()
        return asdict(config)
    
    def import_config(self, config_data: Dict[str, Any], user_id: str = None) -> bool:
        """從字典導入配置"""
        try:
            config = ProcessingConfig(**config_data)
            if user_id:
                return self.save_user_config(user_id, config)
            else:
                return self.save_global_config(config)
        except Exception as e:
            logger.error(f"導入配置失敗: {e}")
            return False
    
    def get_config_schema(self) -> Dict[str, Any]:
        """獲取配置架構信息"""
        return {
            "fields": {
                # 語音處理設置
                "whisper_model": {
                    "type": "string",
                    "options": ["tiny", "base", "small", "medium", "large"],
                    "default": "base",
                    "description": "Whisper 語音識別模型"
                },
                "speaker_count_mode": {
                    "type": "string",
                    "options": ["auto", "manual"],
                    "default": "auto",
                    "description": "說話人數量模式"
                },
                "estimated_speakers": {
                    "type": "integer",
                    "min": 1,
                    "max": 10,
                    "default": 3,
                    "description": "預估說話人數量"
                },
                "enable_timestamps": {
                    "type": "boolean",
                    "default": True,
                    "description": "啟用時間戳"
                },
                
                # AI 文字處理設置
                "ai_model": {
                    "type": "string",
                    "default": "phi4-mini:3.8b",
                    "description": "AI 文字處理模型"
                },
                "enable_llm_processing": {
                    "type": "boolean",
                    "default": True,
                    "description": "啟用 LLM 文字整理"
                },
                "processing_mode": {
                    "type": "string",
                    "options": ["default", "meeting", "lecture"],
                    "default": "default",
                    "description": "處理模式"
                },
                "detail_level": {
                    "type": "string",
                    "options": ["simple", "normal", "detailed"],
                    "default": "normal",
                    "description": "詳細程度"
                },
                
                # 系統設置
                "theme": {
                    "type": "string",
                    "options": ["light", "dark"],
                    "default": "light",
                    "description": "界面主題"
                },
                "upload_mode": {
                    "type": "string",
                    "options": ["single", "dual"],
                    "default": "single",
                    "description": "上傳模式"
                },
                "auto_save_results": {
                    "type": "boolean",
                    "default": True,
                    "description": "自動保存結果"
                },
                "max_file_size_mb": {
                    "type": "integer",
                    "min": 1,
                    "max": 1000,
                    "default": 100,
                    "description": "最大文件大小 (MB)"
                },
                
                # 高級設置
                "gpu_acceleration": {
                    "type": "boolean",
                    "default": True,
                    "description": "GPU 加速"
                },
                "batch_processing": {
                    "type": "boolean",
                    "default": False,
                    "description": "批次處理"
                },
                "cache_models": {
                    "type": "boolean",
                    "default": True,
                    "description": "緩存模型"
                },
                "debug_mode": {
                    "type": "boolean",
                    "default": False,
                    "description": "調試模式"
                }
            }
        }

# 單例實例
config_service = ConfigService()