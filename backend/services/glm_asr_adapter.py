"""
GLM-ASR 適配器

支持智譜 GLM-ASR 系列模型，如 GLM-ASR-Nano-2512。
特點：
- 1.5B 參數，輕量級
- 支持中文（普通話、粵語）和英文
- 對低音量語音有良好魯棒性
- 使用 transformers Seq2Seq 架構

使用前需安裝最新版 transformers:
pip install git+https://github.com/huggingface/transformers
"""

import logging
import time
import gc
from typing import Dict, Any, List, Optional
import numpy as np

from services.asr_engine import ASREngine

logger = logging.getLogger(__name__)


class GLMASRAdapter(ASREngine):
    """GLM-ASR 適配器

    支持智譜 GLM-ASR 系列模型的語音識別。

    特點：
    - 支持中文（普通話、粵語）和英文
    - 對低音量/耳語語音有良好魯棒性
    - 1.5B 參數，輕量級部署
    - 使用 BF16 混合精度
    """

    def __init__(self,
                 model_id: str = "zai-org/GLM-ASR-Nano-2512",
                 device: str = "auto",
                 dtype: str = "auto",
                 max_new_tokens: int = 500):
        """初始化 GLM-ASR 適配器

        Args:
            model_id: HuggingFace 模型 ID
            device: 設備 ("auto", "cuda", "cpu")
            dtype: 數據類型 ("auto", "bfloat16", "float16", "float32")
            max_new_tokens: 生成的最大 token 數
        """
        self._model_id = model_id
        self._device = device
        self._dtype = dtype
        self._max_new_tokens = max_new_tokens

        self._model = None
        self._processor = None
        self._is_loaded = False
        self._actual_device = None

        logger.info(f"GLMASRAdapter 初始化: model_id={model_id}, device={device}")

    def load_model(self) -> bool:
        """載入 GLM-ASR 模型

        Returns:
            bool: 載入是否成功
        """
        try:
            import torch

            # 嘗試導入 GLM-ASR 專用類，如果失敗則使用通用類
            try:
                from transformers import GlmAsrForConditionalGeneration, AutoProcessor
                model_class = GlmAsrForConditionalGeneration
                logger.info("使用 GlmAsrForConditionalGeneration 類")
            except ImportError:
                from transformers import AutoModelForSeq2SeqLM, AutoProcessor
                model_class = AutoModelForSeq2SeqLM
                logger.info("使用 AutoModelForSeq2SeqLM 類 (GlmAsrForConditionalGeneration 不可用)")

            logger.info(f"正在載入 GLM-ASR 模型: {self._model_id}")

            # 確定數據類型
            if self._dtype == "auto":
                torch_dtype = "auto"
            elif self._dtype == "bfloat16":
                torch_dtype = torch.bfloat16
            elif self._dtype == "float16":
                torch_dtype = torch.float16
            else:
                torch_dtype = torch.float32

            # 載入處理器
            logger.info("載入處理器...")
            self._processor = AutoProcessor.from_pretrained(
                self._model_id,
                trust_remote_code=True
            )

            # 載入模型
            logger.info("載入模型...")
            self._model = model_class.from_pretrained(
                self._model_id,
                torch_dtype=torch_dtype,
                device_map=self._device,
                trust_remote_code=True
            )

            # 記錄實際設備
            if hasattr(self._model, 'device'):
                self._actual_device = str(self._model.device)
            else:
                self._actual_device = "auto"

            self._is_loaded = True
            logger.info(f"✅ GLM-ASR 模型載入成功: {self._model_id}")
            logger.info(f"   設備: {self._actual_device}")

            return True

        except ImportError as e:
            logger.error(f"依賴未安裝: {e}")
            logger.error("請執行: pip install git+https://github.com/huggingface/transformers")
            return False
        except Exception as e:
            logger.error(f"GLM-ASR 模型載入失敗: {e}")
            import traceback
            traceback.print_exc()
            return False

    # GLM-ASR 模型最大支持 655 秒，使用 600 秒作為安全閾值
    MAX_CHUNK_DURATION = 600  # 秒
    CHUNK_OVERLAP = 5  # 重疊秒數，確保連貫性

    def transcribe(self, audio: np.ndarray, sampling_rate: int = 16000,
                  language: str = "zh", task: str = "transcribe",
                  **kwargs) -> Dict[str, Any]:
        """使用 GLM-ASR 轉錄音頻

        Args:
            audio: 音頻數據 (numpy array, float32)
            sampling_rate: 採樣率
            language: 語言代碼 (zh, en, yue)
            task: 任務類型 (transcribe)
            **kwargs: 額外參數
                - max_new_tokens: int - 最大生成 token 數
                - do_sample: bool - 是否採樣（默認 False）

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

            audio_duration = len(audio) / sampling_rate

            # 如果音頻超過最大長度，分段處理
            if audio_duration > self.MAX_CHUNK_DURATION:
                logger.info(f"音頻時長 {audio_duration:.1f}s 超過 {self.MAX_CHUNK_DURATION}s，使用分段處理")
                return self._transcribe_long_audio(audio, sampling_rate, language, task, **kwargs)

            # 短音頻直接處理
            return self._transcribe_chunk(audio, sampling_rate, language, task, **kwargs)

        except Exception as e:
            logger.error(f"GLM-ASR 轉錄失敗: {e}")
            import traceback
            traceback.print_exc()
            return {"text": "", "error": str(e)}

    def _transcribe_long_audio(self, audio: np.ndarray, sampling_rate: int,
                               language: str, task: str, **kwargs) -> Dict[str, Any]:
        """分段處理長音頻

        Args:
            audio: 完整音頻數據
            sampling_rate: 採樣率
            language: 語言代碼
            task: 任務類型
            **kwargs: 額外參數

        Returns:
            Dict: 合併後的轉錄結果
        """
        start_time = time.time()
        total_duration = len(audio) / sampling_rate

        # 計算分段
        chunk_samples = self.MAX_CHUNK_DURATION * sampling_rate
        overlap_samples = self.CHUNK_OVERLAP * sampling_rate

        chunks = []
        chunk_start = 0
        while chunk_start < len(audio):
            chunk_end = min(chunk_start + chunk_samples, len(audio))
            chunks.append((chunk_start, chunk_end))
            chunk_start = chunk_end - overlap_samples
            if chunk_end >= len(audio):
                break

        logger.info(f"長音頻分段: {len(chunks)} 個片段，每段最長 {self.MAX_CHUNK_DURATION}s")

        # 處理每個分段
        all_texts = []
        all_segments = []
        current_offset = 0.0

        for i, (start_idx, end_idx) in enumerate(chunks):
            chunk_audio = audio[start_idx:end_idx]
            chunk_start_time = start_idx / sampling_rate
            chunk_duration = len(chunk_audio) / sampling_rate

            logger.info(f"處理片段 {i+1}/{len(chunks)}: {chunk_start_time:.1f}s - {chunk_start_time + chunk_duration:.1f}s")

            # 轉錄此分段
            result = self._transcribe_chunk(chunk_audio, sampling_rate, language, task, **kwargs)

            if "error" in result and result["error"]:
                logger.warning(f"片段 {i+1} 轉錄失敗: {result['error']}")
                continue

            text = result.get("text", "").strip()
            if text:
                all_texts.append(text)

                # 添加時間戳段落
                all_segments.append({
                    "start": chunk_start_time,
                    "end": chunk_start_time + chunk_duration,
                    "text": text
                })

        # 合併結果
        combined_text = "".join(all_texts)
        inference_time = time.time() - start_time

        logger.info(f"長音頻轉錄完成: {len(chunks)} 個片段，總文本 {len(combined_text)} 字符，耗時 {inference_time:.1f}s")

        return {
            "text": combined_text,
            "language": language,
            "task": task,
            "inference_time": inference_time,
            "model_size": self._model_id,
            "backend": "glm_asr",
            "segments": all_segments,
            "duration": total_duration,
            "chunks_processed": len(chunks)
        }

    def _transcribe_chunk(self, audio: np.ndarray, sampling_rate: int,
                          language: str, task: str, **kwargs) -> Dict[str, Any]:
        """轉錄單個音頻片段

        Args:
            audio: 音頻數據片段
            sampling_rate: 採樣率
            language: 語言代碼
            task: 任務類型
            **kwargs: 額外參數

        Returns:
            Dict: 轉錄結果
        """
        import torch

        start_time = time.time()

        # 獲取參數
        max_new_tokens = kwargs.get('max_new_tokens', self._max_new_tokens)
        do_sample = kwargs.get('do_sample', False)

        # 處理輸入
        logger.debug(f"處理音頻輸入: {len(audio)} 樣本, {sampling_rate} Hz")

        # 使用處理器處理音頻
        # GLM-ASR 使用 apply_transcription_request 方法
        if hasattr(self._processor, 'apply_transcription_request'):
            inputs = self._processor.apply_transcription_request(audio)
        else:
            # 備用方案：使用標準的處理方式
            inputs = self._processor(
                audio,
                sampling_rate=sampling_rate,
                return_tensors="pt"
            )

        # 移動到正確的設備和數據類型
        if hasattr(self._model, 'device') and hasattr(self._model, 'dtype'):
            inputs = inputs.to(self._model.device, dtype=self._model.dtype)
        elif hasattr(self._model, 'device'):
            inputs = inputs.to(self._model.device)

        # 生成輸出
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                do_sample=do_sample,
                max_new_tokens=max_new_tokens
            )

        # 解碼輸出
        # 跳過輸入部分，只取生成的部分
        if hasattr(inputs, 'input_ids'):
            input_length = inputs.input_ids.shape[1]
            decoded_outputs = self._processor.batch_decode(
                outputs[:, input_length:],
                skip_special_tokens=True
            )
        else:
            decoded_outputs = self._processor.batch_decode(
                outputs,
                skip_special_tokens=True
            )

        # 合併結果
        text = decoded_outputs[0] if decoded_outputs else ""

        inference_time = time.time() - start_time

        return {
            "text": text,
            "language": language,
            "task": task,
            "inference_time": inference_time,
            "model_size": self._model_id,
            "backend": "glm_asr",
            "segments": [],
            "duration": len(audio) / sampling_rate
        }

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
        logger.info("GLMASRAdapter 資源已清理")

    def get_model_info(self) -> Dict[str, Any]:
        """獲取模型信息"""
        return {
            "engine": "glm_asr",
            "backend": "transformers",
            "model_size": self._model_id,
            "device": self._actual_device or self._device,
            "is_loaded": self._is_loaded
        }

    @property
    def is_loaded(self) -> bool:
        """模型是否已載入"""
        return self._is_loaded

    @property
    def model_id(self) -> str:
        """獲取模型 ID"""
        return self._model_id

    def supports_vad(self) -> bool:
        """GLM-ASR 不內置 VAD"""
        return False

    def supports_word_timestamps(self) -> bool:
        """GLM-ASR 不直接支持詞級時間戳"""
        return False

    def get_supported_languages(self) -> List[str]:
        """獲取支持的語言"""
        return ["zh", "en", "yue"]  # 中文、英文、粵語
