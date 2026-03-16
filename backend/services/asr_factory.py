"""
ASR 引擎工廠

負責創建和管理不同類型的 ASR 引擎實例。
支持多種本地 STT 模型：
- Whisper (faster-whisper, ctranslate2, transformers)
- Vosk (離線輕量級)
- HuggingFace (Wav2Vec2, XLSR, distil-whisper 等)
"""

import logging
from typing import Dict, Type, Optional, List

from services.asr_engine import ASREngine

logger = logging.getLogger(__name__)


class ASRFactory:
    """ASR 引擎工廠

    使用工廠模式創建 ASR 引擎實例，支持：
    - 多種本地 STT 模型
    - 動態註冊新的 ASR 引擎
    - 延遲載入（避免不必要的依賴載入）
    - 根據配置自動選擇引擎
    """

    # 已註冊的引擎類型
    _engines: Dict[str, Optional[Type[ASREngine]]] = {}

    # 支持的引擎列表及其說明
    SUPPORTED_ENGINES = {
        "whisper": "Whisper (faster-whisper/ctranslate2/transformers)",
        "vosk": "Vosk 離線語音識別",
        "huggingface": "HuggingFace ASR Pipeline (Wav2Vec2, XLSR, etc.)",
        "glm_asr": "智譜 GLM-ASR (GLM-ASR-Nano-2512)",
        "funasr": "阿里 FunASR (Paraformer-Large)",
        "vibevoice": "微軟 VibeVoice-ASR (60分鐘長音頻)",
    }

    @classmethod
    def register(cls, name: str, engine_class: Optional[Type[ASREngine]] = None) -> None:
        """註冊 ASR 引擎

        Args:
            name: 引擎名稱 (如 "whisper", "vosk", "huggingface")
            engine_class: 引擎類（可為 None，表示延遲載入）
        """
        cls._engines[name] = engine_class
        logger.debug(f"ASR 引擎已註冊: {name}")

    @classmethod
    def get_registered_engines(cls) -> List[str]:
        """獲取所有已註冊的引擎名稱

        Returns:
            list: 引擎名稱列表
        """
        return list(cls._engines.keys())

    @classmethod
    def get_available_engines(cls) -> Dict[str, bool]:
        """獲取所有引擎及其可用性狀態

        Returns:
            Dict[str, bool]: 引擎名稱 -> 是否可用
        """
        result = {}
        for engine_name in cls.SUPPORTED_ENGINES:
            result[engine_name] = cls.is_available(engine_name)
        return result

    @classmethod
    def create(cls, engine_type: str = None, **kwargs) -> ASREngine:
        """創建 ASR 引擎實例

        Args:
            engine_type: 引擎類型 (whisper, vosk, huggingface)
            **kwargs: 傳遞給引擎構造函數的參數

                Whisper 參數:
                - backend: str - 後端 (auto, faster_whisper, ctranslate2, transformers)
                - model_size: str - 模型大小或 HF 模型 ID

                Vosk 參數:
                - model_path: str - Vosk 模型目錄路徑
                - sample_rate: int - 採樣率（默認 16000）

                HuggingFace 參數:
                - model_id: str - HuggingFace 模型 ID
                - device: str - 設備 (auto, cuda, cpu)
                - torch_dtype: str - 數據類型 (auto, float16, float32)
                - chunk_length_s: int - 分塊長度（秒）

        Returns:
            ASREngine: 引擎實例

        Raises:
            ValueError: 如果指定的引擎類型未知或不可用
        """
        # 從配置獲取默認引擎類型
        if engine_type is None:
            try:
                from config import config
                engine_type = getattr(config, 'ASR_ENGINE', 'whisper')
            except ImportError:
                engine_type = 'whisper'

        engine_type = engine_type.lower()
        logger.info(f"創建 ASR 引擎: {engine_type}")

        # ===== Whisper 引擎 =====
        if engine_type == "whisper":
            from services.whisper_adapter import WhisperASRAdapter
            return WhisperASRAdapter(**kwargs)

        # ===== Vosk 引擎 =====
        elif engine_type == "vosk":
            try:
                from services.vosk_adapter import VoskASRAdapter
                return VoskASRAdapter(**kwargs)
            except ImportError as e:
                raise ValueError(f"Vosk 適配器載入失敗: {e}。請確保已安裝 vosk: pip install vosk")

        # ===== HuggingFace 引擎 =====
        elif engine_type == "huggingface" or engine_type == "hf":
            try:
                from services.hf_asr_adapter import HuggingFaceASRAdapter
                return HuggingFaceASRAdapter(**kwargs)
            except ImportError as e:
                raise ValueError(f"HuggingFace 適配器載入失敗: {e}。請確保已安裝 transformers: pip install transformers torch")

        # ===== GLM-ASR 引擎 =====
        elif engine_type == "glm_asr" or engine_type == "glm":
            try:
                from services.glm_asr_adapter import GLMASRAdapter
                return GLMASRAdapter(**kwargs)
            except ImportError as e:
                raise ValueError(f"GLM-ASR 適配器載入失敗: {e}。請確保已安裝最新版 transformers: pip install git+https://github.com/huggingface/transformers")

        # ===== FunASR 引擎 =====
        elif engine_type == "funasr" or engine_type == "paraformer":
            try:
                from services.funasr_adapter import FunASRAdapter
                return FunASRAdapter(**kwargs)
            except ImportError as e:
                raise ValueError(f"FunASR 適配器載入失敗: {e}。請確保已安裝 funasr: pip install funasr")

        # ===== VibeVoice 引擎 =====
        elif engine_type == "vibevoice":
            try:
                from services.vibevoice_adapter import VibeVoiceAdapter
                return VibeVoiceAdapter(**kwargs)
            except ImportError as e:
                raise ValueError(f"VibeVoice 適配器載入失敗: {e}。請確保已安裝: pip install 'vibevoice[asr] @ git+https://github.com/microsoft/VibeVoice.git'")

        # ===== 檢查動態註冊的引擎 =====
        if engine_type in cls._engines:
            engine_class = cls._engines[engine_type]
            if engine_class is not None:
                return engine_class(**kwargs)

        # 未知引擎
        available = ", ".join(cls.SUPPORTED_ENGINES.keys())
        raise ValueError(f"未知的 ASR 引擎類型: {engine_type}。可用類型: {available}")

    @classmethod
    def is_available(cls, engine_type: str) -> bool:
        """檢查引擎是否可用（依賴已安裝）

        Args:
            engine_type: 引擎類型

        Returns:
            bool: 引擎是否可用
        """
        engine_type = engine_type.lower()

        if engine_type == "whisper":
            try:
                from whisper_integration import WhisperManager
                return True
            except ImportError:
                return False

        elif engine_type == "vosk":
            try:
                import vosk
                return True
            except ImportError:
                return False

        elif engine_type == "huggingface" or engine_type == "hf":
            try:
                import transformers
                import torch
                return True
            except ImportError:
                return False

        elif engine_type == "glm_asr" or engine_type == "glm":
            try:
                import transformers
                import torch
                return True
            except ImportError:
                return False

        elif engine_type == "funasr" or engine_type == "paraformer":
            try:
                import funasr
                return True
            except ImportError:
                return False

        elif engine_type == "vibevoice":
            try:
                import vibevoice
                return True
            except ImportError:
                return False

        # 檢查動態註冊的引擎
        return engine_type in cls._engines

    @classmethod
    def get_engine_info(cls, engine_type: str) -> Dict[str, any]:
        """獲取引擎的詳細信息

        Args:
            engine_type: 引擎類型

        Returns:
            Dict: 包含引擎名稱、描述、是否可用等信息
        """
        engine_type = engine_type.lower()
        return {
            "name": engine_type,
            "description": cls.SUPPORTED_ENGINES.get(engine_type, "未知引擎"),
            "available": cls.is_available(engine_type),
            "registered": engine_type in cls._engines
        }


# ===== 自動註冊內置引擎 =====
ASRFactory.register("whisper", None)
ASRFactory.register("vosk", None)
ASRFactory.register("huggingface", None)
ASRFactory.register("glm_asr", None)
ASRFactory.register("funasr", None)
ASRFactory.register("vibevoice", None)
