"""
批次處理控制器 - 處理多檔案批次任務相關的 API 請求
"""
from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

batch_bp = Blueprint('batch', __name__, url_prefix='/api/batch')

@batch_bp.route('/progress/<batch_id>', methods=['GET'])
def get_batch_progress(batch_id):
    """獲取批次處理進度"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': '缺少 user_id 參數'}), 400
        
        from services.batch_cache_service import batch_cache_service
        
        # 獲取批次進度
        progress = batch_cache_service.get_batch_progress(batch_id)
        if not progress:
            return jsonify({'error': '找不到指定的批次任務'}), 404
        
        return jsonify({
            'status': 'success',
            'data': progress
        })
        
    except Exception as e:
        logger.error(f"獲取批次進度失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@batch_bp.route('/result/<batch_id>', methods=['GET'])
def get_batch_result(batch_id):
    """獲取批次處理結果（只有在完成後才返回）"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': '缺少 user_id 參數'}), 400
        
        from services.batch_cache_service import batch_cache_service
        
        # 檢查批次是否完成
        if not batch_cache_service.is_batch_completed(batch_id):
            return jsonify({'error': '批次任務尚未完成'}), 400
        
        # 獲取完整結果
        cache_data = batch_cache_service.get_batch_result(batch_id)
        if not cache_data:
            return jsonify({'error': '找不到指定的批次任務'}), 404
        
        # 檢查用戶權限
        if cache_data.get('user_id') != user_id:
            return jsonify({'error': '無權訪問此批次任務'}), 403
        
        # 構建批次結果格式
        batch_result = {
            'task_id': batch_id,
            'batch_info': {
                'total_files': cache_data['total_files'],
                'successful_files': cache_data['completed_files'],
                'failed_files': cache_data['failed_files']
            },
            'files': cache_data['files'],
            'config': cache_data['config'],
            'user_id': cache_data['user_id'],
            'created_at': cache_data['created_at'],
            'completed_at': cache_data['updated_at']
        }
        
        return jsonify({
            'status': 'success',
            'data': batch_result
        })
        
    except Exception as e:
        logger.error(f"獲取批次結果失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@batch_bp.route('/list', methods=['GET'])
def list_user_batches():
    """列出用戶的所有批次任務"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': '缺少 user_id 參數'}), 400
        
        from services.batch_cache_service import batch_cache_service
        
        # 獲取用戶的批次列表
        user_batches = batch_cache_service.list_user_batches(user_id)
        
        return jsonify({
            'status': 'success',
            'data': {
                'batches': user_batches,
                'total_count': len(user_batches)
            }
        })
        
    except Exception as e:
        logger.error(f"列出用戶批次失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@batch_bp.route('/delete/<batch_id>', methods=['DELETE'])
def delete_batch(batch_id):
    """刪除指定的批次緩存"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': '缺少 user_id 參數'}), 400
        
        from services.batch_cache_service import batch_cache_service
        
        # 檢查用戶權限
        cache_data = batch_cache_service.get_batch_result(batch_id)
        if cache_data and cache_data.get('user_id') != user_id:
            return jsonify({'error': '無權刪除此批次任務'}), 403
        
        # 刪除批次緩存
        success = batch_cache_service.delete_batch_cache(batch_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': '批次緩存已刪除'
            })
        else:
            return jsonify({'error': '刪除失敗或批次不存在'}), 404
        
    except Exception as e:
        logger.error(f"刪除批次失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500