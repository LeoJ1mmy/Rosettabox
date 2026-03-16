"""
任務管理控制器 - 處理任務隊列相關的 API 請求
"""
from flask import Blueprint, request, jsonify, current_app
import logging

# 避免循環依賴，延遲導入 queue_manager
def get_queue_manager():
    """動態獲取隊列管理器"""
    try:
        import app
        return getattr(app, 'queue_manager', None)
    except Exception:
        return None

def get_resource_manager():
    """動態獲取資源管理器"""
    try:
        import app
        return getattr(app, 'resource_manager', None)
    except:
        try:
            from utils.resource_manager import resource_manager
            return resource_manager
        except ImportError:
            return None

def get_limiter():
    """動態獲取速率限制器"""
    try:
        import app
        return getattr(app, 'limiter', None)
    except:
        return None

logger = logging.getLogger(__name__)

task_bp = Blueprint('task', __name__, url_prefix='/api/task')

@task_bp.route('/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """獲取任務狀態 - 修復版（無速率限制，允許頻繁輪詢）"""
    try:
        user_id = request.args.get('user_id')
        logger.info(f"請求任務狀態: {task_id}, user_id: {user_id}")

        queue_manager = get_queue_manager()
        if queue_manager:
            status = queue_manager.get_task_status(task_id, user_id)
            if status:
                return jsonify(status)
            # 任務不存在於記憶體中（已過期或重啟後遺失）
            return jsonify({'error': '任務不存在或已過期'}), 404
        else:
            return jsonify({
                'task_id': task_id,
                'status': 'unknown',
                'message': '隊列管理器未初始化'
            })

    except Exception as e:
        logger.error(f"獲取任務狀態失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@task_bp.route('/<task_id>/progress', methods=['GET'])
def get_task_progress(task_id):
    """獲取任務進度"""
    try:
        user_id = request.args.get('user_id')
        logger.info(f"請求任務進度: {task_id}, 用戶: {user_id}")
        
        queue_manager = get_queue_manager()
        if queue_manager:
            task = queue_manager.get_task_status(task_id, user_id)
            if task:
                # 安全地獲取進度信息
                progress_data = task.get('progress', {})
                if isinstance(progress_data, dict):
                    stage = progress_data.get('stage', '未知')
                    percentage = progress_data.get('percentage', 0)
                else:
                    # 如果 progress 不是字典，使用默認值
                    stage = task.get('current_stage', '未知')
                    percentage = progress_data if isinstance(progress_data, (int, float)) else 0
                
                return jsonify({
                    'task_id': task_id,
                    'progress': progress_data if isinstance(progress_data, dict) else {'stage': stage, 'percentage': percentage},
                    'status': task.get('status'),
                    'stage': stage,
                    'percentage': percentage
                })
            else:
                return jsonify({'error': '任務不存在或權限不足'}), 404
        else:
            return jsonify({
                'task_id': task_id,
                'progress': 0,
                'message': '隊列管理器未初始化'
            })
        
    except Exception as e:
        logger.error(f"獲取任務進度失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@task_bp.route('/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    """取消任務"""
    try:
        user_id = request.args.get('user_id')
        logger.info(f"取消任務請求: {task_id}, 用戶: {user_id}")
        
        queue_manager = get_queue_manager()
        if queue_manager:
            success = queue_manager.cancel_task(task_id, user_id)
            if success:
                return jsonify({'message': '任務已取消'})
            else:
                return jsonify({'error': '無法取消任務（任務不存在或權限不足）'}), 404
        else:
            return jsonify({'error': '隊列管理器未初始化'}), 503
        
    except Exception as e:
        logger.error(f"取消任務失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@task_bp.route('/<task_id>/verify', methods=['GET'])
def verify_task(task_id):
    """驗證任務所有權"""
    try:
        user_id = request.args.get('user_id')
        logger.info(f"驗證任務請求: {task_id}, 用戶: {user_id}")
        
        queue_manager = get_queue_manager()
        if queue_manager:
            task = queue_manager.get_task_status(task_id, user_id)
            task_exists = task is not None
            is_owner = task_exists and task.get('user_id') == user_id
            
            return jsonify({
                'valid': task_exists,
                'is_owner': is_owner,
                'task_exists': task_exists,
                'task_id': task_id,
                'user_id': user_id
            })
        else:
            return jsonify({
                'valid': False,
                'is_owner': False,
                'task_exists': False,
                'error': '隊列管理器未初始化'
            })
        
    except Exception as e:
        logger.error(f"驗證任務失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@task_bp.route('/<task_id>/wait', methods=['GET'])
def wait_for_task(task_id):
    """等待任務完成"""
    try:
        user_id = request.args.get('user_id')
        timeout = int(request.args.get('timeout', 1800))  # 默認30分鐘
        
        logger.info(f"等待任務完成請求: {task_id}, 用戶: {user_id}, 超時: {timeout}秒")
        
        queue_manager = get_queue_manager()
        if not queue_manager:
            return jsonify({'error': '隊列管理器不可用'}), 503
        
        # 首先驗證任務所有權
        if not queue_manager.verify_task_ownership(task_id, user_id):
            return jsonify({'error': '任務不存在或無權限訪問'}), 404
        
        # 等待任務完成
        result = queue_manager.wait_for_task_completion(task_id, user_id, timeout)
        if result:
            return jsonify(result)
        else:
            return jsonify({'error': '任務等待超時'}), 408
            
    except Exception as e:
        logger.error(f"等待任務失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@task_bp.route('/queue/status', methods=['GET'])
def get_queue_status():
    """獲取隊列狀態"""
    try:
        logger.info("獲取隊列狀態請求")
        queue_manager = get_queue_manager()
        if queue_manager:
            status = queue_manager.get_queue_status()
            return jsonify(status)
        else:
            return jsonify({
                'queue_length': 0,
                'is_processing': False,
                'current_task': None,
                'waiting_tasks': [],
                'status': 'no_queue_manager',
                'message': '隊列管理器未初始化'
            })
        
    except Exception as e:
        logger.error(f"獲取隊列狀態失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@task_bp.route('/user/<user_id>/tasks', methods=['GET'])
def get_user_tasks(user_id):
    """獲取用戶的所有任務"""
    try:
        logger.info(f"獲取用戶任務: {user_id}")
        
        queue_manager = get_queue_manager()
        if queue_manager:
            tasks = queue_manager.get_user_tasks(user_id)
            return jsonify({
                'tasks': tasks,
                'user_id': user_id,
                'count': len(tasks)
            })
        else:
            return jsonify({
                'tasks': [],
                'user_id': user_id,
                'error': '隊列管理器未初始化'
            })
        
    except Exception as e:
        logger.error(f"獲取用戶任務失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@task_bp.route('/global/status', methods=['GET'])
def get_global_queue_status():
    """獲取全局隊列狀態，包含他人任務但保護隱私"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': '需要提供用戶ID'}), 400
        
        logger.info(f"獲取全局隊列狀態: {user_id}")
        
        queue_manager = get_queue_manager()
        if queue_manager:
            global_status = queue_manager.get_global_queue_status(user_id)
            # 調試信息
            logger.info(f"🔍 Global status for user {user_id}:")
            logger.info(f"   User tasks: {len(global_status.get('user_tasks', []))}")
            logger.info(f"   Other tasks: {len(global_status.get('other_tasks', []))}")
            logger.info(f"   Queue stats: {global_status.get('queue_stats', {})}")
            return jsonify(global_status)
        else:
            return jsonify({
                'user_tasks': [],
                'other_tasks': [],
                'queue_stats': {
                    'total_tasks': 0,
                    'active_tasks': 0,
                    'pending_tasks': 0,
                    'completed_tasks': 0,
                    'failed_tasks': 0
                },
                'error': '隊列管理器未初始化'
            })
        
    except Exception as e:
        logger.error(f"獲取全局隊列狀態失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@task_bp.route('/cleanup', methods=['POST'])
def cleanup_tasks():
    """清理已完成的任務"""
    try:
        logger.info("清理任務請求")
        
        queue_manager = get_queue_manager()
        if queue_manager:
            # 簡單清理，移除已完成的任務
            cleaned_count = len(queue_manager.completed)
            queue_manager.completed.clear()
            return jsonify({
                'message': f'已清理 {cleaned_count} 個已完成的任務',
                'cleaned_count': cleaned_count
            })
        else:
            return jsonify({
                'message': '隊列管理器未初始化，無法清理',
                'cleaned_count': 0
            })
        
    except Exception as e:
        logger.error(f"清理任務失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@task_bp.route('/clear-all', methods=['POST'])
def clear_all_tasks():
    """清除所有任務"""
    try:
        user_id = request.json.get('user_id') if request.is_json else request.form.get('user_id')
        clear_all = request.json.get('clear_all', False) if request.is_json else request.form.get('clear_all', 'false').lower() == 'true'
        
        logger.info(f"清除任務請求: 用戶={user_id}, 清除全部={clear_all}")
        
        queue_manager = get_queue_manager()
        if not queue_manager:
            return jsonify({'error': '隊列管理器不可用'}), 503
        
        # 如果 clear_all 為 true，清除所有用戶的任務；否則只清除指定用戶的任務
        target_user_id = None if clear_all else user_id
        
        result = queue_manager.clear_all_tasks(target_user_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'cleared_count': result['cleared_count'],
                'cleared_tasks': result['cleared_tasks']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
            
    except Exception as e:
        logger.error(f"清除所有任務失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500