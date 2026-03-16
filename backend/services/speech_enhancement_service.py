"""
語音增強服務 - ClearerVoice-Studio

使用 MossFormerGAN_SE_16K 或 FRCRN_SE_16K 模型進行語音增強，
凸顯人聲、抑制背景噪音。原生 16kHz 輸入輸出，完美匹配 Whisper。

注意：預設關閉。只在使用者判斷音頻品質差時啟用。
過度的神經網路增強可能改變頻譜特徵，反而傷害 ASR。

使用前需安裝:
    pip install clearvoice
"""

import logging
import gc
import tempfile
import os
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

# 模組級單例
_service_instance: Optional['SpeechEnhancementService'] = None


def get_speech_enhancement_service() -> 'SpeechEnhancementService':
    """取得語音增強服務單例"""
    global _service_instance
    if _service_instance is None:
        from config import config
        _service_instance = SpeechEnhancementService(
            model_name=config.AUDIO_SPEECH_ENHANCEMENT_MODEL,
        )
    return _service_instance


class SpeechEnhancementService:
    """ClearerVoice 語音增強服務"""

    def __init__(self, model_name: str = "MossFormerGAN_SE_16K"):
        """
        Args:
            model_name: ClearerVoice 模型名稱
                - MossFormerGAN_SE_16K: 最佳品質 (PESQ 3.57, STOI 98.05%)
                - FRCRN_SE_16K: 較輕量 (PESQ 3.24, STOI 97.73%)
        """
        self._model_name = model_name
        self._model = None
        self._is_loaded = False

    def load_model(self) -> bool:
        """載入 ClearerVoice 模型

        Returns:
            bool: 載入是否成功
        """
        if self._is_loaded:
            return True

        try:
            from clearvoice import ClearVoice

            logger.info(f"🔊 載入語音增強模型: {self._model_name}")
            self._model = ClearVoice(
                task='speech_enhancement',
                model_names=[self._model_name],
            )
            self._is_loaded = True
            logger.info(f"✅ 語音增強模型載入完成: {self._model_name}")
            return True

        except ImportError:
            logger.error("❌ clearvoice 未安裝，請執行: pip install clearvoice")
            return False
        except Exception as e:
            logger.error(f"❌ 語音增強模型載入失敗: {e}")
            return False

    def enhance(self, audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """增強音頻，凸顯人聲

        Args:
            audio: 輸入音頻 (float32, mono, 16kHz)
            sample_rate: 取樣率

        Returns:
            增強後的音頻 (float32)，失敗時返回原始音頻
        """
        if not self._is_loaded:
            if not self.load_model():
                logger.warning("語音增強模型未載入，返回原始音頻")
                return audio

        if len(audio) < sample_rate * 0.1:
            return audio

        if np.max(np.abs(audio)) < 1e-6:
            return audio

        try:
            import soundfile as sf

            # ClearerVoice 需要檔案路徑輸入，建立臨時檔案
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                sf.write(f.name, audio, sample_rate)
                temp_input = f.name

            try:
                enhanced = self._model(input_path=temp_input, online_write=False)

                # ClearerVoice 回傳 numpy array 或 dict
                if isinstance(enhanced, dict):
                    # 取第一個結果
                    enhanced = list(enhanced.values())[0]
                if isinstance(enhanced, np.ndarray):
                    # 確保形狀正確
                    if len(enhanced.shape) > 1:
                        enhanced = enhanced.flatten()
                    enhanced = enhanced.astype(np.float32)

                    # 正規化到 [-1, 1]
                    max_val = np.max(np.abs(enhanced))
                    if max_val > 0:
                        enhanced = enhanced / max_val

                    logger.info(f"🔊 語音增強完成: {len(enhanced)} samples")
                    return enhanced
                else:
                    logger.warning(f"語音增強輸出格式不符預期: {type(enhanced)}")
                    return audio

            finally:
                try:
                    os.unlink(temp_input)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"語音增強失敗: {e}")
            return audio

    def cleanup(self):
        """釋放模型資源"""
        if self._model is not None:
            del self._model
            self._model = None
            self._is_loaded = False
            gc.collect()

            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

            logger.info("🧹 語音增強模型已釋放")

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def __del__(self):
        self.cleanup()
