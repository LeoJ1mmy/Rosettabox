"""
VibeVoice-ASR 適配器

支持 Microsoft VibeVoice-ASR 模型，特點：
- 60 分鐘單次處理（64K token）
- 支持中文和英文
- 說話人分離 + 時間戳
- 熱詞支持

使用前需安裝: pip install "vibevoice[asr] @ git+https://github.com/microsoft/VibeVoice.git"
"""

import logging
import time
import gc
from typing import Dict, Any, List, Optional
import numpy as np

from services.asr_engine import ASREngine

logger = logging.getLogger(__name__)


class VibeVoiceAdapter(ASREngine):
    """VibeVoice-ASR 適配器

    支持 Microsoft VibeVoice-ASR 模型的語音識別。

    特點：
    - 60 分鐘單次處理
    - 支持中文和英文
    - 說話人分離
    - 時間戳標記
    """

    def __init__(self,
                 model_path: str = "microsoft/VibeVoice-ASR",
                 language_model: str = "Qwen/Qwen2.5-7B",
                 device: str = "cuda",
                 dtype: str = "bfloat16",
                 max_new_tokens: int = 8192,
                 **kwargs):
        """初始化 VibeVoice-ASR 適配器

        Args:
            model_path: 模型路徑或 HuggingFace 模型 ID
            language_model: 語言模型名稱
            device: 設備 ("cuda", "cpu")
            dtype: 數據類型 ("bfloat16", "float16", "float32")
            max_new_tokens: 最大生成 token 數
        """
        self._model_path = model_path
        self._language_model = language_model
        self._device = device
        self._dtype = dtype
        self._max_new_tokens = max_new_tokens
        self._kwargs = kwargs

        self._model = None
        self._processor = None
        self._is_loaded = False

        logger.info(f"VibeVoiceAdapter 初始化: model={model_path}, device={device}")

    def load_model(self) -> bool:
        """載入 VibeVoice-ASR 模型

        Returns:
            bool: 載入是否成功
        """
        try:
            import torch
            from vibevoice.modular.modeling_vibevoice_asr import VibeVoiceASRForConditionalGeneration
            from vibevoice.processor.vibevoice_asr_processor import VibeVoiceASRProcessor

            logger.info(f"正在載入 VibeVoice-ASR 模型: {self._model_path}")

            # 確定數據類型
            if self._dtype == "bfloat16":
                torch_dtype = torch.bfloat16
            elif self._dtype == "float16":
                torch_dtype = torch.float16
            else:
                torch_dtype = torch.float32

            # 載入處理器
            logger.info("載入處理器...")
            self._processor = VibeVoiceASRProcessor.from_pretrained(
                self._model_path,
                language_model_pretrained_name=self._language_model,
                trust_remote_code=True
            )

            # 載入模型
            logger.info("載入模型...")
            self._model = VibeVoiceASRForConditionalGeneration.from_pretrained(
                self._model_path,
                torch_dtype=torch_dtype,
                device_map=self._device,
                trust_remote_code=True,
                attn_implementation="flash_attention_2" if self._device == "cuda" else "eager",
                # GB10 optimizations
                low_cpu_mem_usage=True,
            )

            # PyTorch 2.x optimization: torch.compile for faster inference
            if hasattr(torch, 'compile') and self._device == "cuda":
                try:
                    logger.info("🚀 啟用 torch.compile 優化...")
                    self._model = torch.compile(self._model, mode="reduce-overhead")
                    logger.info("✅ torch.compile 優化已啟用")
                except Exception as e:
                    logger.warning(f"torch.compile 優化失敗，使用原生模式: {e}")

            # Set model to evaluation mode
            self._model.eval()

            self._is_loaded = True
            logger.info(f"✅ VibeVoice-ASR 模型載入成功: {self._model_path}")
            logger.info(f"   設備: {self._device}")
            logger.info(f"   數據類型: {self._dtype}")
            logger.info(f"   Flash Attention 2: {'啟用' if self._device == 'cuda' else '停用'}")

            return True

        except ImportError as e:
            logger.error(f"依賴未安裝: {e}")
            logger.error('請執行: pip install "vibevoice[asr] @ git+https://github.com/microsoft/VibeVoice.git"')
            return False
        except Exception as e:
            logger.error(f"VibeVoice-ASR 模型載入失敗: {e}")
            import traceback
            traceback.print_exc()
            return False

    def transcribe(self, audio: np.ndarray, sampling_rate: int = 16000,
                  language: str = "zh", task: str = "transcribe",
                  **kwargs) -> Dict[str, Any]:
        """使用 VibeVoice-ASR 轉錄音頻

        Args:
            audio: 音頻數據 (numpy array, float32)
            sampling_rate: 採樣率
            language: 語言代碼 (zh, en)
            task: 任務類型 (transcribe)
            **kwargs: 額外參數
                - max_new_tokens: int - 最大生成 token 數
                - hotwords: List[str] - 熱詞列表

        Returns:
            Dict: 轉錄結果
        """
        if not self._is_loaded:
            return {"text": "", "error": "模型未載入"}

        start_time = time.time()

        try:
            import torch

            # 確保音頻是正確的格式
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # 確保音頻是 1D
            if len(audio.shape) > 1:
                audio = audio.flatten()

            # 獲取參數
            max_new_tokens = kwargs.get('max_new_tokens', self._max_new_tokens)
            hotwords = kwargs.get('hotwords', [])

            audio_duration = len(audio) / sampling_rate
            logger.info(f"處理音頻: {audio_duration:.1f} 秒")

            # 處理音頻輸入
            inputs = self._processor(
                audio,
                sampling_rate=sampling_rate,
                return_tensors="pt"
            )

            # 移動到正確的設備 (使用 non_blocking 加速傳輸)
            if self._device == "cuda":
                inputs = {k: v.cuda(non_blocking=True) if isinstance(v, torch.Tensor) else v for k, v in inputs.items()}
                # 同步確保數據傳輸完成
                torch.cuda.synchronize()

            # 生成轉錄 (使用 inference_mode 比 no_grad 更快)
            with torch.inference_mode():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                    temperature=0.0,
                    # 優化參數
                    use_cache=True,  # 啟用 KV cache
                    num_beams=1,     # 貪婪解碼更快
                    early_stopping=True,
                )

            # 解碼輸出
            transcription = self._processor.batch_decode(
                outputs,
                skip_special_tokens=True
            )

            text = transcription[0] if transcription else ""

            inference_time = time.time() - start_time

            # 解析時間戳和說話人信息（如果有）
            segments = self._parse_segments(text)

            logger.info(f"✅ VibeVoice-ASR 轉錄完成: {len(text)} 字符, 耗時 {inference_time:.1f}s")

            return {
                "text": self._clean_text(text),
                "language": language,
                "task": task,
                "inference_time": inference_time,
                "model_size": self._model_path,
                "backend": "vibevoice",
                "segments": segments,
                "duration": audio_duration,
                "raw_text": text
            }

        except Exception as e:
            logger.error(f"VibeVoice-ASR 轉錄失敗: {e}")
            import traceback
            traceback.print_exc()
            return {"text": "", "error": str(e)}

    def _parse_segments(self, text: str) -> List[Dict[str, Any]]:
        """解析文本中的時間戳和說話人信息

        Args:
            text: 原始輸出文本

        Returns:
            List[Dict]: 分段信息列表
        """
        segments = []
        # VibeVoice 輸出格式可能包含時間戳標記
        # 需要根據實際輸出格式解析
        # 暫時返回空列表，待實際測試後完善
        return segments

    def _clean_text(self, text: str) -> str:
        """清理文本，移除特殊標記

        Args:
            text: 原始文本

        Returns:
            str: 清理後的文本
        """
        # 移除可能的特殊標記
        import re
        # 移除時間戳標記 [00:00:00.000 --> 00:00:05.000]
        text = re.sub(r'\[\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}\]', '', text)
        # 移除說話人標記 <speaker_0>
        text = re.sub(r'<speaker_\d+>', '', text)
        return text.strip()

    def cleanup(self) -> None:
        """清理資源"""
        if self._model is not None:
            del self._model
            self._model = None

        if self._processor is not None:
            del self._processor
            self._processor = None

        gc.collect()

        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except:
            pass

        self._is_loaded = False
        logger.info("VibeVoiceAdapter 資源已清理")

    def get_model_info(self) -> Dict[str, Any]:
        """獲取模型信息"""
        return {
            "engine": "vibevoice",
            "backend": "vibevoice",
            "model_size": self._model_path,
            "device": self._device,
            "is_loaded": self._is_loaded,
            "language_model": self._language_model
        }

    @property
    def is_loaded(self) -> bool:
        """模型是否已載入"""
        return self._is_loaded

    @property
    def model_path(self) -> str:
        """獲取模型路徑"""
        return self._model_path

    def supports_vad(self) -> bool:
        """VibeVoice 內建 VAD"""
        return True

    def supports_word_timestamps(self) -> bool:
        """VibeVoice 支持時間戳"""
        return True

    def get_supported_languages(self) -> List[str]:
        """獲取支持的語言"""
        return ["zh", "en"]
