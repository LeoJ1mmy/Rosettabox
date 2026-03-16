"""
Whisper ASR 適配器

將 WhisperManager 包裝為 ASREngine 接口，
完整保留 faster-whisper 的所有特有功能。
"""

import logging
from typing import Dict, Any, List
import numpy as np

from services.asr_engine import ASREngine

logger = logging.getLogger(__name__)


class WhisperASRAdapter(ASREngine):
    """Whisper ASR 適配器 - 將 WhisperManager 包裝為 ASREngine

    完整保留 faster-whisper 的所有特有功能：
    - VAD (語音活動檢測)
    - 詞級時間戳
    - 防重複機制
    - 幻覺過濾
    - GPU 自動降級
    - 多後端支持 (faster_whisper, ctranslate2, transformers)
    """

    def __init__(self, backend: str = "auto", model_size: str = "base"):
        """初始化 Whisper 適配器

        Args:
            backend: 後端類型 (auto, faster_whisper, ctranslate2, transformers)
            model_size: 模型大小或 Hugging Face 模型名稱
        """
        # 延遲導入避免循環依賴
        from whisper_integration import WhisperManager
        self._manager = WhisperManager(backend=backend, model_size=model_size)
        logger.info(f"WhisperASRAdapter 初始化: backend={backend}, model_size={model_size}")

    def load_model(self) -> bool:
        """載入 Whisper 模型

        Returns:
            bool: 載入是否成功
        """
        result = self._manager.load_model()
        if result:
            logger.info(f"Whisper 模型載入成功: {self._manager.model_size} ({self._manager.current_backend})")
        else:
            logger.error("Whisper 模型載入失敗")
        return result

    def transcribe(self, audio: np.ndarray, sampling_rate: int = 16000,
                  language: str = "zh", task: str = "transcribe",
                  **kwargs) -> Dict[str, Any]:
        """轉錄音頻 - 完整支持 faster-whisper 所有參數

        所有 kwargs 直接透傳到 WhisperManager.transcribe()，
        因此支持所有 faster-whisper 的進階參數。

        Args:
            audio: 音頻數據 (numpy array)
            sampling_rate: 採樣率
            language: 語言代碼
            task: 任務類型
            **kwargs: faster-whisper 特有參數，包括：
                - vad_filter: bool - 啟用 VAD
                - vad_parameters: dict - VAD 配置
                - word_timestamps: bool - 詞級時間戳
                - beam_size: int - Beam search 寬度
                - best_of: int - 最佳候選數
                - temperature: float - 採樣溫度
                - condition_on_previous_text: bool - 基於前文
                - no_repeat_ngram_size: int - 防 n-gram 重複
                - repetition_penalty: float - 重複懲罰
                - compression_ratio_threshold: float - 重複片段過濾
                - hallucination_silence_threshold: float - 幻覺過濾

        Returns:
            Dict: 轉錄結果
        """
        return self._manager.transcribe(audio, sampling_rate, language, task, **kwargs)

    def cleanup(self) -> None:
        """清理資源

        釋放 GPU 記憶體、卸載 Whisper 模型。
        """
        self._manager.cleanup()
        logger.info("WhisperASRAdapter 資源已清理")

    def get_model_info(self) -> Dict[str, Any]:
        """獲取模型信息

        Returns:
            Dict: 包含引擎、後端、模型大小、設備等信息
        """
        return {
            "engine": "whisper",
            "backend": self._manager.current_backend,
            "model_size": self._manager.model_size,
            "device": self._manager.device_type,
            "is_loaded": self._manager.is_loaded
        }

    @property
    def is_loaded(self) -> bool:
        """模型是否已載入"""
        return self._manager.is_loaded

    # ===== 向後兼容：暴露 WhisperManager 的所有重要屬性 =====

    @property
    def model_size(self) -> str:
        """獲取模型大小"""
        return self._manager.model_size

    @property
    def current_backend(self) -> str:
        """獲取當前後端"""
        return self._manager.current_backend

    @property
    def device_type(self) -> str:
        """獲取設備類型 (gpu 或 cpu)"""
        return self._manager.device_type

    @property
    def backend(self) -> str:
        """獲取後端設定 (可能是 auto)"""
        return self._manager.backend

    # ===== 進階功能 =====

    @property
    def manager(self):
        """獲取底層 WhisperManager

        用於需要直接操作 WhisperManager 的特殊場景。

        Returns:
            WhisperManager: 底層管理器實例
        """
        return self._manager

    def supports_vad(self) -> bool:
        """是否支持 VAD

        faster-whisper 支持內置 VAD。
        """
        return self._manager.current_backend == "faster_whisper"

    def supports_word_timestamps(self) -> bool:
        """是否支持詞級時間戳

        faster-whisper 支持詞級時間戳。
        """
        return self._manager.current_backend == "faster_whisper"

    def get_supported_languages(self) -> List[str]:
        """獲取支持的語言列表

        Whisper 支持 99 種語言。
        """
        return [
            "zh", "en", "ja", "ko", "es", "fr", "de", "it", "pt", "ru",
            "ar", "hi", "th", "vi", "id", "ms", "tr", "pl", "nl", "sv",
            "no", "da", "fi", "el", "he", "uk", "cs", "hu", "ro", "bg"
            # ... 還有更多
        ]

    def switch_backend(self, new_backend: str) -> bool:
        """切換 Whisper 後端

        Args:
            new_backend: 新的後端 (faster_whisper, ctranslate2, transformers)

        Returns:
            bool: 切換是否成功
        """
        if hasattr(self._manager, 'switch_backend'):
            return self._manager.switch_backend(new_backend)
        return False
