"""
ASR 語音識別引擎抽象接口

設計原則：
- 保持核心方法簡潔，通過 **kwargs 支持引擎特有功能
- 所有 faster-whisper 特有參數都通過 kwargs 傳遞
- 返回值格式統一，確保上層代碼無需感知具體引擎
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import numpy as np


class ASREngine(ABC):
    """ASR 語音識別引擎抽象接口

    所有 ASR 引擎實現都應繼承此類並實現所有抽象方法。
    這個接口設計為與 faster-whisper 的功能完全兼容，
    同時也能支持其他 ASR 服務（如 Google STT、Azure Speech）。
    """

    @abstractmethod
    def load_model(self) -> bool:
        """載入模型

        Returns:
            bool: 載入是否成功
        """
        pass

    @abstractmethod
    def transcribe(self, audio: np.ndarray, sampling_rate: int = 16000,
                  language: str = "zh", task: str = "transcribe",
                  **kwargs) -> Dict[str, Any]:
        """轉錄音頻

        Args:
            audio: 音頻數據 (numpy array, float32, 單聲道)
            sampling_rate: 採樣率 (默認 16000)
            language: 語言代碼 (默認 "zh")
            task: 任務類型 ("transcribe" 轉錄 或 "translate" 翻譯成英文)
            **kwargs: 引擎特有參數

                faster-whisper 支持的參數:
                - vad_filter: bool - 啟用 VAD (語音活動檢測)
                - vad_parameters: dict - VAD 配置參數
                - word_timestamps: bool - 啟用詞級時間戳
                - beam_size: int - Beam search 寬度
                - best_of: int - 最佳候選數
                - temperature: float - 採樣溫度
                - condition_on_previous_text: bool - 是否基於前文生成
                - no_repeat_ngram_size: int - 防止 n-gram 重複
                - repetition_penalty: float - 重複懲罰係數
                - compression_ratio_threshold: float - 重複片段過濾閾值
                - log_prob_threshold: float - 低概率過濾閾值
                - no_speech_threshold: float - 無語音閾值
                - hallucination_silence_threshold: float - 靜音段幻覺過濾

        Returns:
            Dict 包含以下字段:
            - text: str - 完整轉錄文本
            - language: str - 檢測到的語言代碼
            - segments: List[Dict] - 時間戳段落列表，每個包含 start, end, text
            - duration: float - 音頻總時長（秒）
            - inference_time: float - 推理耗時（秒）
            - backend: str - 使用的後端類型
            - error: Optional[str] - 錯誤信息（如果有）
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """清理資源

        釋放 GPU 記憶體、卸載模型等。
        在處理完成後或切換模型時調用。
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """獲取模型信息

        Returns:
            Dict 包含:
            - engine: str - 引擎類型 (如 "whisper", "google", "azure")
            - backend: str - 後端類型 (如 "faster_whisper", "ctranslate2")
            - model_size: str - 模型大小或名稱
            - device: str - 運行設備 ("gpu" 或 "cpu")
            - is_loaded: bool - 模型是否已載入
        """
        pass

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """模型是否已載入

        Returns:
            bool: True 如果模型已載入且可用
        """
        pass

    # 可選方法 - 有默認實現，子類可覆蓋

    def supports_vad(self) -> bool:
        """是否支持 VAD (語音活動檢測)

        Returns:
            bool: True 如果引擎支持 VAD 功能
        """
        return False

    def supports_word_timestamps(self) -> bool:
        """是否支持詞級時間戳

        Returns:
            bool: True 如果引擎支持詞級時間戳
        """
        return False

    def get_supported_languages(self) -> List[str]:
        """獲取支持的語言列表

        Returns:
            List[str]: 支持的語言代碼列表
        """
        return ["zh", "en"]  # 默認支持中英文

    def switch_backend(self, new_backend: str) -> bool:
        """切換後端

        某些引擎（如 Whisper）支持多個後端，可通過此方法切換。

        Args:
            new_backend: 新的後端名稱

        Returns:
            bool: 切換是否成功
        """
        return False  # 默認不支持切換
