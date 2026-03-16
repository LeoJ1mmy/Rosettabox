"""
FunASR 適配器

支持阿里達摩院 FunASR 框架的 Paraformer 系列模型。
特點：
- 非自回歸架構，高效率推理
- 60,000 小時中文語料訓練
- 內建 VAD 和標點符號恢復
- 支持長音頻處理

使用前需安裝: pip install funasr
"""

import logging
import time
import gc
from typing import Dict, Any, List, Optional
import numpy as np

from services.asr_engine import ASREngine

logger = logging.getLogger(__name__)


class FunASRAdapter(ASREngine):
    """FunASR 適配器

    支持 Paraformer 系列模型的語音識別。

    特點：
    - 支持中文（普通話）和英文
    - 內建 VAD（語音活動檢測）
    - 內建標點符號恢復
    - 支持長音頻自動分段處理
    """

    def __init__(self,
                 model: str = "paraformer-zh",
                 model_revision: str = "v2.0.4",
                 vad_model: str = "fsmn-vad",
                 vad_model_revision: str = "v2.0.4",
                 punc_model: str = "ct-punc-c",
                 punc_model_revision: str = "v2.0.4",
                 device: str = "cuda",
                 batch_size_s: int = 300,
                 **kwargs):
        """初始化 FunASR 適配器

        Args:
            model: 模型名稱 (paraformer-zh, paraformer-en, iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch)
            model_revision: 模型版本
            vad_model: VAD 模型名稱
            vad_model_revision: VAD 模型版本
            punc_model: 標點模型名稱
            punc_model_revision: 標點模型版本
            device: 設備 ("cuda", "cpu")
            batch_size_s: 批次處理的音頻長度（秒）
        """
        self._model_name = model
        self._model_revision = model_revision
        self._vad_model = vad_model
        self._vad_model_revision = vad_model_revision
        self._punc_model = punc_model
        self._punc_model_revision = punc_model_revision
        self._device = device
        self._batch_size_s = batch_size_s
        self._kwargs = kwargs

        self._model = None
        self._is_loaded = False

        logger.info(f"FunASRAdapter 初始化: model={model}, device={device}")

    def load_model(self) -> bool:
        """載入 FunASR 模型

        Returns:
            bool: 載入是否成功
        """
        try:
            from funasr import AutoModel

            logger.info(f"正在載入 FunASR 模型: {self._model_name}")

            # 構建模型參數
            model_kwargs = {
                "model": self._model_name,
                "device": self._device,
            }

            # 添加版本號（如果指定）
            if self._model_revision:
                model_kwargs["model_revision"] = self._model_revision

            # 添加 VAD 模型
            if self._vad_model:
                model_kwargs["vad_model"] = self._vad_model
                if self._vad_model_revision:
                    model_kwargs["vad_model_revision"] = self._vad_model_revision

            # 添加標點模型
            if self._punc_model:
                model_kwargs["punc_model"] = self._punc_model
                if self._punc_model_revision:
                    model_kwargs["punc_model_revision"] = self._punc_model_revision

            # 合併額外參數
            model_kwargs.update(self._kwargs)

            logger.info(f"模型參數: {model_kwargs}")

            # 載入模型
            self._model = AutoModel(**model_kwargs)

            self._is_loaded = True
            logger.info(f"✅ FunASR 模型載入成功: {self._model_name}")
            logger.info(f"   設備: {self._device}")
            logger.info(f"   VAD: {self._vad_model}")
            logger.info(f"   標點: {self._punc_model}")

            return True

        except ImportError as e:
            logger.error(f"依賴未安裝: {e}")
            logger.error("請執行: pip install funasr")
            return False
        except Exception as e:
            logger.error(f"FunASR 模型載入失敗: {e}")
            import traceback
            traceback.print_exc()
            return False

    def transcribe(self, audio: np.ndarray, sampling_rate: int = 16000,
                  language: str = "zh", task: str = "transcribe",
                  **kwargs) -> Dict[str, Any]:
        """使用 FunASR 轉錄音頻

        Args:
            audio: 音頻數據 (numpy array, float32)
            sampling_rate: 採樣率
            language: 語言代碼 (zh, en)
            task: 任務類型 (transcribe)
            **kwargs: 額外參數
                - batch_size_s: int - 批次處理音頻長度（秒）
                - hotword: str - 熱詞

        Returns:
            Dict: 轉錄結果
        """
        if not self._is_loaded:
            return {"text": "", "error": "模型未載入"}

        start_time = time.time()

        try:
            # 確保音頻是正確的格式
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # 確保音頻是 1D
            if len(audio.shape) > 1:
                audio = audio.flatten()

            # 獲取參數
            batch_size_s = kwargs.get('batch_size_s', self._batch_size_s)
            hotword = kwargs.get('hotword', '')

            audio_duration = len(audio) / sampling_rate
            logger.info(f"處理音頻: {audio_duration:.1f} 秒, batch_size_s={batch_size_s}")

            # 調用 FunASR 進行轉錄
            # FunASR 可以接受 numpy array 作為輸入
            generate_kwargs = {
                "input": audio,
                "batch_size_s": batch_size_s,
            }

            if hotword:
                generate_kwargs["hotword"] = hotword

            results = self._model.generate(**generate_kwargs)

            inference_time = time.time() - start_time

            # 處理結果
            if results and len(results) > 0:
                result = results[0]

                # FunASR 返回格式可能是 dict 或帶有 text 屬性的對象
                if isinstance(result, dict):
                    text = result.get("text", "")
                    timestamps = result.get("timestamp", [])
                elif hasattr(result, "text"):
                    text = result.text
                    timestamps = getattr(result, "timestamp", [])
                else:
                    text = str(result)
                    timestamps = []

                # 轉換時間戳格式
                segments = []
                if timestamps:
                    for ts in timestamps:
                        if isinstance(ts, (list, tuple)) and len(ts) >= 2:
                            segments.append({
                                "start": ts[0] / 1000.0,  # 毫秒轉秒
                                "end": ts[1] / 1000.0,
                                "text": ts[2] if len(ts) > 2 else ""
                            })

                logger.info(f"✅ FunASR 轉錄完成: {len(text)} 字符, 耗時 {inference_time:.1f}s")

                return {
                    "text": text,
                    "language": language,
                    "task": task,
                    "inference_time": inference_time,
                    "model_size": self._model_name,
                    "backend": "funasr",
                    "segments": segments,
                    "duration": audio_duration,
                    "timestamps": timestamps
                }
            else:
                return {
                    "text": "",
                    "language": language,
                    "task": task,
                    "inference_time": inference_time,
                    "model_size": self._model_name,
                    "backend": "funasr",
                    "segments": [],
                    "duration": audio_duration
                }

        except Exception as e:
            logger.error(f"FunASR 轉錄失敗: {e}")
            import traceback
            traceback.print_exc()
            return {"text": "", "error": str(e)}

    def cleanup(self) -> None:
        """清理資源"""
        if self._model is not None:
            del self._model
            self._model = None

        gc.collect()

        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except:
            pass

        self._is_loaded = False
        logger.info("FunASRAdapter 資源已清理")

    def get_model_info(self) -> Dict[str, Any]:
        """獲取模型信息"""
        return {
            "engine": "funasr",
            "backend": "funasr",
            "model_size": self._model_name,
            "device": self._device,
            "is_loaded": self._is_loaded,
            "vad_model": self._vad_model,
            "punc_model": self._punc_model
        }

    @property
    def is_loaded(self) -> bool:
        """模型是否已載入"""
        return self._is_loaded

    @property
    def model_name(self) -> str:
        """獲取模型名稱"""
        return self._model_name

    def supports_vad(self) -> bool:
        """FunASR 內建 VAD"""
        return True

    def supports_word_timestamps(self) -> bool:
        """FunASR 支持時間戳"""
        return True

    def get_supported_languages(self) -> List[str]:
        """獲取支持的語言"""
        if "zh" in self._model_name or "chinese" in self._model_name.lower():
            return ["zh", "en"]
        elif "en" in self._model_name:
            return ["en"]
        return ["zh", "en"]  # 默認支持中英文
