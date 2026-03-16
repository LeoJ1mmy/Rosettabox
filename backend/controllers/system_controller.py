"""
系統管理控制器 - 處理系統狀態和管理相關的 API 請求
"""
from flask import Blueprint, request, jsonify
import logging
from utils.resource_manager import resource_manager
from utils.cache_manager import cache_manager
from utils.model_manager import model_manager

logger = logging.getLogger(__name__)

system_bp = Blueprint('system', __name__, url_prefix='/api/system')

@system_bp.route('/health', methods=['GET'])
def health_check():
    """系統健康檢查 - 完整版本"""
    try:
        from utils.timezone_utils import to_taipei_isoformat
        from services.ai_engine_service import ai_engine_manager

        system_stats = resource_manager.get_system_stats()

        # 檢查 AI 引擎狀態
        ai_engine_status = {
            'status': 'unknown',
            'model': None
        }
        try:
            if ai_engine_manager.check_health():
                ai_engine_status = {
                    'status': 'healthy',
                    'model': ai_engine_manager.get_current_model()
                }
            else:
                ai_engine_status['status'] = 'unavailable'
        except Exception as e:
            ai_engine_status = {'status': 'error', 'error': str(e)}

        # 檢查 ASR/Whisper 狀態
        whisper_status = {
            'loaded': False,
            'model': None
        }
        try:
            from services.asr_service import get_asr_service
            asr = get_asr_service()
            asr_info = asr.get_model_info()
            if asr_info and asr_info.get('status') != 'not_loaded':
                whisper_status = {
                    'loaded': asr_info.get('is_loaded', False),
                    'model': asr_info.get('model_size'),
                    'backend': asr_info.get('backend'),
                    'device': asr_info.get('device')
                }
        except Exception:
            pass

        # 檢查隊列狀態
        queue_status = {'status': 'unknown'}
        try:
            from app import get_queue_manager
            qm = get_queue_manager()
            if qm:
                queue_stats = qm.get_queue_status()
                queue_status = {
                    'status': 'healthy',
                    'pending': queue_stats.get('pending_tasks', 0),
                    'active': queue_stats.get('active_tasks', 0),
                    'completed': queue_stats.get('completed_tasks', 0)
                }
        except Exception:
            pass

        return jsonify({
            'status': 'healthy',
            'timestamp': to_taipei_isoformat(),
            'system': system_stats,
            'ai_engine': ai_engine_status,
            'whisper': whisper_status,
            'queue': queue_status
        })

    except Exception as e:
        logger.error(f"健康檢查失敗: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@system_bp.route('/stats', methods=['GET'])
def get_system_stats():
    """獲取系統統計信息"""
    try:
        system_stats = resource_manager.get_system_stats()
        cache_stats = cache_manager.get_stats()
        model_stats = model_manager.get_loaded_models()
        
        return jsonify({
            'system': system_stats,
            'cache': cache_stats,
            'models': {
                'loaded': model_stats,
                'memory_usage': model_manager.get_memory_usage()
            }
        })
        
    except Exception as e:
        logger.error(f"獲取系統統計失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@system_bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    """清理系統快取"""
    try:
        cache_manager.clear_all()
        
        return jsonify({
            'message': '快取已清空',
            'cache_stats': cache_manager.get_stats()
        })
        
    except Exception as e:
        logger.error(f"清理快取失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@system_bp.route('/memory/cleanup', methods=['POST'])
def cleanup_memory():
    """清理系統記憶體"""
    try:
        stats = resource_manager.cleanup_memory()
        
        return jsonify({
            'message': '記憶體清理完成',
            'cleanup_stats': stats
        })
        
    except Exception as e:
        logger.error(f"記憶體清理失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@system_bp.route('/gpu/cleanup', methods=['POST'])
def cleanup_gpu_cache():
    """強制清理GPU緩存"""
    try:
        from utils.gpu_cleaner import force_cleanup, get_gpu_info
        
        # 獲取清理前的GPU狀態
        gpu_info_before = get_gpu_info()
        
        # 執行強制清理
        success = force_cleanup()
        
        # 獲取清理後的GPU狀態
        gpu_info_after = get_gpu_info()
        
        if success:
            return jsonify({
                'message': 'GPU緩存清理完成',
                'gpu_info_before': gpu_info_before,
                'gpu_info_after': gpu_info_after,
                'cleaned': True
            })
        else:
            return jsonify({
                'error': 'GPU緩存清理失敗',
                'gpu_info': gpu_info_before,
                'cleaned': False
            }), 500
            
    except Exception as e:
        logger.error(f"GPU緩存清理API失敗: {str(e)}")
        return jsonify({'error': f"GPU緩存清理失敗: {str(e)}"}), 500

@system_bp.route('/gpu/info', methods=['GET'])
def get_gpu_info_api():
    """獲取GPU記憶體資訊"""
    try:
        from utils.gpu_cleaner import get_gpu_info
        
        gpu_info = get_gpu_info()
        
        if gpu_info:
            return jsonify({
                'gpu_info': gpu_info,
                'available': True
            })
        else:
            return jsonify({
                'message': 'GPU不可用或無法獲取資訊',
                'available': False
            })
            
    except Exception as e:
        logger.error(f"獲取GPU資訊API失敗: {str(e)}")
        return jsonify({'error': f"獲取GPU資訊失敗: {str(e)}"}), 500

@system_bp.route('/temp-files/cleanup', methods=['POST'])
def cleanup_temp_files():
    """清理臨時文件"""
    try:
        import asyncio
        
        # 如果在事件循環中，直接運行
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在運行的事件循環中創建任務
                future = asyncio.create_task(
                    resource_manager.cleanup_temp_files_async()
                )
                # 這裡需要等待完成，但不能在運行的事件循環中使用 await
                # 所以我們返回一個後台任務狀態
                return jsonify({
                    'message': '臨時文件清理已開始',
                    'status': 'running'
                })
        except RuntimeError:
            # 沒有運行的事件循環，創建新的
            stats = asyncio.run(resource_manager.cleanup_temp_files_async())
            
            return jsonify({
                'message': '臨時文件清理完成',
                'cleanup_stats': stats
            })
        
    except Exception as e:
        logger.error(f"清理臨時文件失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@system_bp.route('/models/unload/<model_name>', methods=['POST'])
def unload_model(model_name):
    """卸載特定模型"""
    try:
        model_manager.unload_model(model_name)
        
        return jsonify({
            'message': f'模型 {model_name} 已卸載',
            'loaded_models': model_manager.get_loaded_models()
        })
        
    except Exception as e:
        logger.error(f"卸載模型失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@system_bp.route('/models/unload-all', methods=['POST'])
def unload_all_models():
    """卸載所有模型"""
    try:
        model_manager.unload_all()
        
        return jsonify({
            'message': '所有模型已卸載',
            'loaded_models': model_manager.get_loaded_models()
        })
        
    except Exception as e:
        logger.error(f"卸載所有模型失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500