"""
網路模式控制器 - 管理網路模式和相關功能
"""
from flask import Blueprint, request, jsonify
import logging
from network_manager import network_manager
from email_service import EmailService
from config import config

logger = logging.getLogger(__name__)

network_bp = Blueprint('network', __name__, url_prefix='/api/network')

@network_bp.route('/status', methods=['GET'])
def get_network_status():
    """獲取網路狀態"""
    try:
        status = network_manager.get_network_status()
        
        # 添加Email服務狀態
        email_service = EmailService()
        status['email_enabled'] = email_service.is_enabled()
        status['email_configured'] = bool(
            config.EMAIL_USERNAME and 
            config.EMAIL_PASSWORD and 
            config.EMAIL_TO_ADDRESS
        )
        
        # 添加上傳限制配置
        status['max_batch_upload_count'] = config.MAX_BATCH_UPLOAD_COUNT
        status['auto_retry_count'] = config.AUTO_RETRY_COUNT
        status['retry_interval'] = config.RETRY_INTERVAL
        
        return jsonify({
            'status': 'success',
            'data': status
        })
        
    except Exception as e:
        logger.error(f"獲取網路狀態失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@network_bp.route('/check', methods=['POST'])
def check_connection():
    """檢查網路連接"""
    try:
        force_check = request.json.get('force_check', False) if request.json else False
        is_connected = network_manager.check_internet_connection(force_check=force_check)
        
        return jsonify({
            'status': 'success',
            'data': {
                'connected': is_connected,
                'timestamp': network_manager.last_check_time
            }
        })
        
    except Exception as e:
        logger.error(f"檢查網路連接失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@network_bp.route('/email/test', methods=['POST'])
def test_email():
    """測試Email連接"""
    try:
        if not config.NETWORK_MODE_ENABLED:
            return jsonify({'error': '需要先啟用網路模式'}), 400
            
        email_service = EmailService()
        
        if not email_service.is_enabled():
            return jsonify({'error': 'Email服務未正確配置或網路不可用'}), 400
        
        # 發送測試郵件
        success = email_service.send_notification(
            to_email=config.EMAIL_TO_ADDRESS,
            subject="語音處理系統 - 連接測試",
            message="這是一封測試郵件，如果您收到此郵件，表示Email服務配置正確。"
        )
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Email測試發送成功'
            })
        else:
            return jsonify({'error': 'Email發送失敗'}), 500
            
    except Exception as e:
        logger.error(f"測試Email失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@network_bp.route('/config', methods=['GET'])
def get_config():
    """獲取當前配置（敏感信息會被遮蔽）"""
    try:
        safe_config = {
            'network_mode_enabled': config.NETWORK_MODE_ENABLED,
            'email_enabled': config.EMAIL_ENABLED,
            'email_smtp_server': config.EMAIL_SMTP_SERVER,
            'email_smtp_port': config.EMAIL_SMTP_PORT,
            'email_username': '***' if config.EMAIL_USERNAME else '',
            'email_password': '***' if config.EMAIL_PASSWORD else '',
            'email_from_name': config.EMAIL_FROM_NAME,
            'email_to_address': '***' if config.EMAIL_TO_ADDRESS else '',
            'whisper_model_fixed': config.WHISPER_MODEL_FIXED,
            'ai_model_fixed': config.get_current_ai_model(),
            'ai_engine': config.AI_ENGINE,
            'ollama_model_fixed': config.OLLAMA_MODEL_FIXED,
            'vllm_model_fixed': config.VLLM_MODEL_FIXED
        }
        
        return jsonify({
            'status': 'success',
            'data': safe_config
        })
        
    except Exception as e:
        logger.error(f"獲取配置失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@network_bp.route('/models', methods=['GET'])
def get_model_config():
    """獲取模型配置信息"""
    try:
        model_config = {
            'whisper_model_fixed': config.WHISPER_MODEL_FIXED,
            'ai_model_fixed': config.get_current_ai_model(),
            'ai_engine': config.AI_ENGINE,
            'ollama_model_fixed': config.OLLAMA_MODEL_FIXED,
            'vllm_model_fixed': config.VLLM_MODEL_FIXED,
            'is_whisper_locked': bool(config.WHISPER_MODEL_FIXED),
            'is_ai_locked': bool(config.get_current_ai_model())
        }
        
        return jsonify({
            'status': 'success',
            'data': model_config
        })
        
    except Exception as e:
        logger.error(f"獲取模型配置失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500
