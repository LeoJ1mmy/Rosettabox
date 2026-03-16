"""
外部 API v1 - 統一的語音文字處理接口
提供完整的功能給外部系統使用，包括音頻處理、文字整理、配置管理等
"""

from flask import Blueprint, request, jsonify, current_app, g
import logging
import os
import time
import uuid
import hashlib
import hmac
import json
from werkzeug.utils import secure_filename
from typing import Dict, Any, List, Optional
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict

# 導入內部服務和API響應系統
import sys
sys.path.append('/home/leo/LeoQxAIBox/voice-text-processor/backend')

from services.text_service import text_service
from services.config_service import config_service
from whisper_integration import WhisperManager
from utils.cache_manager import cache_manager
from utils.api_response import APIResponse, RequestValidator
import numpy as np

logger = logging.getLogger(__name__)

# 創建 Blueprint
api_v1 = Blueprint('external_api_v1', __name__, url_prefix='/external/v1')

# 支援的文件格式
ALLOWED_EXTENSIONS = {
    'audio': {'mp3', 'wav', 'flac', 'm4a', 'ogg', 'wma', 'aac'},
    'video': {'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv', 'webm'}
}

def allowed_file(filename: str, file_type: str = 'audio') -> bool:
    """檢查文件格式是否支援"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS.get(file_type, set())

# 客戶端註冊存儲 (在生產環境中應使用數據庫)
CLIENT_REGISTRY = {}
APIKEY_TO_CLIENT = {}
RATE_LIMIT_STORAGE = defaultdict(list)

def generate_api_key() -> str:
    """生成 API 密鑰"""
    return f"vtp_{uuid.uuid4().hex[:16]}"

def generate_client_secret() -> str:
    """生成客戶端密鑰"""
    return hashlib.sha256(f"{uuid.uuid4().hex}{time.time()}".encode()).hexdigest()[:32]

def verify_api_signature(api_key: str, timestamp: str, signature: str, request_data: str) -> bool:
    """驗證 API 請求簽名"""
    try:
        client_info = APIKEY_TO_CLIENT.get(api_key)
        if not client_info:
            return False
        
        client_secret = client_info.get('client_secret')
        if not client_secret:
            return False
        
        # 檢查時間戳是否在5分鐘內
        current_time = int(time.time())
        request_time = int(timestamp)
        if abs(current_time - request_time) > 300:  # 5分鐘
            return False
        
        # 計算預期簽名
        message = f"{api_key}{timestamp}{request_data}"
        expected_signature = hmac.new(
            client_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    except Exception:
        return False

# ============== 認證中間件 ==============

def require_api_auth(f):
    """API 認證裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 獲取認證信息
        api_key = request.headers.get('X-API-Key')
        client_id = request.headers.get('X-Client-ID')
        timestamp = request.headers.get('X-Timestamp')
        signature = request.headers.get('X-Signature')
        
        if not api_key or not client_id:
            return APIResponse.error(
                "缺少認證信息", 
                code=401, 
                error_code="MISSING_AUTH_HEADERS"
            )
        
        # 驗證 API Key
        client_info = APIKEY_TO_CLIENT.get(api_key)
        if not client_info or client_info.get('client_id') != client_id:
            return APIResponse.error(
                "無效的認證信息", 
                code=401, 
                error_code="INVALID_CREDENTIALS"
            )
        
        # 檢查客戶端狀態
        if client_info.get('status') != 'active':
            return APIResponse.error(
                "客戶端已被禁用", 
                code=403, 
                error_code="CLIENT_DISABLED"
            )
        
        # 驗證簽名 (如果提供)
        if signature and timestamp:
            request_data = request.get_data(as_text=True) or ''
            if not verify_api_signature(api_key, timestamp, signature, request_data):
                return APIResponse.error(
                    "簽名驗證失敗", 
                    code=401, 
                    error_code="INVALID_SIGNATURE"
                )
        
        # 將客戶端信息存儲到 g 對象中
        g.client_info = client_info
        g.client_id = client_id
        
        return f(*args, **kwargs)
    
    return decorated_function

def rate_limit(max_requests: int = 100, window_minutes: int = 60):
    """速率限制裝飾器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_id = g.get('client_id')
            if not client_id:
                return APIResponse.error(
                    "未經認證的請求", 
                    code=401, 
                    error_code="UNAUTHENTICATED"
                )
            
            # 檢查速率限制
            now = time.time()
            window_start = now - (window_minutes * 60)
            
            # 清理過期記錄
            client_requests = RATE_LIMIT_STORAGE[client_id]
            RATE_LIMIT_STORAGE[client_id] = [
                req_time for req_time in client_requests 
                if req_time > window_start
            ]
            
            # 檢查是否超過限制
            if len(RATE_LIMIT_STORAGE[client_id]) >= max_requests:
                return APIResponse.error(
                    f"請求過於頻繁，每 {window_minutes} 分鐘最多 {max_requests} 次請求", 
                    code=429, 
                    error_code="RATE_LIMIT_EXCEEDED",
                    details={
                        'limit': max_requests,
                        'window_minutes': window_minutes,
                        'reset_time': int(window_start + (window_minutes * 60))
                    }
                )
            
            # 記錄此次請求
            RATE_LIMIT_STORAGE[client_id].append(now)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

# ============== 認證和配置管理 ==============

@api_v1.route('/auth/register', methods=['POST'])
def register_client():
    """註冊外部客戶端，獲取 API 密鑰"""
    try:
        data = request.get_json() or {}
        
        # 驗證必需字段
        client_name = data.get('client_name', '').strip()
        if not client_name:
            return APIResponse.validation_error(
                "客戶端名稱不能為空",
                details={'required_fields': ['client_name']}
            )
        
        client_description = data.get('description', '')
        admin_email = data.get('admin_email', '')
        
        # 驗證客戶端名稱格式
        if not RequestValidator.validate_client_name(client_name):
            return APIResponse.validation_error(
                "客戶端名稱格式無效（只允許字母、數字、空格、短橫線和下劃線）"
            )
        
        # 生成唯一的客戶端 ID 和密鑰
        client_id = f"client_{uuid.uuid4().hex[:8]}"
        api_key = generate_api_key()
        client_secret = generate_client_secret()
        
        # 存儲客戶端信息
        client_info = {
            'client_id': client_id,
            'client_name': client_name,
            'description': client_description,
            'admin_email': admin_email,
            'api_key': api_key,
            'client_secret': client_secret,
            'status': 'active',
            'created_at': datetime.now().isoformat(),
            'last_access': None,
            'request_count': 0,
            'rate_limits': {
                'requests_per_hour': 1000,
                'requests_per_day': 10000
            }
        }
        
        CLIENT_REGISTRY[client_id] = client_info
        APIKEY_TO_CLIENT[api_key] = client_info
        
        # 創建客戶端配置
        client_config = config_service.get_global_config()
        config_service.save_user_config(client_id, client_config)
        
        logger.info(f"新客戶端註冊: {client_name} (ID: {client_id})")
        
        return APIResponse.success(
            data={
                'client_id': client_id,
                'api_key': api_key,
                'client_secret': client_secret,
                'client_name': client_name,
                'endpoints': {
                    'audio_process': '/external/v1/audio/process',
                    'text_process': '/external/v1/text/process',
                    'batch_text': '/external/v1/batch/text',
                    'config_get': '/external/v1/config',
                    'config_update': '/external/v1/config',
                    'status': '/external/v1/status'
                },
                'authentication': {
                    'required_headers': [
                        'X-API-Key',
                        'X-Client-ID'
                    ],
                    'optional_headers': [
                        'X-Timestamp',
                        'X-Signature'
                    ],
                    'signature_algorithm': 'HMAC-SHA256'
                },
                'rate_limits': client_info['rate_limits']
            },
            message="客戶端註冊成功",
            code=201
        )
        
    except Exception as e:
        logger.error(f"客戶端註冊失敗: {e}")
        return APIResponse.error(
            f"註冊失敗: {str(e)}",
            code=500,
            error_code="REGISTRATION_FAILED"
        )

@api_v1.route('/config', methods=['GET'])
@require_api_auth
@rate_limit(max_requests=200, window_minutes=60)
def get_client_config():
    """獲取客戶端配置"""
    try:
        client_id = g.client_id
        
        config = config_service.export_config(client_id)
        schema = config_service.get_config_schema()
        
        return APIResponse.success(
            data={
                'client_id': client_id,
                'config': config,
                'schema': schema,
                'last_updated': g.client_info.get('config_updated_at')
            },
            message="配置獲取成功"
        )
        
    except Exception as e:
        logger.error(f"獲取配置失敗: {e}")
        return APIResponse.error(
            f"獲取配置失敗: {str(e)}",
            code=500,
            error_code="CONFIG_FETCH_FAILED"
        )

@api_v1.route('/config', methods=['PUT'])
@require_api_auth
@rate_limit(max_requests=50, window_minutes=60)
def update_client_config():
    """更新客戶端配置"""
    try:
        client_id = g.client_id
        
        data = request.get_json() or {}
        config_updates = data.get('config', {})
        
        if not config_updates:
            return APIResponse.validation_error(
                "沒有提供配置更新數據",
                details={'required_fields': ['config']}
            )
        
        # 驗證配置更新數據
        validation_result = config_service.validate_config(config_updates)
        if not validation_result.get('valid', False):
            return APIResponse.validation_error(
                "配置數據驗證失敗",
                details=validation_result.get('errors', {})
            )
        
        success = config_service.update_multiple_fields(client_id, config_updates)
        
        if success:
            # 更新客戶端信息中的配置更新時間
            if client_id in CLIENT_REGISTRY:
                CLIENT_REGISTRY[client_id]['config_updated_at'] = datetime.now().isoformat()
            
            updated_config = config_service.export_config(client_id)
            
            return APIResponse.success(
                data={
                    'config': updated_config,
                    'updated_fields': list(config_updates.keys()),
                    'updated_at': datetime.now().isoformat()
                },
                message="配置更新成功"
            )
        else:
            return APIResponse.error(
                "配置更新失敗",
                code=500,
                error_code="CONFIG_UPDATE_FAILED"
            )
            
    except Exception as e:
        logger.error(f"更新配置失敗: {e}")
        return APIResponse.error(
            f"更新配置失敗: {str(e)}",
            code=500,
            error_code="CONFIG_UPDATE_ERROR"
        )

# ============== 音頻處理 ==============

@api_v1.route('/audio/process', methods=['POST'])
@require_api_auth
@rate_limit(max_requests=50, window_minutes=60)
def process_audio():
    """處理音頻文件 - 語音轉文字 + AI 整理"""
    try:
        client_id = g.client_id
        
        # 檔案驗證
        if 'audio' not in request.files:
            return APIResponse.validation_error(
                "沒有上傳音頻文件",
                details={'required_files': ['audio']}
            )
        
        file = request.files['audio']
        if file.filename == '':
            return APIResponse.validation_error(
                "沒有選擇文件",
                details={'error': 'empty_filename'}
            )
        
        if not allowed_file(file.filename, 'audio') and not allowed_file(file.filename, 'video'):
            return APIResponse.validation_error(
                f"不支援的文件格式，支援格式: {', '.join(ALLOWED_EXTENSIONS['audio'] | ALLOWED_EXTENSIONS['video'])}",
                details={'supported_formats': list(ALLOWED_EXTENSIONS['audio'] | ALLOWED_EXTENSIONS['video'])}
            )
        
        # 文件大小驗證 (50MB 限制)
        file.seek(0, 2)  # 移動到文件末尾
        file_size = file.tell()
        file.seek(0)  # 重置指針
        
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            return APIResponse.validation_error(
                f"文件大小超過限制 ({file_size / 1024 / 1024:.1f}MB > 50MB)",
                details={'file_size': file_size, 'max_size': max_size}
            )
        
        # 使用系統配置的固定模型
        from config import config as system_config

        # 獲取和驗證處理參數
        processing_options = {
            'whisper_model': system_config.WHISPER_MODEL_FIXED if system_config.WHISPER_MODEL_FIXED else system_config.DEFAULT_WHISPER_MODEL,
            'enable_llm': request.form.get('enable_llm', 'true').lower() == 'true',
            'processing_mode': request.form.get('processing_mode', 'default'),
            'detail_level': request.form.get('detail_level', 'normal'),
            'ai_model': system_config.get_current_ai_model(),
            'language': request.form.get('language', 'zh')
        }
        
        # 驗證處理參數
        if not RequestValidator.validate_model_name(processing_options['ai_model']):
            return APIResponse.validation_error(
                f"無效的 AI 模型名稱: {processing_options['ai_model']}"
            )
        
        if not RequestValidator.validate_processing_mode(processing_options['processing_mode']):
            return APIResponse.validation_error(
                f"無效的處理模式: {processing_options['processing_mode']}"
            )
        
        if not RequestValidator.validate_detail_level(processing_options['detail_level']):
            return APIResponse.validation_error(
                f"無效的詳細程度: {processing_options['detail_level']}"
            )
        
        # 獲取客戶端配置並合併
        client_config = config_service.get_user_config(client_id)
        final_config = {
            'whisper_model': processing_options.get('whisper_model', client_config.whisper_model),
            'enable_llm': processing_options.get('enable_llm', client_config.enable_llm_processing),
            'processing_mode': processing_options.get('processing_mode', client_config.processing_mode),
            'detail_level': processing_options.get('detail_level', client_config.detail_level),
            'ai_model': processing_options.get('ai_model', client_config.ai_model),
            'language': processing_options.get('language', 'zh')
        }
        
        logger.info(f"外部 API 音頻處理開始: client={client_id}, config={final_config}")
        
        # 保存上傳的文件
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        unique_filename = f"{timestamp}_{filename}"
        upload_dir = '/tmp/external_api_uploads'
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, unique_filename)
        file.save(file_path)
        
        try:
            # 1. Whisper 語音轉文字
            start_time = time.time()
            whisper_result = process_audio_with_whisper(file_path, final_config)
            transcription = whisper_result.get('text', '')
            whisper_time = time.time() - start_time
            
            if not transcription:
                return APIResponse.error(
                    "Whisper 轉錄失敗，沒有識別到文字",
                    code=422,
                    error_code="TRANSCRIPTION_FAILED"
                )
            
            # 1.5. 應用增強版後處理管道
            try:
                from processing.text_processing import enhanced_post_processing_pipeline
                original_len = len(transcription)
                transcription = enhanced_post_processing_pipeline(transcription)
                logger.info(f"外部API後處理: {original_len} -> {len(transcription)} 字符")
            except Exception as e:
                logger.warning(f"外部API後處理失敗: {e}")
            
            # 2. AI 文字整理（如果啟用）
            processed_text = transcription
            ai_time = 0
            
            if final_config.get('enable_llm', True) and transcription:
                start_time = time.time()
                processed_text = text_service.process_text_sync(
                    transcription,
                    final_config.get('ai_model', 'phi4-mini:3.8b'),
                    final_config.get('processing_mode', 'default'),
                    final_config.get('detail_level', 'normal')
                )
                ai_time = time.time() - start_time

            # 構建回應
            result = {
                'status': 'success',
                'message': '音頻處理完成',
                'client_id': client_id,
                'file_info': {
                    'original_filename': filename,
                    'file_size': os.path.getsize(file_path),
                    'processing_time': {
                        'whisper': round(whisper_time, 2),
                        'ai_processing': round(ai_time, 2),
                        'total': round(whisper_time + ai_time, 2)
                    }
                },
                'transcription': {
                    'raw_text': transcription,  # Whisper 原始轉錄
                    'ai_processed_text': processed_text if final_config.get('enable_llm') else None,
                    'language': final_config.get('language'),
                    'word_count': len(transcription.replace(' ', ''))
                },
                'processing_config': final_config,
                'timestamps': whisper_result.get('timestamps', [])
            }

            logger.info(f"外部 API 音頻處理完成: client={client_id}, 耗時={result['file_info']['processing_time']['total']}s")
            
            # 更新客戶端統計
            if client_id in CLIENT_REGISTRY:
                CLIENT_REGISTRY[client_id]['last_access'] = datetime.now().isoformat()
                CLIENT_REGISTRY[client_id]['request_count'] += 1
            
            return APIResponse.success(
                data=result,
                message="音頻處理完成"
            )
            
        finally:
            # 清理上傳的文件
            try:
                os.remove(file_path)
            except:
                pass
        
    except Exception as e:
        logger.error(f"外部 API 音頻處理失敗: {e}")
        return APIResponse.error(
            f"音頻處理失敗: {str(e)}",
            code=500,
            error_code="AUDIO_PROCESSING_ERROR"
        )

# ============== 文字處理 ==============

@api_v1.route('/text/process', methods=['POST'])
@require_api_auth
@rate_limit(max_requests=100, window_minutes=60)
def process_text():
    """處理純文字 - AI 整理"""
    try:
        client_id = g.client_id

        data = request.get_json() or {}
        text = data.get('text', '').strip()

        if not text:
            return APIResponse.validation_error(
                "沒有提供要處理的文字內容",
                details={'required_fields': ['text']}
            )

        # 獲取處理參數
        processing_mode = data.get('processing_mode', 'default')
        detail_level = data.get('detail_level', 'normal')
        ai_model = data.get('ai_model')

        # 獲取客戶端配置
        client_config = config_service.get_user_config(client_id)
        final_ai_model = ai_model or client_config.ai_model
        final_mode = processing_mode or client_config.processing_mode
        final_detail = detail_level or client_config.detail_level

        logger.info(f"外部 API 文字處理開始: client={client_id}, model={final_ai_model}, mode={final_mode}")

        # 處理文字
        start_time = time.time()
        processed_text = text_service.process_text_sync(
            text, final_ai_model, final_mode, final_detail
        )
        processing_time = time.time() - start_time

        result = {
            'client_id': client_id,
            'original_text': text,
            'processed_text': processed_text,
            'processing_config': {
                'ai_model': final_ai_model,
                'processing_mode': final_mode,
                'detail_level': final_detail
            },
            'statistics': {
                'original_length': len(text),
                'processed_length': len(processed_text),
                'processing_time': round(processing_time, 2),
                'compression_ratio': round(len(processed_text) / len(text), 2) if text else 0
            }
        }

        logger.info(f"外部 API 文字處理完成: client={client_id}, 耗時={processing_time:.2f}s")

        # 更新客戶端統計
        if client_id in CLIENT_REGISTRY:
            CLIENT_REGISTRY[client_id]['last_access'] = datetime.now().isoformat()
            CLIENT_REGISTRY[client_id]['request_count'] += 1

        return APIResponse.success(
            data=result,
            message="文字處理完成"
        )

    except Exception as e:
        logger.error(f"外部 API 文字處理失敗: {e}")
        return APIResponse.error(
            f"文字處理失敗: {str(e)}",
            code=500,
            error_code="TEXT_PROCESSING_ERROR"
        )

# ============== 批次處理 ==============

@api_v1.route('/batch/text', methods=['POST'])
@require_api_auth
@rate_limit(max_requests=30, window_minutes=60)
def batch_process_text():
    """批次處理多個文字"""
    try:
        client_id = g.client_id

        data = request.get_json() or {}
        texts = data.get('texts', [])

        if not texts or not isinstance(texts, list):
            return APIResponse.validation_error(
                "沒有提供要處理的文字列表",
                details={'required_fields': ['texts'], 'expected_type': 'array'}
            )

        if len(texts) > 100:  # 限制批次大小
            return APIResponse.validation_error(
                f"批次大小不能超過 100 個文字（當前：{len(texts)}）",
                details={'max_batch_size': 100, 'current_size': len(texts)}
            )

        # 獲取處理參數
        processing_mode = data.get('processing_mode', 'default')
        detail_level = data.get('detail_level', 'normal')
        ai_model = data.get('ai_model')

        # 獲取客戶端配置
        client_config = config_service.get_user_config(client_id)
        final_ai_model = ai_model or client_config.ai_model

        logger.info(f"外部 API 批次文字處理開始: client={client_id}, count={len(texts)}")

        # 批次處理
        start_time = time.time()
        results = []

        for i, text in enumerate(texts):
            try:
                if not text.strip():
                    results.append({
                        'index': i,
                        'status': 'skipped',
                        'message': '空文字已跳過',
                        'original_text': text,
                        'processed_text': text
                    })
                    continue

                processed_text = text_service.process_text_sync(
                    text, final_ai_model, processing_mode, detail_level
                )

                results.append({
                    'index': i,
                    'status': 'success',
                    'original_text': text,
                    'processed_text': processed_text,
                    'statistics': {
                        'original_length': len(text),
                        'processed_length': len(processed_text),
                        'compression_ratio': round(len(processed_text) / len(text), 2) if text else 0
                    }
                })

            except Exception as e:
                results.append({
                    'index': i,
                    'status': 'error',
                    'message': str(e),
                    'original_text': text,
                    'processed_text': text
                })

        total_time = time.time() - start_time

        # 統計結果
        success_count = sum(1 for r in results if r['status'] == 'success')
        error_count = sum(1 for r in results if r['status'] == 'error')
        skip_count = sum(1 for r in results if r['status'] == 'skipped')

        result = {
            'client_id': client_id,
            'summary': {
                'total_items': len(texts),
                'success_count': success_count,
                'error_count': error_count,
                'skip_count': skip_count,
                'processing_time': round(total_time, 2),
                'average_time_per_item': round(total_time / len(texts), 2) if texts else 0
            },
            'processing_config': {
                'ai_model': final_ai_model,
                'processing_mode': processing_mode,
                'detail_level': detail_level
            },
            'results': results
        }

        logger.info(f"外部 API 批次文字處理完成: client={client_id}, 成功={success_count}/{len(texts)}")

        # 更新客戶端統計
        if client_id in CLIENT_REGISTRY:
            CLIENT_REGISTRY[client_id]['last_access'] = datetime.now().isoformat()
            CLIENT_REGISTRY[client_id]['request_count'] += 1

        return APIResponse.success(
            data=result,
            message=f"批次處理完成: 成功 {success_count}, 錯誤 {error_count}, 跳過 {skip_count}"
        )

    except Exception as e:
        logger.error(f"外部 API 批次文字處理失敗: {e}")
        return APIResponse.error(
            f"批次處理失敗: {str(e)}",
            code=500,
            error_code="BATCH_PROCESSING_ERROR"
        )

# ============== 系統狀態 ==============

@api_v1.route('/status', methods=['GET'])
@require_api_auth
@rate_limit(max_requests=300, window_minutes=60)
def get_system_status():
    """獲取系統狀態"""
    try:
        client_id = g.client_id
        
        # 檢查各服務狀態
        whisper_status = check_whisper_status()
        ollama_status = check_ollama_status()
        config_status = check_config_status()
        
        # 系統統計
        system_stats = {
            'uptime': time.time(),  # 簡化的運行時間
            'available_models': {
                'whisper': ['tiny', 'base', 'small', 'medium', 'large'],
                'ai': text_service.get_available_models()
            },
            'supported_formats': {
                'audio': list(ALLOWED_EXTENSIONS['audio']),
                'video': list(ALLOWED_EXTENSIONS['video'])
            }
        }
        
        overall_status = 'healthy' if all([
            whisper_status['status'] == 'healthy',
            ollama_status['status'] == 'healthy',
            config_status['status'] == 'healthy'
        ]) else 'degraded'
        
        # 更新客戶端統計
        if client_id in CLIENT_REGISTRY:
            CLIENT_REGISTRY[client_id]['last_access'] = datetime.now().isoformat()
        
        return APIResponse.success(
            data={
                'client_id': client_id,
                'overall_status': overall_status,
                'services': {
                    'whisper': whisper_status,
                    'ollama': ollama_status,
                    'config': config_status
                },
                'system': system_stats,
                'client_info': {
                    'request_count': CLIENT_REGISTRY.get(client_id, {}).get('request_count', 0),
                    'last_access': CLIENT_REGISTRY.get(client_id, {}).get('last_access'),
                    'rate_limits': CLIENT_REGISTRY.get(client_id, {}).get('rate_limits', {})
                }
            },
            message="系統狀態檢查完成"
        )
        
    except Exception as e:
        logger.error(f"系統狀態檢查失敗: {e}")
        return APIResponse.error(
            f"系統狀態檢查失敗: {str(e)}",
            code=500,
            error_code="STATUS_CHECK_ERROR"
        )

# ============== 工具函數 ==============

def process_audio_with_whisper(file_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """使用 Whisper 處理音頻"""
    try:
        from config import config as app_config
        
        whisper_manager = WhisperManager(
            backend=config.get('whisper_backend', app_config.WHISPER_BACKEND),
            model_size=config.get('whisper_model', app_config.DEFAULT_WHISPER_MODEL)
        )
        
        if not whisper_manager.load_model():
            raise Exception("Whisper 模型載入失敗")
        
        # 載入音頻文件
        import librosa
        audio, sr = librosa.load(file_path, sr=16000)
        
        # 轉錄
        result = whisper_manager.transcribe(
            audio,
            sampling_rate=sr,
            language=config.get('language', 'zh'),
            task='transcribe'
        )
        
        whisper_manager.cleanup()
        return result
        
    except Exception as e:
        logger.error(f"Whisper 處理失敗: {e}")
        raise

def check_whisper_status() -> Dict[str, Any]:
    """檢查 Whisper 服務狀態"""
    try:
        from config import config as app_config
        
        # 嘗試創建 Whisper 管理器
        whisper_manager = WhisperManager(
            backend=app_config.WHISPER_BACKEND, 
            model_size=app_config.DEFAULT_WHISPER_MODEL
        )
        if whisper_manager.load_model():
            info = whisper_manager.get_model_info()
            whisper_manager.cleanup()
            return {
                'status': 'healthy',
                'message': 'Whisper 服務正常',
                'backend': info.get('backend', 'unknown'),
                'model_info': info
            }
        else:
            return {
                'status': 'unhealthy',
                'message': 'Whisper 模型載入失敗'
            }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'message': f'Whisper 服務異常: {str(e)}'
        }

def check_ollama_status() -> Dict[str, Any]:
    """檢查 Ollama 服務狀態"""
    try:
        models = text_service.get_available_models()
        if models:
            return {
                'status': 'healthy',
                'message': 'Ollama 服務正常',
                'available_models': models,
                'model_count': len(models)
            }
        else:
            return {
                'status': 'unhealthy',
                'message': 'Ollama 服務不可用或沒有可用模型'
            }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'message': f'Ollama 服務異常: {str(e)}'
        }

def check_config_status() -> Dict[str, Any]:
    """檢查配置服務狀態"""
    try:
        # 測試配置服務
        test_config = config_service.get_global_config()
        if test_config:
            return {
                'status': 'healthy',
                'message': '配置服務正常',
                'config_fields': len(config_service.get_config_schema()['fields'])
            }
        else:
            return {
                'status': 'unhealthy',
                'message': '配置服務異常'
            }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'message': f'配置服務異常: {str(e)}'
        }