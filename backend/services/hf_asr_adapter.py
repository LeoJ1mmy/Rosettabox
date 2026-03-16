"""
HuggingFace ASR 適配器

支持 HuggingFace 上的各種 ASR 模型，包括：
- Wav2Vec2 系列
- Whisper 變體 (distil-whisper, whisper-large-v3)
- XLSR 多語言模型
- Conformer 模型
- 其他 transformers ASR pipeline 支持的模型

使用前需安裝: pip install transformers torch
"""

import logging
import time
from typing import Dict, Any, List, Optional
import numpy as np

from services.asr_engine import ASREngine

logger = logging.getLogger(__name__)


class HuggingFaceASRAdapter(ASREngine):
    """HuggingFace ASR 適配器

    通用適配器，支持 HuggingFace transformers 的 ASR pipeline。
    可以載入各種 ASR 模型，如 Wav2Vec2、Whisper、XLSR 等。
    """

    def __init__(self, model_id: str = "openai/whisper-base",
                 device: str = "auto",
                 torch_dtype: str = "auto",
                 chunk_length_s: int = 30,
                 batch_size: int = 8):
        """初始化 HuggingFace ASR 適配器

        Args:
            model_id: HuggingFace 模型 ID (如 "openai/whisper-base", "facebook/wav2vec2-large-xlsr-53")
            device: 設備 ("auto", "cuda", "cpu")
            torch_dtype: 數據類型 ("auto", "float16", "float32")
            chunk_length_s: 長音頻分塊長度（秒）
            batch_size: 批次大小
        """
        self._model_id = model_id
        self._device = device
        self._torch_dtype = torch_dtype
        self._chunk_length_s = chunk_length_s
        self._batch_size = batch_size

        self._pipeline = None
        self._is_loaded = False

        logger.info(f"HuggingFaceASRAdapter 初始化: model_id={model_id}")

    def load_model(self) -> bool:
        """載入 HuggingFace ASR 模型

        Returns:
            bool: 載入是否成功
        """
        try:
            import torch
            from transformers import pipeline

            # 確定設備
            if self._device == "auto":
                device = 0 if torch.cuda.is_available() else -1
            elif self._device == "cuda":
                device = 0
            else:
                device = -1

            # 確定數據類型
            if self._torch_dtype == "auto":
                torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            elif self._torch_dtype == "float16":
                torch_dtype = torch.float16
            else:
                torch_dtype = torch.float32

            logger.info(f"正在載入 HuggingFace 模型: {self._model_id}")
            logger.info(f"設備: {'GPU' if device >= 0 else 'CPU'}, 數據類型: {torch_dtype}")

            # 創建 ASR pipeline
            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=self._model_id,
                device=device,
                torch_dtype=torch_dtype,
                chunk_length_s=self._chunk_length_s,
                batch_size=self._batch_size
            )

            self._is_loaded = True
            logger.info(f"✅ HuggingFace 模型載入成功: {self._model_id}")
            return True

        except ImportError as e:
            logger.error(f"依賴未安裝: {e}")
            logger.error("請執行: pip install transformers torch")
            return False
        except Exception as e:
            logger.error(f"HuggingFace 模型載入失敗: {e}")
            return False

    def transcribe(self, audio: np.ndarray, sampling_rate: int = 16000,
                  language: str = "zh", task: str = "transcribe",
                  **kwargs) -> Dict[str, Any]:
        """使用 HuggingFace pipeline 轉錄音頻

        Args:
            audio: 音頻數據 (numpy array, float32)
            sampling_rate: 採樣率
            language: 語言代碼
            task: 任務類型 ("transcribe" 或 "translate")
            **kwargs: 傳遞給 pipeline 的額外參數
                - return_timestamps: bool - 是否返回時間戳
                - generate_kwargs: dict - 傳遞給 generate 的參數

        Returns:
            Dict: 轉錄結果
        """
        if not self._is_loaded:
            return {"text": "", "error": "模型未載入"}

        start_time = time.time()

        try:
            # 準備輸入
            inputs = {
                "raw": audio,
                "sampling_rate": sampling_rate
            }

            # 構建 generate_kwargs
            generate_kwargs = kwargs.get("generate_kwargs", {})

            # 對於支持語言參數的模型（如 Whisper）
            if "whisper" in self._model_id.lower():
                generate_kwargs["language"] = language
                generate_kwargs["task"] = task

            # 是否返回時間戳
            return_timestamps = kwargs.get("return_timestamps", True)

            # 執行轉錄
            result = self._pipeline(
                inputs,
                return_timestamps=return_timestamps,
                generate_kwargs=generate_kwargs if generate_kwargs else None
            )

            inference_time = time.time() - start_time

            # 處理結果
            text = result.get("text", "")
            chunks = result.get("chunks", [])

            # 轉換時間戳格式
            segments = []
            if chunks:
                for chunk in chunks:
                    timestamp = chunk.get("timestamp", (0, 0))
                    segments.append({
                        "start": timestamp[0] if timestamp[0] is not None else 0,
                        "end": timestamp[1] if timestamp[1] is not None else 0,
                        "text": chunk.get("text", "")
                    })

            return {
                "text": text,
                "language": language,
                "task": task,
                "inference_time": inference_time,
                "model_size": self._model_id,
                "backend": "huggingface",
                "segments": segments,
                "duration": len(audio) / sampling_rate
            }

        except Exception as e:
            logger.error(f"HuggingFace 轉錄失敗: {e}")
            return {"text": "", "error": str(e)}

    def cleanup(self) -> None:
        """清理資源"""
        import gc

        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None

        gc.collect()

        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except:
            pass

        self._is_loaded = False
        logger.info("HuggingFaceASRAdapter 資源已清理")

    def get_model_info(self) -> Dict[str, Any]:
        """獲取模型信息"""
        device = "unknown"
        if self._pipeline is not None:
            try:
                device = str(self._pipeline.device)
            except:
                pass

        return {
            "engine": "huggingface",
            "backend": "transformers",
            "model_size": self._model_id,
            "device": device,
            "is_loaded": self._is_loaded
        }

    @property
    def is_loaded(self) -> bool:
        """模型是否已載入"""
        return self._is_loaded

    def supports_vad(self) -> bool:
        """HuggingFace pipeline 不內置 VAD"""
        return False

    def supports_word_timestamps(self) -> bool:
        """部分模型支持時間戳"""
        return "whisper" in self._model_id.lower()

    def get_supported_languages(self) -> List[str]:
        """支持的語言取決於具體模型"""
        if "whisper" in self._model_id.lower():
            return ["zh", "en", "ja", "ko", "es", "fr", "de", "it", "pt", "ru"]
        elif "xlsr" in self._model_id.lower():
            return ["zh", "en", "de", "fr", "es", "it", "pt", "nl", "ru", "ja"]
        return ["en"]  # 默認只支持英文
