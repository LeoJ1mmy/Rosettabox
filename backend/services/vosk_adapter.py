"""
Vosk ASR 適配器

支持 Vosk 離線語音識別模型。
Vosk 支持多種語言，模型體積小，適合離線環境。

使用前需安裝: pip install vosk
模型下載: https://alphacephei.com/vosk/models
"""

import logging
import os
import json
from typing import Dict, Any, List, Optional
import numpy as np

from services.asr_engine import ASREngine

logger = logging.getLogger(__name__)


class VoskASRAdapter(ASREngine):
    """Vosk ASR 適配器

    Vosk 是一個離線語音識別工具包，特點：
    - 輕量級，模型體積小（40MB-1.5GB）
    - 支持 20+ 種語言
    - 純離線，無需網路
    - 支持 Raspberry Pi 等嵌入式設備
    """

    def __init__(self, model_path: str = None, sample_rate: int = 16000):
        """初始化 Vosk 適配器

        Args:
            model_path: Vosk 模型目錄路徑
            sample_rate: 音頻採樣率（Vosk 通常使用 16000）
        """
        self._model = None
        self._recognizer = None
        self._model_path = model_path
        self._sample_rate = sample_rate
        self._is_loaded = False

        logger.info(f"VoskASRAdapter 初始化: model_path={model_path}")

    def load_model(self) -> bool:
        """載入 Vosk 模型

        Returns:
            bool: 載入是否成功
        """
        try:
            from vosk import Model, KaldiRecognizer

            if not self._model_path or not os.path.exists(self._model_path):
                logger.error(f"Vosk 模型路徑不存在: {self._model_path}")
                return False

            logger.info(f"正在載入 Vosk 模型: {self._model_path}")
            self._model = Model(self._model_path)
            self._recognizer = KaldiRecognizer(self._model, self._sample_rate)
            self._recognizer.SetWords(True)  # 啟用詞級時間戳
            self._is_loaded = True

            logger.info("✅ Vosk 模型載入成功")
            return True

        except ImportError:
            logger.error("Vosk 未安裝，請執行: pip install vosk")
            return False
        except Exception as e:
            logger.error(f"Vosk 模型載入失敗: {e}")
            return False

    def transcribe(self, audio: np.ndarray, sampling_rate: int = 16000,
                  language: str = "zh", task: str = "transcribe",
                  **kwargs) -> Dict[str, Any]:
        """使用 Vosk 轉錄音頻

        Args:
            audio: 音頻數據 (numpy array, float32)
            sampling_rate: 採樣率
            language: 語言代碼（Vosk 由模型決定語言）
            task: 任務類型（Vosk 只支持 transcribe）
            **kwargs: 其他參數

        Returns:
            Dict: 轉錄結果
        """
        import time

        if not self._is_loaded:
            return {"text": "", "error": "模型未載入"}

        start_time = time.time()

        try:
            # 確保音頻格式正確
            if audio.dtype == np.float32:
                # 轉換為 int16（Vosk 需要）
                audio_int16 = (audio * 32767).astype(np.int16)
            else:
                audio_int16 = audio.astype(np.int16)

            # 重新初始化識別器以清除狀態
            from vosk import KaldiRecognizer
            self._recognizer = KaldiRecognizer(self._model, self._sample_rate)
            self._recognizer.SetWords(True)

            # 分段處理音頻
            chunk_size = 4000  # 每次處理 4000 個樣本
            full_text = []
            segments = []

            for i in range(0, len(audio_int16), chunk_size):
                chunk = audio_int16[i:i + chunk_size].tobytes()
                if self._recognizer.AcceptWaveform(chunk):
                    result = json.loads(self._recognizer.Result())
                    if result.get("text"):
                        full_text.append(result["text"])
                        # 提取詞級時間戳
                        if "result" in result:
                            for word_info in result["result"]:
                                segments.append({
                                    "start": word_info.get("start", 0),
                                    "end": word_info.get("end", 0),
                                    "text": word_info.get("word", "")
                                })

            # 獲取最後的結果
            final_result = json.loads(self._recognizer.FinalResult())
            if final_result.get("text"):
                full_text.append(final_result["text"])
                if "result" in final_result:
                    for word_info in final_result["result"]:
                        segments.append({
                            "start": word_info.get("start", 0),
                            "end": word_info.get("end", 0),
                            "text": word_info.get("word", "")
                        })

            inference_time = time.time() - start_time
            text = " ".join(full_text)

            return {
                "text": text,
                "language": language,
                "task": task,
                "inference_time": inference_time,
                "model_size": os.path.basename(self._model_path) if self._model_path else "unknown",
                "backend": "vosk",
                "segments": segments,
                "duration": len(audio) / sampling_rate
            }

        except Exception as e:
            logger.error(f"Vosk 轉錄失敗: {e}")
            return {"text": "", "error": str(e)}

    def cleanup(self) -> None:
        """清理資源"""
        self._recognizer = None
        # Vosk Model 不需要顯式清理
        logger.info("VoskASRAdapter 資源已清理")

    def get_model_info(self) -> Dict[str, Any]:
        """獲取模型信息"""
        return {
            "engine": "vosk",
            "backend": "vosk",
            "model_size": os.path.basename(self._model_path) if self._model_path else None,
            "device": "cpu",  # Vosk 主要在 CPU 運行
            "is_loaded": self._is_loaded
        }

    @property
    def is_loaded(self) -> bool:
        """模型是否已載入"""
        return self._is_loaded

    def supports_vad(self) -> bool:
        """Vosk 內置 VAD"""
        return True

    def supports_word_timestamps(self) -> bool:
        """Vosk 支持詞級時間戳"""
        return True

    def get_supported_languages(self) -> List[str]:
        """Vosk 支持的語言取決於下載的模型"""
        return ["zh", "en", "ru", "de", "fr", "es", "pt", "it", "ja", "ko"]
