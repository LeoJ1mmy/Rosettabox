from flask import Blueprint, request, jsonify
from services.feedback_service import FeedbackService
import logging

logger = logging.getLogger(__name__)

feedback_bp = Blueprint('feedback', __name__)

# 創建服務實例
feedback_service = FeedbackService()

@feedback_bp.route('/submit', methods=['POST'])
def submit_feedback():
    """提交回饋"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': '請求數據無效'
            }), 400
        
        required_fields = ['type', 'message']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'缺少必要欄位: {", ".join(missing_fields)}'
            }), 400
        
        feedback_data = {
            'type': data.get('type', 'other'),
            'subject': data.get('subject', ''),
            'message': data.get('message', ''),
            'user_email': data.get('userEmail', ''),
            'timestamp': None
        }
        
        result = feedback_service.send_feedback(feedback_data)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': '回饋已成功送出'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f"發送失敗: {result['error']}"
            }), 500
            
    except Exception as e:
        logger.error(f"提交回饋失敗: {str(e)}")
        return jsonify({
            'success': False,
            'error': '提交回饋失敗'
        }), 500