"""
ASR 服務統一入口

所有 ASR 相關操作都應通過此服務進行，
提供統一的 API 並管理引擎生命週期。
"""

import logging
import threading
from typing import Dict, Any, Optional

from services.asr_factory import ASRFactory
from services.asr_engine import ASREngine

logger = logging.getLogger(__name__)


class ASRService:
    """ASR 服務 - 統一入口

    提供以下功能：
    - 統一的 ASR 引擎訪問接口
    - 引擎生命週期管理
    - 配置驅動的引擎選擇
    - 單例模式確保資源有效利用
    """

    _instance: Optional['ASRService'] = None
    _instance_lock: threading.Lock = threading.Lock()

    def __init__(self):
        """初始化 ASR 服務"""
        self._engine: Optional[ASREngine] = None
        self._current_config: Dict[str, str] = {}
        logger.debug("ASRService 實例已創建")

    @classmethod
    def get_instance(cls) -> 'ASRService':
        """獲取單例實例（執行緒安全，雙重檢查鎖定）

        Returns:
            ASRService: 服務實例
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
                    logger.info("ASRService 單例已初始化")
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置單例實例（主要用於測試）"""
        if cls._instance is not None:
            cls._instance.cleanup()
            cls._instance = None
            logger.info("ASRService 單例已重置")

    def get_engine(self, backend: str = None, model_size: str = None,
                   engine_type: str = None, force_new: bool = False,
                   **kwargs) -> ASREngine:
        """獲取 ASR 引擎（延遲初始化）

        Args:
            backend: Whisper 後端 (auto, faster_whisper, ctranslate2, transformers)
            model_size: 模型大小或名稱
            engine_type: 引擎類型 (whisper, glm_asr, vosk, huggingface)
            force_new: 強制創建新引擎（忽略緩存）
            **kwargs: 傳遞給引擎構造函數的額外參數

        Returns:
            ASREngine: ASR 引擎實例
        """
        # 獲取默認配置
        try:
            from config import config
            engine_type = engine_type or config.ASR_ENGINE
        except ImportError:
            engine_type = engine_type or "whisper"

        # 根據引擎類型構建配置和參數
        if engine_type == "glm_asr" or engine_type == "glm":
            current_config, engine_kwargs = self._build_glm_asr_config(**kwargs)
        elif engine_type == "vosk":
            current_config, engine_kwargs = self._build_vosk_config(**kwargs)
        elif engine_type == "huggingface" or engine_type == "hf":
            current_config, engine_kwargs = self._build_hf_config(**kwargs)
        elif engine_type == "funasr" or engine_type == "paraformer":
            current_config, engine_kwargs = self._build_funasr_config(**kwargs)
        elif engine_type == "vibevoice":
            current_config, engine_kwargs = self._build_vibevoice_config(**kwargs)
        elif engine_type == "whisper":
            current_config, engine_kwargs = self._build_whisper_config(backend, model_size, **kwargs)
        else:
            # 未知引擎類型，嘗試直接使用
            logger.warning(f"未知引擎類型: {engine_type}，嘗試直接創建")
            current_config = {"engine_type": engine_type}
            engine_kwargs = kwargs

        current_config["engine_type"] = engine_type

        # 檢查是否需要創建新引擎
        config_changed = current_config != self._current_config
        need_new = force_new or self._engine is None or config_changed

        if need_new:
            # 清理舊引擎
            if self._engine is not None:
                logger.info("配置已更改，清理舊引擎")
                self._engine.cleanup()

            # 創建新引擎
            logger.info(f"創建新 ASR 引擎: type={engine_type}, config={current_config}")
            self._engine = ASRFactory.create(
                engine_type=engine_type,
                **engine_kwargs
            )
            self._current_config = current_config

        return self._engine

    def _build_whisper_config(self, backend: str = None, model_size: str = None, **kwargs) -> tuple:
        """構建 Whisper 引擎配置"""
        try:
            from config import config
            backend = backend or config.WHISPER_BACKEND
            model_size = model_size or config.DEFAULT_WHISPER_MODEL
        except ImportError:
            backend = backend or "auto"
            model_size = model_size or "base"

        current_config = {"backend": backend, "model_size": model_size}
        engine_kwargs = {"backend": backend, "model_size": model_size}
        engine_kwargs.update(kwargs)
        return current_config, engine_kwargs

    def _build_glm_asr_config(self, **kwargs) -> tuple:
        """構建 GLM-ASR 引擎配置"""
        try:
            from config import config
            model_id = kwargs.get('model_id') or config.GLM_ASR_MODEL
            device = kwargs.get('device') or config.GLM_ASR_DEVICE
            dtype = kwargs.get('dtype') or config.GLM_ASR_DTYPE
        except ImportError:
            model_id = kwargs.get('model_id', "zai-org/GLM-ASR-Nano-2512")
            device = kwargs.get('device', "auto")
            dtype = kwargs.get('dtype', "auto")

        current_config = {"model_id": model_id, "device": device, "dtype": dtype}
        engine_kwargs = {"model_id": model_id, "device": device, "dtype": dtype}
        return current_config, engine_kwargs

    def _build_vosk_config(self, **kwargs) -> tuple:
        """構建 Vosk 引擎配置"""
        model_path = kwargs.get('model_path', None)
        sample_rate = kwargs.get('sample_rate', 16000)

        current_config = {"model_path": model_path, "sample_rate": sample_rate}
        engine_kwargs = {"model_path": model_path, "sample_rate": sample_rate}
        return current_config, engine_kwargs

    def _build_hf_config(self, **kwargs) -> tuple:
        """構建 HuggingFace 引擎配置"""
        model_id = kwargs.get('model_id', "openai/whisper-base")
        device = kwargs.get('device', "auto")
        torch_dtype = kwargs.get('torch_dtype', "auto")

        current_config = {"model_id": model_id, "device": device, "torch_dtype": torch_dtype}
        engine_kwargs = {"model_id": model_id, "device": device, "torch_dtype": torch_dtype}
        return current_config, engine_kwargs

    def _build_funasr_config(self, **kwargs) -> tuple:
        """構建 FunASR 引擎配置"""
        try:
            from config import config
            model = kwargs.get('model') or config.FUNASR_MODEL
            vad_model = kwargs.get('vad_model') or config.FUNASR_VAD_MODEL
            punc_model = kwargs.get('punc_model') or config.FUNASR_PUNC_MODEL
            device = kwargs.get('device') or config.FUNASR_DEVICE
            batch_size_s = kwargs.get('batch_size_s') or config.FUNASR_BATCH_SIZE_S
        except ImportError:
            model = kwargs.get('model', "paraformer-zh")
            vad_model = kwargs.get('vad_model', "fsmn-vad")
            punc_model = kwargs.get('punc_model', "ct-punc-c")
            device = kwargs.get('device', "cuda")
            batch_size_s = kwargs.get('batch_size_s', 300)

        current_config = {
            "model": model,
            "vad_model": vad_model,
            "punc_model": punc_model,
            "device": device,
            "batch_size_s": batch_size_s
        }
        engine_kwargs = current_config.copy()
        return current_config, engine_kwargs

    def _build_vibevoice_config(self, **kwargs) -> tuple:
        """構建 VibeVoice 引擎配置"""
        try:
            from config import config
            model_path = kwargs.get('model_path') or config.VIBEVOICE_MODEL
            language_model = kwargs.get('language_model') or config.VIBEVOICE_LANGUAGE_MODEL
            device = kwargs.get('device') or config.VIBEVOICE_DEVICE
            dtype = kwargs.get('dtype') or config.VIBEVOICE_DTYPE
            max_new_tokens = kwargs.get('max_new_tokens') or config.VIBEVOICE_MAX_NEW_TOKENS
        except ImportError:
            model_path = kwargs.get('model_path', "microsoft/VibeVoice-ASR")
            language_model = kwargs.get('language_model', "Qwen/Qwen2.5-7B")
            device = kwargs.get('device', "cuda")
            dtype = kwargs.get('dtype', "bfloat16")
            max_new_tokens = kwargs.get('max_new_tokens', 8192)

        current_config = {
            "model_path": model_path,
            "language_model": language_model,
            "device": device,
            "dtype": dtype,
            "max_new_tokens": max_new_tokens
        }
        engine_kwargs = current_config.copy()
        return current_config, engine_kwargs

    def transcribe(self, audio, config_data: dict = None, **kwargs) -> Dict[str, Any]:
        """執行轉錄

        便捷方法，自動獲取引擎並執行轉錄。

        Args:
            audio: 音頻數據 (numpy array)
            config_data: 配置字典（包含 whisper_backend, whisper_model, asr_engine 等）
            **kwargs: 傳遞給 transcribe 的額外參數

        Returns:
            Dict: 轉錄結果

        Raises:
            RuntimeError: 如果模型載入失敗
        """
        config_data = config_data or {}

        # 獲取引擎類型
        try:
            from config import config
            engine_type = config_data.get('asr_engine', config.ASR_ENGINE)
        except ImportError:
            engine_type = config_data.get('asr_engine', 'whisper')

        # 根據引擎類型提取配置
        engine_kwargs = {}
        if engine_type == "glm_asr" or engine_type == "glm":
            try:
                from config import config
                engine_kwargs = {
                    'model_id': config_data.get('glm_asr_model', config.GLM_ASR_MODEL),
                    'device': config_data.get('glm_asr_device', config.GLM_ASR_DEVICE),
                    'dtype': config_data.get('glm_asr_dtype', config.GLM_ASR_DTYPE)
                }
            except ImportError:
                engine_kwargs = {
                    'model_id': config_data.get('glm_asr_model', 'zai-org/GLM-ASR-Nano-2512'),
                    'device': config_data.get('glm_asr_device', 'auto'),
                    'dtype': config_data.get('glm_asr_dtype', 'auto')
                }
        else:
            # Whisper 引擎配置 (default)
            try:
                from config import config
                engine_kwargs = {
                    'backend': config_data.get('whisper_backend', config.WHISPER_BACKEND),
                    'model_size': config_data.get('whisper_model', config.DEFAULT_WHISPER_MODEL)
                }
            except ImportError:
                engine_kwargs = {
                    'backend': config_data.get('whisper_backend', 'auto'),
                    'model_size': config_data.get('whisper_model', 'base')
                }

        # 獲取引擎
        engine = self.get_engine(engine_type=engine_type, **engine_kwargs)

        # 確保模型已載入
        if not engine.is_loaded:
            logger.info("模型未載入，正在載入...")
            if not engine.load_model():
                raise RuntimeError("ASR 模型載入失敗")

        # 執行轉錄
        return engine.transcribe(audio, **kwargs)

    def cleanup(self) -> None:
        """清理資源

        釋放當前引擎佔用的資源。
        """
        if self._engine is not None:
            logger.info("清理 ASR 引擎資源")
            self._engine.cleanup()
            self._engine = None
            self._current_config = {}

    def get_model_info(self) -> Dict[str, Any]:
        """獲取當前模型信息

        Returns:
            Dict: 模型信息，如果未載入則返回 {"status": "not_loaded"}
        """
        if self._engine is not None and self._engine.is_loaded:
            return self._engine.get_model_info()
        return {"status": "not_loaded", "engine": None}

    def is_ready(self) -> bool:
        """檢查服務是否就緒

        Returns:
            bool: True 如果引擎已創建且模型已載入
        """
        return self._engine is not None and self._engine.is_loaded

    @property
    def engine(self) -> Optional[ASREngine]:
        """獲取當前引擎（可能為 None）

        Returns:
            Optional[ASREngine]: 當前引擎實例
        """
        return self._engine


# ===== 便捷函數 =====

def get_asr_service() -> ASRService:
    """獲取 ASR 服務實例（便捷函數）

    Returns:
        ASRService: 服務實例
    """
    return ASRService.get_instance()


# 向後兼容的別名
asr_service = ASRService.get_instance()


# ===== 向後兼容函數 =====

def get_whisper_model_info() -> Dict[str, Any]:
    """獲取 Whisper 模型信息（向後兼容）

    這是一個向後兼容函數，提供與舊版 whisper_integration.get_whisper_model_info()
    相同的接口。

    Returns:
        Dict: 模型信息
    """
    service = get_asr_service()
    info = service.get_model_info()

    # 轉換為舊格式
    if info.get("status") == "not_loaded":
        return {
            "model_loaded": False,
            "model_size": None,
            "backend": None,
            "device": None
        }

    return {
        "model_loaded": True,
        "model_size": info.get("model_size"),
        "backend": info.get("backend"),
        "device": info.get("device")
    }
