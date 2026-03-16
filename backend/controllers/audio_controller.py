"""
音頻處理控制器 - 處理音頻相關的 API 請求
"""
from flask import Blueprint, request, jsonify, current_app
import logging
import shutil
from werkzeug.utils import secure_filename
from werkzeug.exceptions import ClientDisconnected

# 安全性導入
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logging.warning("python-magic 未安裝，文件類型驗證將使用擴展名方式")

# 動態導入避免循環依賴
def get_services():
    """動態獲取服務"""
    try:
        from services.audio_service import audio_service
        from services.text_service import text_service
        from services.config_service import config_service
        from utils.cache_manager import cache_manager
        return audio_service, text_service, config_service, cache_manager
    except ImportError as e:
        logger.error(f"服務導入失敗: {e}")
        return None, None, None, None

def get_queue_manager():
    """動態獲取隊列管理器"""
    try:
        import app
        return getattr(app, 'queue_manager', None)
    except Exception:
        return None

def get_whisper_manager():
    """動態獲取 Whisper 管理器"""
    try:
        from whisper_integration import WhisperManager
        return WhisperManager
    except ImportError:
        return None

logger = logging.getLogger(__name__)

audio_bp = Blueprint('audio', __name__, url_prefix='/api/audio')

# 安全配置
MAX_FILE_SIZE = 3 * 1024 * 1024 * 1024  # 3GB per file (與 Flask MAX_CONTENT_LENGTH 一致)
MAX_TOTAL_UPLOAD_SIZE = 15 * 1024 * 1024 * 1024  # 🔒 安全修復：15GB 批次總大小限制
MIN_FREE_SPACE = 10 * 1024 * 1024 * 1024  # 10GB minimum free space

# 允許的 MIME 類型
ALLOWED_MIME_TYPES = {
    'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav',
    'audio/mp4', 'audio/m4a', 'audio/x-m4a', 'audio/aac',
    'audio/ogg', 'audio/flac', 'audio/x-flac', 'audio/wma',
    'audio/3gpp', 'audio/3gpp2',  # 3GPP audio formats (often used for M4A)
    'video/mp4', 'video/x-msvideo', 'video/quicktime',
    'video/x-matroska', 'video/webm',
    'video/3gpp', 'video/3gpp2'  # 3GPP video formats (sometimes detected for M4A files)
}

def check_disk_space(upload_folder):
    """檢查磁盤空間是否充足"""
    try:
        stats = shutil.disk_usage(upload_folder)
        if stats.free < MIN_FREE_SPACE:
            return False, f"磁盤空間不足 (剩餘: {stats.free / (1024**3):.1f}GB)"
        return True, None
    except Exception as e:
        logger.error(f"檢查磁盤空間失敗: {e}")
        return True, None  # 失敗時允許繼續，但記錄日誌

def validate_file_content(filepath, filename):
    """
    驗證文件內容是否為有效的音視頻文件
    使用 magic number 檢查，而不僅僅依賴擴展名
    """
    if not MAGIC_AVAILABLE:
        # 降級到擴展名檢查
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        allowed_extensions = {'mp3', 'wav', 'm4a', 'flac', 'aac', 'ogg', 'wma',
                            'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv'}
        if ext not in allowed_extensions:
            return False, f"不支持的文件格式: .{ext}"
        return True, None

    try:
        # 使用 magic number 檢查文件實際類型
        mime = magic.from_file(filepath, mime=True)

        if mime not in ALLOWED_MIME_TYPES:
            logger.warning(f"拒絕上傳非音視頻文件: {mime} (文件名: {filename})")
            return False, f"無效的文件類型，僅支持音頻和視頻文件"

        logger.debug(f"文件驗證通過: {filename} ({mime})")
        return True, None

    except Exception as e:
        logger.error(f"文件驗證失敗: {filename} - {e}")
        return False, "文件驗證失敗"

def validate_file_size(file_size):
    """驗證文件大小"""
    if file_size > MAX_FILE_SIZE:
        size_mb = file_size / (1024 * 1024)
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        return False, f"文件過大 ({size_mb:.1f}MB)，最大允許 {max_mb:.0f}MB"
    return True, None

def get_limiter():
    """獲取速率限制器"""
    try:
        import app
        return app.limiter
    except:
        return None

@audio_bp.route('/upload', methods=['POST'])
def upload_audio():
    """音頻文件上傳處理 - 支持多檔案上傳"""
    # 🔒 速率限制已在 app.py 中豁免此端點，以支援 Cloudflare Tunnel 多用戶訪問
    # 如需重新啟用，可取消以下註解
    # limiter = get_limiter()
    # if limiter:
    #     try:
    #         limiter.limit("100 per hour")(lambda: None)()  # 已放寬至 100/hour
    #     except Exception as e:
    #         if "rate limit" in str(e).lower():
    #             logger.warning(f"速率限制觸發: {request.remote_addr}")
    #             return jsonify({
    #                 'error': '上傳請求過於頻繁，請稍後再試',
    #                 'retry_after': '1 hour'
    #             }), 429
    try:
        # 🔒 安全檢查 1: 檢查磁盤空間
        from config import config
        disk_ok, disk_error = check_disk_space(config.UPLOAD_FOLDER)
        if not disk_ok:
            logger.warning(f"磁盤空間不足: {disk_error}")
            return jsonify({'error': '服務器存儲空間不足，請稍後再試'}), 507

        # 檢查檔案數量
        file_count = int(request.form.get('file_count', 1))
        if file_count > 5:
            return jsonify({'error': '最多只能上傳 5 個檔案'}), 400

        logger.info(f"📁 收到上傳請求: {file_count} 個檔案")

        # 收集所有檔案
        files = []
        for i in range(file_count):
            file_key = f'audio_{i}'
            if file_key in request.files:
                file = request.files[file_key]
                if file.filename != '':
                    files.append(file)
                    logger.info(f"✅ 檔案: {file.filename}")
                else:
                    logger.warning(f"⚠️ 檔案字段 {file_key} 有空檔名")
            else:
                logger.warning(f"⚠️ 檔案字段 {file_key} 不存在")
        
        # 如果沒有檔案，試著從傳統字段讀取
        if not files:
            logger.info("🔍 嘗試傳統字段...")
            if 'file' in request.files:
                file = request.files['file']
                if file.filename != '':
                    files.append(file)
                    logger.info(f"✅ 傳統字段 'file' 找到: {file.filename}")
            elif 'audio' in request.files:
                file = request.files['audio']
                if file.filename != '':
                    files.append(file)
                    logger.info(f"✅ 傳統字段 'audio' 找到: {file.filename}")
        
        if not files:
            logger.error("❌ 沒有找到任何有效檔案")
            # 詳細記錄所有請求字段
            logger.info(f"📝 請求檔案字段: {list(request.files.keys())}")
            logger.info(f"📝 請求表單字段: {list(request.form.keys())}")
            return jsonify({
                'error': '沒有有效的檔案上傳',
                'debug_info': {
                    'file_keys': list(request.files.keys()),
                    'form_keys': list(request.form.keys()),
                    'file_count': file_count
                }
            }), 400
        
        logger.info(f"✅ 成功收集到 {len(files)} 個檔案")
        
        # 獲取用戶ID
        user_id = request.form.get('user_id')
        
        # 動態獲取服務
        audio_service, text_service, config_service, cache_manager = get_services()
        queue_manager = get_queue_manager()
        
        if not config_service:
            return jsonify({'error': '配置服務不可用'}), 503
        if not queue_manager:
            return jsonify({'error': '隊列管理器不可用'}), 503
        
        # 獲取用戶配置
        user_config = config_service.get_user_config(user_id)
        
        # 獲取處理選項，優先使用表單參數，其次使用用戶配置
        processing_mode = request.form.get('processing_mode', user_config.processing_mode)
        detail_level = request.form.get('detail_level', user_config.detail_level)

        # 使用系統配置的固定模型，忽略前端傳入的模型參數
        from config import config as system_config
        whisper_model = system_config.WHISPER_MODEL_FIXED if system_config.WHISPER_MODEL_FIXED else system_config.DEFAULT_WHISPER_MODEL

        # 🔧 修復：正確處理 AI 智能整理開關
        enable_llm_raw = request.form.get('enable_llm')
        if enable_llm_raw is not None:
            enable_llm = enable_llm_raw.lower() == 'true'
        else:
            enable_llm = user_config.enable_llm_processing if hasattr(user_config, 'enable_llm_processing') else True
        
        # 使用系統配置的固定 AI 模型，忽略前端傳入的模型參數
        ai_model = system_config.get_current_ai_model()
        
        logger.info(f"🤖 AI 智能整理開關:")
        logger.info(f"  - enable_llm (表單): {enable_llm_raw}")
        logger.info(f"  - 最終 enable_llm: {enable_llm}")
        
        logger.info(f"🎯 AI 模型選擇:")
        logger.info(f"  - ai_model (系統配置): {ai_model}")
        logger.info(f"  - ai_model (用戶配置): {user_config.ai_model}")
        logger.info(f"  - 最終 ai_model: {ai_model}")
        
        # 獲取 Email 通知參數
        email_enabled_raw = request.form.get('email_enabled')
        email_address = request.form.get('email_address')
        
        # 處理 Email 通知設定
        email_enabled = email_enabled_raw and email_enabled_raw.lower() == 'true'
        
        logger.info(f"📧 Email 通知設定:")
        logger.info(f"  - email_enabled (表單): {email_enabled_raw}")
        logger.info(f"  - email_address (表單): {email_address}")
        logger.info(f"  - 最終 email_enabled: {email_enabled}")
        
        # 獲取標籤參數
        selected_tags_raw = request.form.get('selected_tags')
        selected_tags = []
        if selected_tags_raw:
            try:
                import json
                selected_tags = json.loads(selected_tags_raw)
                if not isinstance(selected_tags, list):
                    selected_tags = []
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"無效的標籤格式: {selected_tags_raw}")
                selected_tags = []
        
        logger.info(f"🏷️ 標籤設定:")
        logger.info(f"  - selected_tags (表單): {selected_tags_raw}")
        logger.info(f"  - 最終 selected_tags: {selected_tags}")

        # 獲取自定義標籤 Prompt（當選擇了 custom 標籤時）
        custom_tag_prompt = request.form.get('custom_tag_prompt', '')
        if custom_tag_prompt:
            logger.info(f"✨ 自定義標籤 Prompt: {custom_tag_prompt[:100]}...")

        # 創建處理配置
        processing_config = {
            'processing_mode': processing_mode,
            'detail_level': detail_level,
            'whisper_model': whisper_model,
            'enable_llm': enable_llm,  # 🔧 使用正確的 enable_llm 值
            'ai_model': ai_model,  # 🔧 使用正確的 ai_model 值
            'email_enabled': email_enabled,  # 📧 Email 通知開關
            'email_address': email_address if email_enabled else None,  # 📧 Email 地址
            'selected_tags': selected_tags,  # 🏷️ 選擇的標籤
            'custom_prompt': custom_tag_prompt  # ✨ 自定義標籤 Prompt (用於 custom 標籤)
        }
        
        # 處理多個檔案
        import os
        import uuid
        from config import config
        
        saved_files = []
        total_size = 0
        
        for file in files:
            original_filename = file.filename

            # 獲取文件大小
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)

            # 🔒 安全檢查 2a: 拒絕空文件
            if file_size == 0:
                logger.warning(f"拒絕空文件: {original_filename}")
                return jsonify({'error': f'文件 {original_filename} 為空，無法處理'}), 400

            # 🔒 安全檢查 2b: 拒絕過小的文件（小於 1KB，可能不是有效音頻）
            MIN_AUDIO_SIZE = 1024  # 1KB
            if file_size < MIN_AUDIO_SIZE:
                logger.warning(f"文件過小被拒絕: {original_filename} ({file_size} bytes)")
                return jsonify({'error': f'文件 {original_filename} 過小 ({file_size} bytes)，可能不是有效的音頻文件'}), 400

            # 🔒 安全檢查 2c: 驗證文件大小
            size_ok, size_error = validate_file_size(file_size)
            if not size_ok:
                logger.warning(f"文件過大被拒絕: {original_filename} ({file_size} bytes)")
                return jsonify({'error': size_error}), 413

            total_size += file_size

            # 🔒 安全檢查 3: 驗證批次總大小
            if total_size > MAX_TOTAL_UPLOAD_SIZE:
                total_gb = total_size / (1024 ** 3)
                max_gb = MAX_TOTAL_UPLOAD_SIZE / (1024 ** 3)
                logger.warning(f"批次上傳總大小超限: {total_gb:.1f}GB > {max_gb:.0f}GB")
                return jsonify({'error': f'批次上傳總大小過大 ({total_gb:.1f}GB)，最大允許 {max_gb:.0f}GB'}), 413

            # 🔒 安全檢查 4: 清理文件名（防止路徑穿越攻擊）
            file_id = str(uuid.uuid4())
            safe_filename = secure_filename(original_filename)
            if not safe_filename:
                safe_filename = 'unnamed_file'
            filename = f"{file_id}_{safe_filename}"
            filepath = os.path.join(config.UPLOAD_FOLDER, filename)

            logger.info(f"保存文件到: {filepath}")
            file.save(filepath)
            logger.info(f"文件保存成功: {filename}")

            # 🔧 優化：快速檢查文件擴展名（移除同步的 magic number 檢查以避免阻塞）
            # 完整的內容驗證將在任務處理時進行，這樣上傳端點可以快速響應
            ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else ''
            allowed_extensions = {'mp3', 'wav', 'm4a', 'flac', 'aac', 'ogg', 'wma',
                                'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', '3gp'}
            if ext not in allowed_extensions:
                # 刪除無效文件
                try:
                    os.remove(filepath)
                    logger.warning(f"刪除不支持格式的文件: {filepath}")
                except Exception as e:
                    logger.error(f"刪除無效文件失敗: {e}")
                return jsonify({'error': f'不支持的文件格式: .{ext}'}), 400

            # 📝 注意：完整的內容驗證（magic number 檢查）將在後台任務處理時進行
            # 這樣可以讓上傳端點快速響應，避免大文件導致請求超時

            saved_files.append({
                'filename': filename,
                'original_name': original_filename,
                'size': file_size,
                'filepath': filepath  # 🔧 添加路徑供後續驗證使用
            })
        
        # 創建任務
        task_data = {
            'type': 'audio_processing',
            'files': saved_files,
            'file_count': len(saved_files),
            'user_id': user_id,
            'processing_config': processing_config
        }
        
        # 獲取客戶端 IP
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        # 添加到隊列（使用第一個檔案名為主檔案名）
        primary_filename = saved_files[0]['filename'] if saved_files else 'multiple_files'
        task_id = queue_manager.add_to_queue(user_id, primary_filename, total_size, task_data, ip_address=client_ip)
        
        return jsonify({
            'task_id': task_id,
            'message': f'{len(saved_files)} 個文件上傳成功，正在處理中...',
            'status': 'queued',
            'file_count': len(saved_files),
            'files': [f['original_name'] for f in saved_files]
        })
        
    except ClientDisconnected:
        # 客戶端在上傳過程中斷開連接（用戶取消、網絡中斷等）
        logger.info("客戶端在上傳過程中斷開連接（可能是用戶取消或網絡中斷）")
        return jsonify({'error': '上傳已取消或連接中斷'}), 499  # 499 = Client Closed Request
    except ValueError as e:
        # 用戶輸入錯誤 - 可以安全顯示
        logger.warning(f"用戶輸入錯誤: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        # 系統錯誤 - 隱藏內部細節
        logger.error(f"音頻上傳失敗: {str(e)}", exc_info=True)
        return jsonify({'error': '上傳處理失敗，請稍後再試'}), 500

@audio_bp.route('/process', methods=['POST'])
def process_audio_file():
    """處理單個音頻文件"""
    try:
        data = request.json
        audio_path = data.get('audio_path')
        options = data.get('options', {})
        
        if not audio_path:
            return jsonify({'error': '缺少音頻文件路徑'}), 400
        
        # 預處理音頻
        processed_audio, sr = audio_service.preprocess_audio(audio_path)
        
        # 語音識別
        whisper_manager = WhisperManager()
        transcription = whisper_manager.transcribe(processed_audio)
        
        # 文字整理（如果啟用）
        if options.get('enable_llm', True):
            processed_text = text_service.process_text_sync(
                transcription,
                options.get('ai_model', 'phi4-mini:3.8b'),
                options.get('processing_mode', 'default'),
                options.get('detail_level', 'normal')
            )
        else:
            processed_text = transcription
        
        return jsonify({
            'transcription': transcription,
            'processed_text': processed_text,
            'audio_info': audio_service.get_audio_info(audio_path)
        })
        
    except Exception as e:
        logger.error(f"音頻處理失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@audio_bp.route('/models', methods=['GET'])
def get_whisper_models():
    """獲取可用的 Whisper 模型列表"""
    try:
        models = ['tiny', 'base', 'small', 'medium', 'large']
        return jsonify({'models': models})
    except Exception as e:
        logger.error(f"獲取模型列表失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@audio_bp.route('/switch-model', methods=['POST'])
def switch_whisper_model():
    """切換 Whisper 模型"""
    try:
        data = request.json
        model_name = data.get('model')
        
        if not model_name:
            return jsonify({'error': '缺少模型名稱'}), 400
        
        # 這裡可以實現模型切換邏輯
        return jsonify({
            'message': f'已切換到 {model_name} 模型',
            'current_model': model_name
        })
        
    except Exception as e:
        logger.error(f"模型切換失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500