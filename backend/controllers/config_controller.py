"""
配置管理控制器 - 提供配置相關的 API 端點
"""
import logging
from flask import Blueprint, request, jsonify
from services.config_service import config_service, ProcessingConfig
from typing import Dict, Any

logger = logging.getLogger(__name__)

config_bp = Blueprint('config', __name__)

@config_bp.route('/config', methods=['GET'])
def get_config():
    """獲取配置"""
    try:
        user_id = request.args.get('user_id')
        config = config_service.get_user_config(user_id)
        
        return jsonify({
            'status': 'success',
            'config': config_service.export_config(user_id),
            'user_id': user_id
        })
    except Exception as e:
        logger.error(f"獲取配置失敗: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@config_bp.route('/config', methods=['POST'])
def update_config():
    """更新配置"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        config_updates = data.get('config', {})
        
        if not config_updates:
            return jsonify({
                'status': 'error',
                'message': '沒有提供配置更新數據'
            }), 400
        
        # 驗證配置字段
        valid_fields = set(config_service.default_config.__dict__.keys())
        invalid_fields = set(config_updates.keys()) - valid_fields
        
        if invalid_fields:
            return jsonify({
                'status': 'error',
                'message': f'無效的配置字段: {list(invalid_fields)}'
            }), 400
        
        # 更新配置
        success = config_service.update_multiple_fields(user_id, config_updates)
        
        if success:
            updated_config = config_service.get_user_config(user_id)
            return jsonify({
                'status': 'success',
                'message': '配置更新成功',
                'config': config_service.export_config(user_id)
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '配置更新失敗'
            }), 500
            
    except Exception as e:
        logger.error(f"更新配置失敗: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@config_bp.route('/config/field', methods=['PUT'])
def update_config_field():
    """更新單個配置字段"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        field = data.get('field')
        value = data.get('value')
        
        if not field:
            return jsonify({
                'status': 'error',
                'message': '必須提供字段名稱'
            }), 400
        
        success = config_service.update_config_field(user_id, field, value)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'字段 {field} 更新成功',
                'field': field,
                'value': value
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'字段 {field} 更新失敗'
            }), 500
            
    except Exception as e:
        logger.error(f"更新配置字段失敗: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@config_bp.route('/config/reset', methods=['POST'])
def reset_config():
    """重置配置為默認值"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        success = config_service.reset_user_config(user_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': '配置已重置為默認值',
                'config': config_service.export_config(user_id)
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '配置重置失敗'
            }), 500
            
    except Exception as e:
        logger.error(f"重置配置失敗: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@config_bp.route('/config/export', methods=['GET'])
def export_config():
    """導出配置"""
    try:
        user_id = request.args.get('user_id')
        config_data = config_service.export_config(user_id)
        
        return jsonify({
            'status': 'success',
            'config': config_data,
            'export_time': __import__('datetime').datetime.now().isoformat(),
            'user_id': user_id
        })
        
    except Exception as e:
        logger.error(f"導出配置失敗: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@config_bp.route('/config/import', methods=['POST'])
def import_config():
    """導入配置"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        config_data = data.get('config')
        
        if not config_data:
            return jsonify({
                'status': 'error',
                'message': '沒有提供配置數據'
            }), 400
        
        success = config_service.import_config(config_data, user_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': '配置導入成功',
                'config': config_service.export_config(user_id)
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '配置導入失敗'
            }), 500
            
    except Exception as e:
        logger.error(f"導入配置失敗: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@config_bp.route('/config/schema', methods=['GET'])
def get_config_schema():
    """獲取配置架構"""
    try:
        schema = config_service.get_config_schema()
        return jsonify({
            'status': 'success',
            'schema': schema
        })
    except Exception as e:
        logger.error(f"獲取配置架構失敗: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@config_bp.route('/config/presets', methods=['GET'])
def get_config_presets():
    """獲取預設配置"""
    try:
        presets = {
            'default': config_service.export_config(),
            'meeting_optimized': {
                **config_service.export_config(),
                'processing_mode': 'meeting',
                'speaker_count_mode': 'auto',
                'detail_level': 'detailed',
                'enable_timestamps': True
            },
            'lecture_optimized': {
                **config_service.export_config(),
                'processing_mode': 'lecture',
                'detail_level': 'detailed',
                'enable_timestamps': True
            },
            'quick_transcription': {
                **config_service.export_config(),
                'whisper_model': 'base',
                'enable_llm_processing': False,
                'detail_level': 'simple'
            },
            'high_quality': {
                **config_service.export_config(),
                'whisper_model': 'large',
                'speaker_count_mode': 'auto',
                'detail_level': 'detailed',
                'gpu_acceleration': True
            }
        }
        
        return jsonify({
            'status': 'success',
            'presets': presets
        })
    except Exception as e:
        logger.error(f"獲取預設配置失敗: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@config_bp.route('/config/apply-preset', methods=['POST'])
def apply_config_preset():
    """應用預設配置"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        preset_name = data.get('preset')
        
        if not preset_name:
            return jsonify({
                'status': 'error',
                'message': '必須提供預設名稱'
            }), 400
        
        # 獲取預設配置
        presets_response = get_config_presets()
        presets_data = presets_response.get_json()
        
        if presets_data['status'] != 'success':
            return jsonify({
                'status': 'error',
                'message': '無法獲取預設配置'
            }), 500
        
        presets = presets_data['presets']
        
        if preset_name not in presets:
            return jsonify({
                'status': 'error',
                'message': f'預設配置不存在: {preset_name}'
            }), 400
        
        # 應用預設配置
        preset_config = presets[preset_name]
        success = config_service.import_config(preset_config, user_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'預設配置 {preset_name} 應用成功',
                'config': config_service.export_config(user_id)
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '預設配置應用失敗'
            }), 500
            
    except Exception as e:
        logger.error(f"應用預設配置失敗: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@config_bp.route('/config/validate', methods=['POST'])
def validate_config():
    """驗證配置有效性"""
    try:
        data = request.get_json()
        config_data = data.get('config', {})
        
        validation_errors = []
        schema = config_service.get_config_schema()
        
        for field, value in config_data.items():
            if field not in schema['fields']:
                validation_errors.append(f'未知字段: {field}')
                continue
                
            field_schema = schema['fields'][field]
            field_type = field_schema['type']
            
            # 類型驗證
            if field_type == 'boolean' and not isinstance(value, bool):
                validation_errors.append(f'{field}: 必須是布爾值')
            elif field_type == 'integer' and not isinstance(value, int):
                validation_errors.append(f'{field}: 必須是整數')
            elif field_type == 'string' and not isinstance(value, str):
                validation_errors.append(f'{field}: 必須是字符串')
            
            # 選項驗證
            if 'options' in field_schema and value not in field_schema['options']:
                validation_errors.append(f'{field}: 必須是以下選項之一: {field_schema["options"]}')
            
            # 範圍驗證
            if field_type == 'integer':
                if 'min' in field_schema and value < field_schema['min']:
                    validation_errors.append(f'{field}: 不能小於 {field_schema["min"]}')
                if 'max' in field_schema and value > field_schema['max']:
                    validation_errors.append(f'{field}: 不能大於 {field_schema["max"]}')
        
        return jsonify({
            'status': 'success',
            'valid': len(validation_errors) == 0,
            'errors': validation_errors
        })
        
    except Exception as e:
        logger.error(f"配置驗證失敗: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@config_bp.route('/config/debug', methods=['GET'])
def debug_app_config():
    """調試應用配置信息（顯示當前生效的環境變數配置）"""
    try:
        import os
        from config import config
        
        # 獲取敏感配置的掩碼版本
        debug_info = {
            'loaded_config': {
                'NETWORK_MODE_ENABLED': config.NETWORK_MODE_ENABLED,
                'EMAIL_ENABLED': config.EMAIL_ENABLED,
                'EMAIL_SMTP_SERVER': config.EMAIL_SMTP_SERVER,
                'EMAIL_USERNAME': '***' if config.EMAIL_USERNAME else '',
                'EMAIL_PASSWORD': '***' if config.EMAIL_PASSWORD else '',
                'WHISPER_MODEL_FIXED': config.WHISPER_MODEL_FIXED,
                'AI_MODEL_FIXED': config.get_current_ai_model(),
                'AI_ENGINE': config.AI_ENGINE,
                'OLLAMA_MODEL_FIXED': config.OLLAMA_MODEL_FIXED,
                'VLLM_MODEL_FIXED': config.VLLM_MODEL_FIXED,
                'PORT': config.PORT,
                'MAX_CONTENT_LENGTH': config.MAX_CONTENT_LENGTH,
                'MAX_BATCH_UPLOAD_COUNT': config.MAX_BATCH_UPLOAD_COUNT,
                'AUTO_RETRY_COUNT': config.AUTO_RETRY_COUNT,
                'RETRY_INTERVAL': config.RETRY_INTERVAL,
                'TASK_TIMEOUT': config.TASK_TIMEOUT
            },
            'env_variables': {
                'NETWORK_MODE_ENABLED': os.getenv('NETWORK_MODE_ENABLED'),
                'EMAIL_ENABLED': os.getenv('EMAIL_ENABLED'),
                'EMAIL_SMTP_SERVER': os.getenv('EMAIL_SMTP_SERVER'),
                'EMAIL_USERNAME': '***' if os.getenv('EMAIL_USERNAME') else None,
                'EMAIL_PASSWORD': '***' if os.getenv('EMAIL_PASSWORD') else None,
                'WHISPER_MODEL_FIXED': os.getenv('WHISPER_MODEL_FIXED'),
                'AI_MODEL_FIXED': config.get_current_ai_model(),
                'AI_ENGINE': os.getenv('AI_ENGINE'),
                'OLLAMA_MODEL_FIXED': os.getenv('OLLAMA_MODEL_FIXED'),
                'VLLM_MODEL_FIXED': os.getenv('VLLM_MODEL_FIXED'),
                'PORT': os.getenv('PORT'),
                'MAX_UPLOAD_SIZE': os.getenv('MAX_UPLOAD_SIZE'),
                'MAX_BATCH_UPLOAD_COUNT': os.getenv('MAX_BATCH_UPLOAD_COUNT'),
                'AUTO_RETRY_COUNT': os.getenv('AUTO_RETRY_COUNT'),
                'RETRY_INTERVAL': os.getenv('RETRY_INTERVAL'),
                'PROCESSING_TIMEOUT': os.getenv('PROCESSING_TIMEOUT')
            }
        }
        
        return jsonify({
            'status': 'success',
            'debug_info': debug_info,
            'message': '請檢查 loaded_config 和 env_variables 是否一致'
        })
    except Exception as e:
        logger.error(f"獲取調試配置失敗: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500