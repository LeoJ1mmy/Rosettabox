"""
任務處理器 - 從 app.py 提取的任務處理邏輯
"""
import logging
import time
import os
import subprocess
from typing import Dict, Any, Optional

from config import config as app_config

from .progress_stages import (
    STAGE_PREPARING, STAGE_ASR,
    STAGE_REFINEMENT, STAGE_AI_PROCESSING, STAGE_COMPLETED,
    ProgressTracker,
)

logger = logging.getLogger(__name__)


class TaskCancelledException(Exception):
    """任務被取消時拋出的異常"""
    pass


def check_task_cancelled(task_id: str, stage: str = "") -> None:
    """
    檢查任務是否已被取消，如果已取消則拋出異常

    Args:
        task_id: 任務 ID
        stage: 當前處理階段（用於日誌記錄）

    Raises:
        TaskCancelledException: 如果任務已被取消
    """
    try:
        import app
        qm = app.get_queue_manager()
        if qm and qm.is_task_cancelled(task_id):
            stage_info = f" (階段: {stage})" if stage else ""
            logger.info(f"🚫 任務 {task_id} 已被取消{stage_info}，停止處理")
            raise TaskCancelledException(f"任務已被用戶取消{stage_info}")
    except ImportError:
        pass  # 如果無法導入 app，繼續執行

def cleanup_cuda_memory():
    """清理 CUDA 記憶體緩存"""
    import gc
    import torch
    try:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception as e:
        logger.warning(f"CUDA 記憶體清理失敗: {e}")

def unload_ollama_model():
    """釋放 Ollama 中載入的模型以節省 GPU 記憶體"""
    try:
        import requests
        from config import config
        
        response = requests.get(f"{config.OLLAMA_URL}/api/ps", timeout=10)
        if response.status_code == 200:
            models = response.json().get('models', [])
            if models:
                for model in models:
                    model_name = model.get('name', '')
                    if model_name:
                        unload_response = requests.post(
                            f"{config.OLLAMA_URL}/api/generate",
                            json={"model": model_name, "keep_alive": 0},
                            timeout=10
                        )
                        pass
                pass
            else:
                pass
        else:
            logger.warning(f"無法獲取 Ollama 模型狀態: {response.status_code}")
    except Exception as e:
        logger.warning(f"釋放 Ollama 模型失敗: {e}")


def _docker_api(method, path, timeout=30):
    """透過 Docker socket API 操作容器（不需要 docker CLI）

    Args:
        method: HTTP 方法 (GET/POST)
        path: API 路徑 (e.g. /containers/vllm-server/stop)
        timeout: 超時秒數

    Returns:
        (status_code, body) tuple
    """
    import socket
    import http.client

    DOCKER_SOCKET = "/var/run/docker.sock"

    class _DockerConn(http.client.HTTPConnection):
        def __init__(self, sock_path, conn_timeout):
            super().__init__("localhost", timeout=conn_timeout)
            self._sock_path = sock_path

        def connect(self):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect(self._sock_path)

    conn = _DockerConn(DOCKER_SOCKET, timeout)
    try:
        conn.request(method, path)
        resp = conn.getresponse()
        body = resp.read().decode('utf-8', errors='replace')
        return resp.status, body
    finally:
        conn.close()


def _is_vllm_running():
    """檢查 vLLM 容器是否在運行"""
    try:
        import json
        status, body = _docker_api("GET", "/containers/vllm-server/json", timeout=5)
        if status == 200:
            data = json.loads(body)
            return data.get("State", {}).get("Running", False)
        return False
    except Exception:
        return False


def _stop_vllm_container():
    """停止 vLLM Docker 容器以釋放 GPU 記憶體（確保一定關閉）"""
    try:
        from config import config
        if config.REFINEMENT_ENGINE != "vllm" or config.AI_ENGINE != "ollama":
            return False

        if not _is_vllm_running():
            logger.info("ℹ️ vLLM 容器未運行，無需停止")
            return False

        logger.info("🛑 停止 vLLM 容器以釋放 GPU 記憶體...")

        # 第 1 步：優雅停止（等 10 秒）
        status, _ = _docker_api("POST", "/containers/vllm-server/stop?t=10", timeout=30)

        # 第 2 步：驗證
        if _is_vllm_running():
            # 第 3 步：強制 kill
            logger.warning("⚠️ stop 未生效，強制 kill...")
            _docker_api("POST", "/containers/vllm-server/kill", timeout=15)
            time.sleep(2)

        # 等待 GPU 記憶體釋放
        time.sleep(3)
        cleanup_cuda_memory()

        # 最終確認
        if _is_vllm_running():
            logger.error("❌ vLLM 容器仍在運行！無法釋放 GPU 記憶體")
            return False

        logger.info("✅ vLLM 容器已確認停止，GPU 記憶體已釋放")
        return True

    except Exception as e:
        logger.warning(f"⚠️ 停止 vLLM 容器異常: {e}")
        # 最後手段：嘗試 kill
        try:
            _docker_api("POST", "/containers/vllm-server/kill", timeout=10)
            time.sleep(3)
            cleanup_cuda_memory()
            return True
        except Exception:
            logger.error("❌ 強制 kill vLLM 也失敗")
            return False


def _start_vllm_container(wait_ready=False):
    """啟動 vLLM Docker 容器

    Args:
        wait_ready: 是否等待 vLLM 模型載入完成（健康檢查通過）
    """
    try:
        from config import config
        if config.REFINEMENT_ENGINE != "vllm" or config.AI_ENGINE != "ollama":
            return False

        # 如果已在運行，只需等就緒
        if _is_vllm_running():
            logger.info("ℹ️ vLLM 容器已在運行")
            if wait_ready:
                _wait_for_vllm_ready()
            return True

        logger.info("🔄 啟動 vLLM 容器...")
        status, body = _docker_api("POST", "/containers/vllm-server/start", timeout=30)

        if status == 204 or status == 304:  # 204=started, 304=already running
            logger.info("✅ vLLM 容器已啟動")
            # 清除快取
            try:
                from services.ai_engine_service import refinement_engine_manager
                if hasattr(refinement_engine_manager, '_engine') and refinement_engine_manager._engine is not None:
                    if hasattr(refinement_engine_manager._engine, '_cached_max_model_len'):
                        refinement_engine_manager._engine._cached_max_model_len = None
            except Exception:
                pass
            if wait_ready:
                _wait_for_vllm_ready()
            return True
        else:
            logger.warning(f"⚠️ 啟動 vLLM 容器失敗: HTTP {status} - {body[:200]}")
            return False
    except Exception as e:
        logger.warning(f"⚠️ 啟動 vLLM 容器異常: {e}")
        return False


def _wait_for_vllm_ready(max_wait=180, interval=5):
    """等待 vLLM 服務就緒（模型載入完成）

    Args:
        max_wait: 最大等待秒數（預設 180 秒 = 3 分鐘）
        interval: 輪詢間隔秒數
    """
    import requests
    from config import config

    url = f"{config.VLLM_URL}/v1/models"
    elapsed = 0
    logger.info(f"⏳ 等待 vLLM 模型載入就緒 (最多 {max_wait}s)...")

    while elapsed < max_wait:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                models = resp.json().get('data', [])
                if models:
                    logger.info(f"✅ vLLM 就緒，模型: {models[0].get('id', 'unknown')}，等待 {elapsed}s")
                    return True
        except Exception:
            pass
        time.sleep(interval)
        elapsed += interval
        if elapsed % 30 == 0:
            logger.info(f"⏳ vLLM 模型載入中... ({elapsed}s/{max_wait}s)")

    logger.warning(f"⚠️ vLLM 在 {max_wait}s 內未就緒，繼續執行")
    return False


def process_task(task):
    """處理單個任務 - 支援音頻和文字處理"""
    task_id = None
    try:
        # 支援多種 task_id 字段名稱
        task_id = task.get('task_id') or task.get('id') or task.get('taskId')
        if not task_id:
            raise ValueError("任務中未找到 task_id 字段")

        # 🔧 修復：開始處理前檢查是否已取消
        check_task_cancelled(task_id, "任務開始")

        task_type = task.get('task_type', 'audio_processing')

        logger.info(f"📋 開始處理任務: {task_id}, 類型: {task_type}")

        if task_type == 'text_processing':
            process_text_task(task)
        else:
            process_audio_task(task)

    except TaskCancelledException:
        # 🔧 修復：任務取消是正常流程，不需要調用 fail_task
        logger.info(f"🚫 任務 {task_id} 已被取消，正常終止處理")
        cleanup_cuda_memory()
        unload_ollama_model()
    except Exception as e:
        logger.error(f"❌ 任務處理失敗: {task_id or '未知'} - {str(e)}")
        # 動態導入避免循環依賴
        try:
            import app
            qm = app.get_queue_manager()
        except:
            qm = None
        # 🔧 修復：只有在任務未被取消時才標記失敗
        if qm and task_id and not qm.is_task_cancelled(task_id):
            qm.fail_task(task_id, str(e))
        cleanup_cuda_memory()
        unload_ollama_model()

def process_text_task(task):
    """處理文字處理任務"""
    task_id = None
    try:
        # 支援多種 task_id 字段名稱
        task_id = task.get('task_id') or task.get('id') or task.get('taskId')
        if not task_id:
            raise ValueError("任務中未找到 task_id 字段")

        # 🔧 修復：處理前檢查取消狀態
        check_task_cancelled(task_id, "文字處理開始")

        task_data = task.get('task_data', {})
        config_data = task.get('processing_config', {}) or task.get('config', {})
        user_id = task.get('user_id')

        text = task_data.get('text', '')
        if not text:
            raise Exception("文字內容為空")

        logger.info(f"📝 處理文字任務: {task_id}, 文字長度: {len(text)}")

        # 動態導入避免循環依賴
        try:
            import app
            qm = app.get_queue_manager()
        except:
            qm = None

        from .progress_stages import STAGE_TEXT_PREPARING, STAGE_TEXT_CLEANING, STAGE_TEXT_AI_PROCESSING, STAGE_COMPLETED

        if qm:
            qm.update_task_progress(task_id, STAGE_TEXT_PREPARING, 10)

        processing_mode = config_data.get('processing_mode', 'default')
        detail_level = config_data.get('detail_level', 'normal')
        ai_model = config_data.get('ai_model', 'phi4-mini:3.8b')
        selected_tags = config_data.get('selected_tags', [])
        enable_clean_filler = config_data.get('enable_clean_filler', False)

        # 口語贅字清理（如果啟用）
        if enable_clean_filler:
            try:
                if qm:
                    qm.update_task_progress(task_id, STAGE_TEXT_CLEANING, 20)
                from .text_refinement import clean_filler_words
                text = clean_filler_words(text)
                logger.info(f"📝 口語贅字清理完成，文字長度: {len(text)}")
            except ImportError:
                logger.warning("text_refinement 模組不可用，跳過口語贅字清理")
            except Exception as e:
                logger.warning(f"口語贅字清理失敗: {e}，使用原始文字")

        # 🔧 修復：AI 處理前檢查取消狀態
        check_task_cancelled(task_id, "AI 處理前")

        if qm:
            qm.update_task_progress(task_id, STAGE_TEXT_AI_PROCESSING, 40)

        # 在 AI 處理前清理 GPU 記憶體
        logger.info("🧹 AI 處理前清理 GPU 記憶體...")
        cleanup_cuda_memory()

        from .text_processing import organize_text_with_ollama
        processed_text = organize_text_with_ollama(
            text, processing_mode, detail_level, ai_model,
            config_data.get('custom_mode_prompt'),
            config_data.get('custom_detail_prompt'),
            config_data.get('custom_format_template'),
            selected_tags,
            config_data.get('custom_prompt'),  # 🔧 修復：添加 custom_prompt 參數
            task_id=task_id  # 🔧 修復：傳遞 task_id 以支援取消檢查
        )

        # 🔧 修復：AI 處理後檢查取消狀態
        check_task_cancelled(task_id, "AI 處理後")

        # 🧹 AI 處理後：卸載 Ollama 模型 + 清理 GPU 記憶體
        logger.info("🧹 AI 處理後卸載 Ollama 模型並清理 GPU 記憶體...")
        unload_ollama_model()
        cleanup_cuda_memory()

        if qm:
            qm.update_task_progress(task_id, STAGE_COMPLETED, 100)

        result = {
            'original_text': text,
            'processed_text': processed_text,
            # 前端期望的字段名稱
            'whisper_result': text,           # 原始文字（對應 Whisper 結果）
            'ai_summary': processed_text,     # AI 處理結果
            'result': processed_text,         # 保持兼容性
            'processing_mode': processing_mode,
            'detail_level': detail_level,
            'ai_model': ai_model,
            'enable_llm_processing': True,    # 文字處理默認啟用 LLM
            'source_type': 'text',            # 標記來源為文字處理
            'status': 'completed'
        }

        # 🔧 修復：完成前再次檢查取消狀態，避免覆蓋已取消狀態
        if qm and not qm.is_task_cancelled(task_id):
            qm.complete_task(task_id, result)
            logger.info(f"✅ 文字處理任務完成: {task_id}")
        else:
            logger.info(f"🚫 任務 {task_id} 已被取消，跳過完成標記")

        cleanup_cuda_memory()
        unload_ollama_model()

    except TaskCancelledException:
        # 🔧 修復：任務取消是正常流程
        logger.info(f"🚫 文字處理任務 {task_id} 已被取消，正常終止")
        cleanup_cuda_memory()
        unload_ollama_model()
    except Exception as e:
        logger.error(f"❌ 文字處理任務失敗: {task_id or '未知'} - {str(e)}")
        # 動態導入避免循環依賴
        try:
            import app
            qm = app.get_queue_manager()
        except:
            qm = None
        # 🔧 修復：只有在任務未被取消時才標記失敗
        if qm and task_id and not qm.is_task_cancelled(task_id):
            qm.fail_task(task_id, str(e))
        cleanup_cuda_memory()
        unload_ollama_model()

def process_single_audio_file(filename, config, task_id, original_name=None):
    """處理單個音頻檔案"""
    try:
        from config import config as app_config
        
        # 處理文件路徑
        if os.path.isabs(filename):
            filepath = filename
        else:
            filepath = os.path.join(app_config.UPLOAD_FOLDER, filename)
            
        if not os.path.exists(filepath):
            raise Exception(f"文件不存在: {filepath}")
        
        logger.info(f"🎤 開始處理: {original_name or filename}")
        
        # Whisper 語音識別
        from .audio_processing import process_audio_with_whisper
        audio_result = process_audio_with_whisper(filepath, config, task_id)
        transcription = audio_result.get('text', '')

        # 🔧 TEXT REFINEMENT AGENT - 文字精煉
        # 使用專用的 refinement 模型（非推理模型）
        try:
            from .text_refinement import refine_transcription
            refinement_model = app_config.get_refinement_model()
            logger.info(f"✨ 開始文字精煉: {original_name or filename}")
            logger.info(f"   使用 Refinement 專用模型: {refinement_model}")
            transcription = refine_transcription(
                raw_text=transcription,
                task_id=task_id,
                ai_model=refinement_model
            )
            cleanup_cuda_memory()
            logger.info(f"✅ 文字精煉完成: {original_name or filename}")
        except Exception as e:
            logger.warning(f"⚠️ 文字精煉失敗，使用原始轉錄: {str(e)}")

        # AI 智能整理（如果啟用）
        ai_summary = ""
        if config.get('enable_llm', True):
            try:
                logger.info("🧹 AI 處理前清理 GPU 記憶體...")
                cleanup_cuda_memory()
                
                from .text_processing import organize_text_with_ollama
                ai_summary = organize_text_with_ollama(
                    transcription,
                    config.get('processing_mode', 'default'),
                    config.get('detail_level', 'normal'),
                    config.get('ai_model', 'phi4-mini:3.8b'),
                    config.get('custom_mode_prompt'),
                    config.get('custom_detail_prompt'),
                    config.get('custom_format_template'),
                    config.get('selected_tags', []),
                    config.get('custom_prompt')
                )
                
                logger.info("🧹 AI 處理後清理 GPU 記憶體...")
                cleanup_cuda_memory()
                logger.info(f"✅ AI 整理完成: {original_name or filename}")
            except Exception as e:
                logger.warning(f"⚠️ AI 整理失敗: {str(e)}")
        
        # 構建返回結果
        result = {
            'filename': original_name or filename,
            'transcription': transcription,
            'ai_summary': ai_summary,
            'audio_metadata': audio_result.get('metadata', {})
        }

        return result
        
    except Exception as e:
        logger.error(f"❌ 處理檔案失敗 {original_name or filename}: {str(e)}")
        return {
            'filename': original_name or filename,
            'error': str(e),
            'transcription': '',
            'ai_summary': ''
        }

def process_audio_task(task):
    """處理音頻處理任務 - 支援多檔案批次處理"""
    task_id = None
    start_time = time.time()  # 記錄處理開始時間
    try:
        # 支援多種 task_id 字段名稱
        task_id = task.get('task_id') or task.get('id') or task.get('taskId')
        if not task_id:
            raise ValueError("任務中未找到 task_id 字段")

        # 🔧 修復：處理前檢查取消狀態
        check_task_cancelled(task_id, "音頻處理開始")

        # 檢查是否為多檔案批次任務
        task_data = task.get('task_data', {})
        files = task_data.get('files', []) or task.get('files', [])
        file_count = task_data.get('file_count', 0) or task.get('file_count', 0)

        logger.debug(f"🔍 多檔案檢測: files={len(files)}, file_count={file_count}")

        if (files and len(files) > 1) or file_count > 1:
            logger.info(f"✅ 檢測到多檔案批次任務，使用多檔案處理器")
            # 使用新的多檔案處理器
            from .multi_file_processor import process_multi_file_audio_task
            return process_multi_file_audio_task(task)
        else:
            logger.info(f"ℹ️  使用單檔案處理器 (檔案數量: {len(files)})")
        
        # 單檔案處理（向後相容）
        filename = task.get('filename') or task.get('file_path') or task.get('filePath')
        if not filename and files:
            # 如果有files但只有一個檔案，使用該檔案
            filename = files[0]['filename']
        if not filename:
            raise ValueError("任務中未找到 filename 字段")
            
        config_data = task.get('processing_config', {}) or task.get('config', {})
        user_id = task.get('user_id')
        
        # 動態導入避免循環依賴
        # 🔧 修復：安全處理 config_service 為 None 的情況，避免 AttributeError 崩潰
        try:
            import app
            config_service = app.get_config_service()
            if config_service is None:
                raise RuntimeError("config_service 未初始化")
            user_config = config_service.get_user_config(user_id)
        except Exception as e:
            logger.error(f"❌ 無法獲取用戶配置: {e}")
            raise RuntimeError(f"任務處理失敗：無法載入配置服務 - {str(e)}")
        
        final_config = {
            'whisper_model': config_data.get('whisper_model', user_config.whisper_model),
            'enable_llm': config_data.get('enable_llm', user_config.enable_llm_processing),
            'processing_mode': config_data.get('processing_mode', user_config.processing_mode),
            'detail_level': config_data.get('detail_level', user_config.detail_level),
            'ai_model': config_data.get('ai_model', user_config.ai_model),
            'asr_engine': config_data.get('asr_engine', app_config.ASR_ENGINE),
            # 自定義參數
            'custom_mode_prompt': config_data.get('custom_mode_prompt'),
            'custom_detail_prompt': config_data.get('custom_detail_prompt'),
            'custom_format_template': config_data.get('custom_format_template'),
            # 標籤參數
            'selected_tags': config_data.get('selected_tags', []),
            'custom_prompt': config_data.get('custom_prompt')  # 🔧 修復：添加 custom_prompt 支持
        }
        
        logger.info(f"📁 處理文件: {filename}")
        logger.info(f"🎤 [診斷] ASR 引擎: {final_config.get('asr_engine')} (env: {app_config.ASR_ENGINE})")
        logger.info(f"🔍 [診斷] final_config 包含 selected_tags: {final_config.get('selected_tags')}")
        logger.info(f"🔍 [診斷] final_config 包含 custom_prompt: {repr(final_config.get('custom_prompt'))}")

        # 動態導入避免循環依賴
        try:
            import app
            qm = app.get_queue_manager()
        except:
            qm = None

        tracker = ProgressTracker(task_id, qm)
        tracker.update(STAGE_PREPARING, 2, "準備處理")

        # 處理文件路徑
        if os.path.isabs(filename):
            # 如果是絕對路徑，直接使用
            filepath = filename
        else:
            # 如果是相對路徑，從上傳目錄開始
            filepath = os.path.join(app_config.UPLOAD_FOLDER, filename)

        if not os.path.exists(filepath):
            raise Exception(f"文件不存在: {filepath}")

        # 🔧 優化：在處理前驗證文件內容（移至後台以避免阻塞上傳）
        tracker.update(STAGE_PREPARING, 4, "驗證文件格式")

        # 動態導入驗證函數
        try:
            from controllers.audio_controller import validate_file_content
            content_ok, content_error = validate_file_content(filepath, filename)
            if not content_ok:
                # 刪除無效文件
                try:
                    os.remove(filepath)
                    logger.warning(f"刪除無效文件: {filepath}")
                except Exception as e:
                    logger.error(f"刪除無效文件失敗: {e}")
                raise Exception(f"文件驗證失敗: {content_error}")
            logger.info(f"✅ 文件驗證通過: {filename}")
        except ImportError:
            logger.warning("⚠️ 無法導入 validate_file_content，跳過內容驗證")

        # 🧹 ASR 前卸載 Ollama 模型，確保 Whisper 有足夠 GPU 記憶體
        logger.info("🧹 ASR 前卸載 Ollama 模型並清理 GPU 記憶體...")
        unload_ollama_model()
        cleanup_cuda_memory()

        from .audio_processing import process_audio_with_whisper
        audio_result = process_audio_with_whisper(
            filepath, final_config, task_id,
            progress_callback=tracker.make_callback()
        )
        transcription = audio_result.get('text', '')

        # 🔧 修復：Whisper 處理後檢查取消狀態
        check_task_cancelled(task_id, "Whisper 轉錄後")

        # 🔧 調試：記錄轉錄結果
        logger.info(f"🎯 Whisper 轉錄結果:")
        logger.info(f"   轉錄文本長度: {len(transcription) if transcription else 0} 字符")
        logger.info(f"   轉錄文本預覽: {transcription[:200] if transcription else '無內容'}...")
        logger.info(f"   audio_result 鍵: {list(audio_result.keys()) if audio_result else '無結果'}")

        # ================================================================
        # 🔧 TEXT REFINEMENT AGENT - 文字精煉代理
        # 移除語氣詞 + LLM 術語校正
        # 使用專用的 refinement 模型（非推理模型）
        # ================================================================
        tracker.update(STAGE_REFINEMENT, 62, "開始文字精煉")

        check_task_cancelled(task_id, "文字精煉前")

        try:
            from .text_refinement import refine_transcription

            # 使用 Refinement 專用模型
            refinement_model = app_config.get_refinement_model()
            logger.info(f"✨ 開始文字精煉處理...")
            logger.info(f"   原始文本長度: {len(transcription) if transcription else 0} 字符")
            logger.info(f"   使用 Refinement 專用模型: {refinement_model}")

            # 📊 創建進度回調函數，更新前端顯示
            def refinement_progress_callback(current, total, message):
                progress_pct = 62 + int((current / total) * 13)  # 62-75% 範圍
                tracker.update(STAGE_REFINEMENT, progress_pct, f"文字精煉中 ({current}/{total})")

            refined_transcription = refine_transcription(
                raw_text=transcription,
                task_id=task_id,
                ai_model=refinement_model,
                progress_callback=refinement_progress_callback
            )

            # 用精煉後的文本替換原始轉錄
            transcription = refined_transcription

            logger.info(f"✅ 文字精煉完成")
            logger.info(f"   精煉後文本長度: {len(transcription) if transcription else 0} 字符")

        except TaskCancelledException:
            raise  # 重新拋出取消異常
        except Exception as e:
            logger.warning(f"⚠️ 文字精煉失敗，使用原始轉錄: {str(e)}")
            # 失敗時保持原始轉錄，不中斷流程

        # 🧹 文字精煉後：卸載 Refinement 模型 + 清理 GPU 記憶體
        logger.info("🧹 文字精煉後卸載 Ollama 模型並清理 GPU 記憶體...")
        unload_ollama_model()
        cleanup_cuda_memory()

        check_task_cancelled(task_id, "文字精煉後")
        # ================================================================
        # END TEXT REFINEMENT AGENT
        # ================================================================

        # 🔧 修復：明確處理 AI 智能整理開關
        enable_llm = final_config.get('enable_llm', True)
        logger.info(f"🤖 AI 智能整理開關檢查: enable_llm = {enable_llm}")

        if enable_llm:
            # 🔧 修復：AI 處理前檢查取消狀態
            check_task_cancelled(task_id, "AI 處理前")

            logger.info("✅ 開始執行 AI 智能整理")
            tracker.update(STAGE_AI_PROCESSING, 76, "AI 智能整理中")

            # 🔧 調試：記錄 AI 處理輸入
            processing_mode = final_config.get('processing_mode', 'default')
            detail_level = final_config.get('detail_level', 'normal')
            ai_model = final_config.get('ai_model', 'phi4-mini:3.8b')

            logger.info(f"🤖 AI 處理參數:")
            logger.info(f"   處理模式: {processing_mode}")
            logger.info(f"   詳細程度: {detail_level}")
            logger.info(f"   AI 模型: {ai_model}")
            logger.info(f"   輸入文本長度: {len(transcription) if transcription else 0} 字符")
            logger.info(f"   輸入文本預覽: {transcription[:100] if transcription else '無內容'}...")

            # 在 AI 處理前清理 GPU 記憶體
            logger.info("🧹 音頻處理 AI 階段前清理 GPU 記憶體...")
            cleanup_cuda_memory()

            from .text_processing import organize_text_with_ollama

            processed_text = organize_text_with_ollama(
                transcription,
                processing_mode,
                detail_level,
                ai_model,
                final_config.get('custom_mode_prompt'),
                final_config.get('custom_detail_prompt'),
                final_config.get('custom_format_template'),
                final_config.get('selected_tags', []),
                final_config.get('custom_prompt'),
                task_id=task_id
            )

            # 🔧 修復：AI 處理後檢查取消狀態
            check_task_cancelled(task_id, "AI 處理後")

            # 🧹 AI 處理後：卸載 Ollama 模型 + 清理 GPU 記憶體
            logger.info("🧹 AI 整理後卸載 Ollama 模型並清理 GPU 記憶體...")
            unload_ollama_model()
            cleanup_cuda_memory()

            logger.info(f"🎯 AI 整理完成，輸出長度: {len(processed_text) if processed_text else 0} 字符")
            logger.info(f"🎯 AI 整理結果預覽: {processed_text[:200] if processed_text else '無結果'}...")
        else:
            logger.info("⚠️ AI 智能整理已關閉，使用原始轉錄結果")
            processed_text = transcription
        
        tracker.update(STAGE_COMPLETED, 100)

        # 計算處理時間
        processing_time = time.time() - start_time

        result = {
            'transcription': transcription,
            'processed_text': processed_text,
            'original_text': transcription,
            'organized_text': processed_text,
            # 前端期望的字段名稱
            'whisper_result': transcription,  # Whisper 原始轉錄結果
            'ai_summary': processed_text,     # AI 摘要結果
            'result': processed_text,         # 保持兼容性
            'filename': filename,
            'processing_mode': config_data.get('processing_mode', 'default'),
            'enable_llm_processing': config_data.get('enable_llm_processing', True),
            'duration': get_audio_duration(filepath),
            'processing_time': processing_time,  # 處理耗時（秒）
            'file_info': {
                'filename': filename,
                'size': os.path.getsize(filepath),
                'format': filepath.split('.')[-1],
                'duration': get_audio_duration(filepath)
            },
            'processing_config': config_data,
            'status': 'completed',
            # 置信度相關數據 (從 Whisper 結果獲取)
            'segments': audio_result.get('segments', []),
            'avg_confidence': audio_result.get('avg_confidence', 0),
            'low_confidence_count': audio_result.get('low_confidence_count', 0)
        }

        # 🔧 修復：完成前再次檢查取消狀態，避免覆蓋已取消狀態
        if qm and not qm.is_task_cancelled(task_id):
            qm.complete_task(task_id, result)
            logger.info(f"✅ 音頻處理任務完成: {task_id}")
        else:
            logger.info(f"🚫 任務 {task_id} 已被取消，跳過完成標記")

        cleanup_cuda_memory()
        unload_ollama_model()

    except TaskCancelledException:
        # 🔧 修復：任務取消是正常流程
        logger.info(f"🚫 音頻處理任務 {task_id} 已被取消，正常終止")
        cleanup_cuda_memory()
        unload_ollama_model()
    except Exception as e:
        import traceback
        logger.error(f"❌ 音頻處理任務失敗: {task_id or '未知'} - {str(e)}")
        logger.error(f"❌ 完整 traceback:\n{traceback.format_exc()}")
        # 動態導入避免循環依賴
        try:
            import app
            qm = app.get_queue_manager()
        except:
            qm = None
        # 🔧 修復：只有在任務未被取消時才標記失敗
        if qm and task_id and not qm.is_task_cancelled(task_id):
            qm.fail_task(task_id, str(e))
        cleanup_cuda_memory()
        unload_ollama_model()

def get_audio_duration(filepath):
    """獲取音頻時長 - 改進版本，抑制警告"""
    import warnings

    # 方法1: 嘗試使用 soundfile（最快）
    try:
        import soundfile as sf
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            info = sf.info(filepath)
            return info.duration
    except Exception:
        pass

    # 方法2: 嘗試使用 librosa（更兼容但有警告）
    try:
        import librosa
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            # 抑制 stderr 輸出
            import sys
            import os
            stderr_fd = sys.stderr.fileno()
            old_stderr = os.dup(stderr_fd)
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, stderr_fd)
            try:
                duration = librosa.get_duration(path=filepath)
            finally:
                os.dup2(old_stderr, stderr_fd)
                os.close(devnull)
                os.close(old_stderr)
            return duration
    except Exception:
        pass

    # 方法3: 使用 ffprobe（最可靠）
    try:
        import subprocess
        import json
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', filepath],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data['format']['duration'])
    except Exception:
        pass

    logger.warning(f"⚠️ 無法獲取音頻時長，使用預設值")
    return 0