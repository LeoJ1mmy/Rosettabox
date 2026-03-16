"""
音頻處理模組 - 從 app.py 提取的音頻處理邏輯
"""
import logging
import time
import numpy as np
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def process_audio_with_whisper(filepath, config_data, task_id, progress_callback=None):
    """使用 Whisper 進行語音識別 - 支持長音頻分段處理

    Args:
        filepath: 音頻文件路徑
        config_data: 處理配置
        task_id: 任務 ID
        progress_callback: 進度回調函數 callback(stage, percentage, message)
    """
    try:
        from .progress_stages import STAGE_ASR, STAGE_PREPARING

        start_time = time.time()
        # 動態導入避免循環依賴
        try:
            import app
            qm = app.get_queue_manager()
        except:
            qm = None
        if progress_callback:
            progress_callback(STAGE_PREPARING, 5, "載入音頻")

        try:
            from services.asr_service import get_asr_service
            from config import config

            # 獲取 ASR 引擎類型
            asr_engine_type = config_data.get('asr_engine', config.ASR_ENGINE)

            # 使用 ASR 服務獲取引擎（適配器模式，支持多種引擎）
            asr = get_asr_service()
            manager = asr.get_engine(engine_type=asr_engine_type)

            if not manager.load_model():
                raise Exception("ASR 模型加載失敗")

            # 獲取引擎信息
            engine_info = manager.get_model_info()
            engine_name = engine_info.get("engine", "unknown")
            model_name = engine_info.get("model_size", "unknown")
            backend_name = engine_info.get("backend", "unknown")
            logger.info(f"📢 使用 {engine_name} 引擎進行語音識別 (模型: {model_name}, 後端: {backend_name})")

        except ImportError as e:
            logger.warning(f"⚠️ ASR 服務不可用: {e}，使用模擬結果")
            return {
                'text': f"模擬的語音識別結果：這是從 {filepath} 提取的文字內容",
                'text_with_timestamps': '[00:00-01:30] 模擬的語音識別結果'
            }
        
        # 從配置獲取最大音頻長度限制
        from config import config
        max_audio_duration = config.AUDIO_MAX_DURATION
        logger.info(f"📋 音頻長度限制: {max_audio_duration} 秒 ({max_audio_duration/3600:.1f} 小時)" if max_audio_duration > 0 else "📋 音頻長度限制: 無限制")

        audio, sr = preprocess_audio(filepath, max_duration_seconds=max_audio_duration, progress_callback=progress_callback)
        if audio is None:
            raise Exception("音頻預處理失敗")

        if progress_callback:
            progress_callback(STAGE_ASR, 15, "開始語音識別")

        audio_duration = len(audio) / sr
        logger.info(f"🎵 音頻預處理完成: {len(audio)} 樣本, {audio_duration:.1f} 秒 ({audio_duration/3600:.2f} 小時)")
        
        # 直接處理整個音頻（faster-whisper 可以處理長音頻）
        # 不再使用分塊處理，因為分塊處理會導致轉錄品質下降
        if audio_duration <= 7200:  # 2小時以內直接處理
            logger.info(f"🎤 直接處理整個音頻 ({audio_duration/60:.1f} 分鐘)")
            try:
                result = manager.transcribe(
                    audio,
                    sampling_rate=sr,
                    language="zh",
                    task="transcribe",
                    progress_callback=progress_callback
                )

                if "error" in result:
                    raise Exception(f"轉錄失敗: {result.get('error')}")

                text = result.get("text", "")
                logger.info(f"✅ 直接轉錄完成: {len(text)} 字符")
                if progress_callback:
                    progress_callback(STAGE_ASR, 58, "語音識別完成")
                
                # 使用時間戳信息（支持多種格式）
                # 優先使用 segments（標準化格式），其次 timestamps
                segments = result.get("segments", []) or result.get("timestamps", [])
                text_with_timestamps = ""
                if segments:
                    timestamp_lines = []
                    for ts in segments:
                        # 支持 dict 格式: {"start": x, "end": y, "text": z}
                        # 支持 list 格式: [start_ms, end_ms, text] (FunASR)
                        if isinstance(ts, dict):
                            seg_start = ts.get('start', 0)
                            seg_end = ts.get('end', 0)
                            text_part = ts.get('text', '').strip()
                        elif isinstance(ts, (list, tuple)) and len(ts) >= 2:
                            # FunASR 格式: [start_ms, end_ms, text?]
                            seg_start = ts[0] / 1000.0 if ts[0] > 1000 else ts[0]  # 毫秒轉秒
                            seg_end = ts[1] / 1000.0 if ts[1] > 1000 else ts[1]
                            text_part = str(ts[2]).strip() if len(ts) > 2 else ""
                        else:
                            continue
                        if text_part:
                            start_min = int(seg_start // 60)
                            start_sec = int(seg_start % 60)
                            end_min = int(seg_end // 60)
                            end_sec = int(seg_end % 60)
                            time_str = f"[{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}]"
                            timestamp_lines.append(f"{time_str} {text_part}")
                    text_with_timestamps = "\n".join(timestamp_lines)

                if not text_with_timestamps:
                    # 回退到簡單時間戳
                    text_with_timestamps = f"[00:00-{int(audio_duration//60):02d}:{int(audio_duration%60):02d}] {text}"
                
                processing_time = time.time() - start_time
                asr.cleanup()
                
                return {
                    'text': text,
                    'text_with_timestamps': text_with_timestamps,
                    'processing_time': processing_time,
                    'segments_count': len(segments) if segments else 1,
                    'total_chunks': 1,
                    'processing_method': 'direct',
                }
                
            except Exception as e:
                logger.error(f"❌ 轉錄失敗: {str(e)}")
                raise  # 不再回退到分塊處理
        
        # 對於長音頻，使用優化的分塊處理
        chunk_length = 120 * sr  # 調整為120秒塊以提供更好的轉錄連貫性
        overlap_length = 5 * sr  # 5秒重疊（較大分塊使用較大重疊）
        
        chunks = []
        for i in range(0, len(audio), chunk_length - overlap_length):
            end_idx = min(i + chunk_length, len(audio))
            chunks.append(audio[i:end_idx])
            if end_idx >= len(audio):
                break
        
        logger.info(f"📦 音頻分塊完成: {len(chunks)} 個塊, 每塊約 {chunk_length/sr:.1f} 秒")
        
        all_text = []
        all_text_with_timestamps = []
        previous_text = ""
        
        for i, chunk in enumerate(chunks):
            if qm and qm.is_task_cancelled(task_id):
                raise Exception("任務已取消")

            if progress_callback:
                fraction = (i + 1) / len(chunks)
                progress_callback(STAGE_ASR, 20 + fraction * 35, f"Whisper 處理中 ({i+1}/{len(chunks)})")
                
            if len(chunk) < sr * 0.1:
                continue
                
            try:
                logger.info(f"🎤 開始轉錄塊 {i+1}/{len(chunks)} (長度: {len(chunk)/sr:.1f}秒)")
                result = manager.transcribe(
                    chunk, 
                    sampling_rate=sr,
                    language="zh", 
                    task="transcribe"
                )
                
                if "error" in result:
                    chunk_text = ""
                    logger.warning(f"⚠️ 塊 {i+1} 轉錄錯誤: {result.get('error')}")
                else:
                    chunk_text = result.get("text", "")
                    logger.info(f"✅ 塊 {i+1} 轉錄完成: '{chunk_text[:50]}{'...' if len(chunk_text) > 50 else ''}'")
                    
            except Exception as e:
                chunk_text = ""
                logger.error(f"❌ 塊 {i+1} 轉錄異常: {str(e)}")
            
            from .text_processing import clean_whisper_output, advanced_text_deduplication
            chunk_text = clean_whisper_output(chunk_text)
            
            if chunk_text and len(chunk_text.strip()) > 0:
                chunk_text = advanced_text_deduplication(chunk_text)
                
                if i > 0 and previous_text:
                    chunk_text = remove_overlap_with_previous(previous_text, chunk_text)
                
                if chunk_text.strip():
                    start_seconds = i * (chunk_length - overlap_length) / sr
                    end_seconds = min(start_seconds + chunk_length / sr, len(audio) / sr)
                    
                    start_time_str = f"{int(start_seconds // 60):02d}:{int(start_seconds % 60):02d}"
                    end_time_str = f"{int(end_seconds // 60):02d}:{int(end_seconds % 60):02d}"
                    
                    all_text.append(chunk_text)
                    all_text_with_timestamps.append(f"[{start_time_str}-{end_time_str}] {chunk_text}")
                    previous_text = chunk_text
        
        if qm and qm.is_task_cancelled(task_id):
            raise Exception("任務已取消")
        
        # 🔧 修復：改進文本合併邏輯，避免重複和丟失
        raw_final_text = " ".join(all_text) if all_text else ""  # 使用空格連接避免換行切斷
        final_text_with_timestamps = "\\n".join(all_text_with_timestamps) if all_text_with_timestamps else ""
        
        logger.info(f"🔧 文本合併結果: 原始長度 {len(raw_final_text)} 字符")
        logger.info(f"🔧 原始合併文本預覽: {raw_final_text[:200]}...")
        
        # 後處理文本
        from .text_processing import enhanced_post_processing_pipeline
        final_text = enhanced_post_processing_pipeline(raw_final_text)
        
        logger.info(f"🔧 後處理結果: 最終長度 {len(final_text)} 字符")
        logger.info(f"🔧 最終文本預覽: {final_text[:200]}...")
        
        processing_time = time.time() - start_time
        
        logger.info(f"🎯 轉錄完成統計:")
        logger.info(f"   總字符數: {len(final_text)}")
        logger.info(f"   有效段落: {len(all_text)}")
        logger.info(f"   處理時間: {processing_time:.1f}秒")
        logger.info(f"   處理方法: 分塊處理")
        
        try:
            asr.cleanup()
        except Exception:
            pass

        return {
            'text': final_text,
            'text_with_timestamps': final_text_with_timestamps,
            'processing_time': processing_time,
            'segments_count': len(all_text),
            'total_chunks': len(chunks),
            'processing_method': 'chunked'
        }

    except Exception as e:
        logger.error(f"❌ 語音識別失敗: {str(e)}")

        try:
            if 'asr' in locals():
                asr.cleanup()
        except Exception:
            pass
        
        return {
            'text': f"語音識別失敗：{str(e)}",
            'text_with_timestamps': f"[00:00-01:30] 語音識別失敗：{str(e)}"
        }

def clean_whisper_model_name(whisper_model):
    """清理 Whisper 模型名稱"""
    model_name_mapping = {
        'Tiny (快速，較低準確度)': 'tiny',
        'Base (平衡)': 'base', 
        'Small (較準確)': 'small',
        'Medium (高準確度)': 'medium',
        'Large (最高準確度)': 'large'
    }
    
    clean_model_name = whisper_model
    for display_name, actual_name in model_name_mapping.items():
        if display_name in whisper_model:
            clean_model_name = actual_name
            break
    
    import re
    clean_model_name = re.sub(r'\\s*-\\s*~.*[MG]B.*$', '', clean_model_name)
    clean_model_name = re.sub(r'\\s*\\(.*\\).*$', '', clean_model_name).strip()
    
    valid_models = ['tiny', 'base', 'small', 'medium', 'large']
    if clean_model_name not in valid_models:
        for model in valid_models:
            if model in clean_model_name.lower():
                clean_model_name = model
                break
        else:
            clean_model_name = 'base'
    
    return clean_model_name

def preprocess_audio(audio_path, max_duration_seconds=None, progress_callback=None):
    """預處理音頻文件，支援多種格式包括MP4

    Args:
        audio_path: 音頻文件路徑
        max_duration_seconds: 最大音頻長度限制（秒）
                             None = 使用配置值
                             0 = 無限制
                             >0 = 具體限制
        progress_callback: 進度回調函數 callback(stage, percentage, message)
    """
    try:
        import librosa
        import os
        import tempfile
        import subprocess

        # 如果未指定限制，從配置獲取
        if max_duration_seconds is None:
            from config import config
            max_duration_seconds = config.AUDIO_MAX_DURATION
            logger.info(f"📋 使用配置的音頻長度限制: {max_duration_seconds} 秒 ({max_duration_seconds/3600:.1f} 小時)" if max_duration_seconds > 0 else "📋 使用配置：無音頻長度限制")
        
        # 檢查文件是否存在
        if not os.path.exists(audio_path):
            logger.error(f"音頻文件不存在: {audio_path}")
            return None, None
            
        # 獲取文件擴展名
        file_ext = os.path.splitext(audio_path)[1].lower()
        logger.info(f"處理音頻文件: {audio_path}, 格式: {file_ext}")
        
        # 如果是MP4或其他視頻格式，先轉換為WAV
        if file_ext in ['.mp4', '.mov', '.avi', '.mkv', '.flv']:
            logger.info(f"檢測到視頻格式 {file_ext}，正在提取音頻...")
            
            # 創建臨時WAV文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name
            
            try:
                # 使用ffmpeg提取音頻
                ffmpeg_cmd = [
                    'ffmpeg', '-i', audio_path,
                    '-vn',  # 不包含視頻
                    '-acodec', 'pcm_s16le',  # 使用PCM編碼
                    '-ar', '16000',  # 採樣率16kHz
                    '-ac', '1',  # 單聲道
                    '-y',  # 覆蓋輸出文件
                    temp_wav_path
                ]
                
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"ffmpeg轉換失敗: {result.stderr}")
                    # 嘗試直接用librosa加載
                    audio_path_to_load = audio_path
                else:
                    logger.info("ffmpeg音頻提取成功")
                    audio_path_to_load = temp_wav_path
                    
            except FileNotFoundError:
                logger.warning("未找到ffmpeg，嘗試直接使用librosa加載...")
                audio_path_to_load = audio_path
            except Exception as e:
                logger.warning(f"ffmpeg轉換出錯: {e}，嘗試直接使用librosa加載...")
                audio_path_to_load = audio_path
        else:
            audio_path_to_load = audio_path
        
        # 優先使用 soundfile（最可靠，避免 librosa 的 deprecation warning）
        try:
            import soundfile as sf
            audio, sr = sf.read(audio_path_to_load, dtype='float32')
            logger.info(f"✅ soundfile 加載成功: 原始長度={len(audio)}, 採樣率={sr}")

            # 多聲道轉單聲道
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)
                logger.info(f"   轉換為單聲道")

            # 重採樣到16kHz（如果需要）
            if sr != 16000:
                logger.info(f"   重採樣: {sr}Hz → 16000Hz")
                audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                sr = 16000

            logger.info(f"   最終音頻: 長度={len(audio)}, 採樣率={sr}Hz")

        except ImportError:
            # soundfile 未安裝，使用 librosa（可能觸發 deprecation warning）
            logger.warning("⚠️ soundfile 未安裝，降級使用 librosa（可能觸發 deprecation warning）")
            logger.warning("💡 建議安裝 soundfile: pip install soundfile")
            try:
                audio, sr = librosa.load(audio_path_to_load, sr=16000, mono=True, dtype=np.float32)
                logger.info(f"✅ librosa 加載成功: 長度={len(audio)}, 採樣率={sr}")
            except Exception as e:
                logger.error(f"❌ librosa 加載失敗: {e}")
                return None, None

        except Exception as e:
            # soundfile 失敗，嘗試 librosa 作為後備
            logger.warning(f"⚠️ soundfile 加載失敗: {e}")
            logger.info(f"   嘗試使用 librosa 後備方案...")
            try:
                audio, sr = librosa.load(audio_path_to_load, sr=16000, mono=True, dtype=np.float32)
                logger.info(f"✅ librosa 加載成功: 長度={len(audio)}, 採樣率={sr}")
            except Exception as e2:
                logger.error(f"❌ 所有音頻加載方法都失敗:")
                logger.error(f"   soundfile 錯誤: {e}")
                logger.error(f"   librosa 錯誤: {e2}")
                return None, None
        
        # 清理臨時文件
        if file_ext in ['.mp4', '.mov', '.avi', '.mkv', '.flv'] and 'temp_wav_path' in locals():
            try:
                os.unlink(temp_wav_path)
            except:
                pass
        
        # 音頻後處理
        if len(audio) == 0:
            logger.error("音頻文件為空")
            return None, None
            
        # 標準化音量
        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio))

        # 音頻增強管線：High-Pass → Noise Reduction → DRC + LUFS
        try:
            from config import config as _cfg
            from .progress_stages import STAGE_AUDIO_ENHANCEMENT, STAGE_NORMALIZATION

            # P1: 高通濾波（移除低頻隆隆聲）
            if _cfg.AUDIO_HIGHPASS_ENABLED:
                from processing.audio_normalization import apply_highpass_filter
                if progress_callback:
                    progress_callback(STAGE_AUDIO_ENHANCEMENT, 7, "高通濾波中...")
                audio = apply_highpass_filter(
                    audio, sample_rate=16000,
                    cutoff_hz=_cfg.AUDIO_HIGHPASS_CUTOFF_HZ,
                )

            # P0: 頻譜閘門降噪（預設關閉）
            if _cfg.AUDIO_NOISE_REDUCTION_ENABLED:
                from processing.audio_normalization import apply_noise_reduction
                if progress_callback:
                    progress_callback(STAGE_AUDIO_ENHANCEMENT, 8, "降噪處理中...")
                audio = apply_noise_reduction(
                    audio, sample_rate=16000,
                    stationary=_cfg.AUDIO_NOISE_REDUCTION_STATIONARY,
                    prop_decrease=_cfg.AUDIO_NOISE_REDUCTION_STRENGTH,
                )

            # 響度正規化（DRC + LUFS）
            if _cfg.AUDIO_LOUDNESS_NORMALIZATION:
                from processing.audio_normalization import normalize_loudness
                if progress_callback:
                    progress_callback(STAGE_NORMALIZATION, 9, "響度正規化中...")
                logger.info("🔊 套用響度正規化 (DRC + LUFS)...")
                audio = normalize_loudness(
                    audio, sample_rate=16000,
                    enable_drc=_cfg.AUDIO_DRC_ENABLED,
                    enable_lufs=_cfg.AUDIO_LUFS_ENABLED,
                    lufs_target=_cfg.AUDIO_LUFS_TARGET,
                    drc_threshold_db=_cfg.AUDIO_DRC_THRESHOLD,
                    drc_ratio=_cfg.AUDIO_DRC_RATIO,
                )
                if progress_callback:
                    progress_callback(STAGE_NORMALIZATION, 12, "響度正規化完成")

            # P3: 語音增強（神經網路，預設關閉）
            if _cfg.AUDIO_SPEECH_ENHANCEMENT_ENABLED:
                try:
                    from services.speech_enhancement_service import get_speech_enhancement_service
                    se_service = get_speech_enhancement_service()
                    if progress_callback:
                        progress_callback(STAGE_AUDIO_ENHANCEMENT, 13, "語音增強中...")
                    logger.info(f"🔊 套用語音增強 ({_cfg.AUDIO_SPEECH_ENHANCEMENT_MODEL})...")
                    audio = se_service.enhance(audio, sample_rate=16000)
                    if progress_callback:
                        progress_callback(STAGE_AUDIO_ENHANCEMENT, 14, "語音增強完成")
                except Exception as e:
                    logger.warning(f"⚠️ 語音增強失敗，使用原始音頻: {e}")

        except Exception as e:
            logger.warning(f"⚠️ 音頻增強/正規化失敗，使用原始音頻: {e}")

        # 去除靜音
        audio, _ = librosa.effects.trim(audio, top_db=20)
        
        # 限制最大長度（如果設置了限制）
        if max_duration_seconds > 0:  # 0 表示無限制
            max_length = 16000 * max_duration_seconds
            audio_duration_seconds = len(audio) / sr
            if len(audio) > max_length:
                logger.warning(f"⚠️ 音頻長度 {audio_duration_seconds:.1f} 秒超過限制 {max_duration_seconds} 秒")
                logger.warning(f"⚠️ 將截取前 {max_duration_seconds} 秒，剩餘 {audio_duration_seconds - max_duration_seconds:.1f} 秒將被忽略")
                logger.warning(f"💡 提示：如需處理完整音頻，請在 .env 中設置 AUDIO_MAX_DURATION=0（無限制）或更大的值")
                audio = audio[:max_length]
            else:
                logger.info(f"✅ 音頻長度 {audio_duration_seconds:.1f} 秒在限制內 (max: {max_duration_seconds} 秒)")
        else:
            audio_duration_seconds = len(audio) / sr
            logger.info(f"✅ 無音頻長度限制，完整處理 {audio_duration_seconds:.1f} 秒")
        
        # 確保最小長度
        min_length = int(0.1 * sr)
        if len(audio) < min_length:
            logger.info("音頻太短，進行填充")
            audio = np.pad(audio, (0, min_length - len(audio)), mode='constant')
            
        logger.info(f"音頻預處理完成: 最終長度={len(audio)}, 持續時間={len(audio)/sr:.2f}秒")
        return audio, sr
        
    except Exception as e:
        logger.error(f"音頻預處理失敗: {str(e)}")
        logger.exception("詳細錯誤信息:")
        return None, None

def remove_overlap_with_previous(previous_text, current_text):
    """移除與前一段的重疊部分"""
    if not previous_text or not current_text:
        return current_text
    
    prev_words = previous_text.split()[-10:]
    curr_words = current_text.split()[:10]
    
    overlap_count = 0
    for i in range(min(len(prev_words), len(curr_words))):
        if prev_words[-(i+1)] == curr_words[i]:
            overlap_count = i + 1
        else:
            break
    
    if overlap_count > 2:
        return ' '.join(current_text.split()[overlap_count:])

    return current_text
