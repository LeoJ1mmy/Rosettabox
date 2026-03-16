"""
音頻處理服務 - 模組化的音頻處理邏輯
"""
import os
import tempfile
import subprocess
import logging
import atexit  # 🔒 安全導入：用於資源清理
import librosa
import soundfile as sf
import numpy as np
from typing import Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
import asyncio

logger = logging.getLogger(__name__)

class AudioService:
    """音頻處理服務"""

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._ffmpeg_available = self._check_ffmpeg()
        # 🔒 安全修復：註冊關閉處理器，防止資源洩漏
        atexit.register(self.shutdown)

    def shutdown(self):
        """🔒 安全修復：優雅關閉線程池"""
        try:
            self.executor.shutdown(wait=True, cancel_futures=False)
            logger.info("✅ AudioService 線程池已關閉")
        except Exception as e:
            logger.warning(f"⚠️ AudioService 關閉時出錯: {e}")
        
    def _check_ffmpeg(self) -> bool:
        """檢查 FFmpeg 是否可用"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            logger.warning("FFmpeg 不可用")
            return False
    
    async def extract_audio_from_video_async(self, video_path: str, output_path: str) -> Tuple[bool, Optional[str]]:
        """異步從影片提取音頻"""
        if not self._ffmpeg_available:
            return False, "FFmpeg 未安裝"
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self._extract_audio_sync, 
            video_path, 
            output_path
        )
    
    def _extract_audio_sync(self, video_path: str, output_path: str) -> Tuple[bool, Optional[str]]:
        """同步提取音頻"""
        try:
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                '-y',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                return False, f"FFmpeg 錯誤: {result.stderr}"
            
            if not os.path.exists(output_path):
                return False, "輸出文件不存在"
            
            return True, None
            
        except subprocess.TimeoutExpired:
            return False, "音頻提取超時"
        except Exception as e:
            return False, str(e)
    
    def preprocess_audio(self, audio_path: str, target_sr: int = 16000) -> Tuple[np.ndarray, int]:
        """預處理音頻文件"""
        try:
            # 載入音頻
            audio, sr = librosa.load(audio_path, sr=target_sr, mono=True)
            
            # 正規化
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio))

            # 響度正規化（DRC + LUFS）
            try:
                from config import config as _cfg
                if _cfg.AUDIO_LOUDNESS_NORMALIZATION:
                    from processing.audio_normalization import normalize_loudness
                    logger.info("🔊 套用響度正規化 (DRC + LUFS)...")
                    audio = normalize_loudness(
                        audio, sample_rate=target_sr,
                        enable_drc=_cfg.AUDIO_DRC_ENABLED,
                        enable_lufs=_cfg.AUDIO_LUFS_ENABLED,
                        lufs_target=_cfg.AUDIO_LUFS_TARGET,
                        drc_threshold_db=_cfg.AUDIO_DRC_THRESHOLD,
                        drc_ratio=_cfg.AUDIO_DRC_RATIO,
                    )
            except Exception as e:
                logger.warning(f"⚠️ 響度正規化失敗，使用原始音頻: {e}")

            # 移除靜音
            audio = self._remove_silence(audio, sr)
            
            return audio, sr
            
        except Exception as e:
            logger.error(f"音頻預處理失敗: {str(e)}")
            raise
    
    def _remove_silence(self, audio: np.ndarray, sr: int, 
                       top_db: int = 20, frame_length: int = 2048) -> np.ndarray:
        """移除音頻中的靜音部分"""
        try:
            # 使用 librosa 的靜音檢測
            intervals = librosa.effects.split(audio, top_db=top_db, 
                                             frame_length=frame_length)
            
            if len(intervals) > 0:
                # 合併非靜音片段
                non_silent = []
                for start, end in intervals:
                    non_silent.append(audio[start:end])
                
                if non_silent:
                    return np.concatenate(non_silent)
            
            return audio
            
        except Exception as e:
            logger.warning(f"靜音移除失敗: {str(e)}")
            return audio
    
    def save_audio(self, audio: np.ndarray, sr: int, output_path: str):
        """保存音頻文件"""
        try:
            sf.write(output_path, audio, sr)
            logger.info(f"音頻已保存: {output_path}")
        except Exception as e:
            logger.error(f"音頻保存失敗: {str(e)}")
            raise
    
    def get_audio_info(self, audio_path: str) -> dict:
        """獲取音頻文件信息"""
        try:
            audio, sr = librosa.load(audio_path, sr=None)
            duration = len(audio) / sr
            
            return {
                'duration': duration,
                'sample_rate': sr,
                'channels': 1,  # mono
                'samples': len(audio),
                'format': os.path.splitext(audio_path)[1]
            }
        except Exception as e:
            logger.error(f"獲取音頻信息失敗: {str(e)}")
            return {}
    
    def split_audio_chunks(self, audio: np.ndarray, sr: int, 
                          chunk_duration: int = 30) -> list:
        """將音頻分割成塊"""
        chunk_samples = chunk_duration * sr
        chunks = []
        
        for i in range(0, len(audio), chunk_samples):
            chunk = audio[i:i + chunk_samples]
            if len(chunk) > sr:  # 至少1秒
                chunks.append(chunk)
        
        return chunks

# 單例模式
audio_service = AudioService()