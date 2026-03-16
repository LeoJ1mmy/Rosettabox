import os
import sys
import site
import ctypes

# 設置 cuDNN 庫路徑（在導入 torch 或其他模組之前）
try:
    site_packages = site.getsitepackages()[0] if site.getsitepackages() else None
    if not site_packages:
        site_packages = os.path.join(sys.prefix, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')
    
    # 添加 ctranslate2.libs 和 nvidia/cudnn/lib 到 LD_LIBRARY_PATH
    ct2_libs_path = os.path.join(site_packages, 'ctranslate2.libs')
    cudnn_lib_path = os.path.join(site_packages, 'nvidia', 'cudnn', 'lib')
    
    current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
    paths_to_add = []
    
    if os.path.exists(ct2_libs_path) and ct2_libs_path not in current_ld_path:
        paths_to_add.append(ct2_libs_path)
    
    if os.path.exists(cudnn_lib_path) and cudnn_lib_path not in current_ld_path:
        paths_to_add.append(cudnn_lib_path)
    
    if paths_to_add:
        new_ld_path = ':'.join(paths_to_add)
        if current_ld_path:
            os.environ['LD_LIBRARY_PATH'] = f"{new_ld_path}:{current_ld_path}"
        else:
            os.environ['LD_LIBRARY_PATH'] = new_ld_path
        
        # Preload cuDNN libraries BEFORE importing any modules that might use them
        # Try ctranslate2.libs first (it has its own cuDNN)
        ct2_cudnn = os.path.join(ct2_libs_path, 'libcudnn-74a4c495.so.9.1.0')
        if os.path.exists(ct2_cudnn):
            try:
                ctypes.CDLL(ct2_cudnn, mode=ctypes.RTLD_GLOBAL)
            except Exception:
                pass
        
        # Also try nvidia/cudnn/lib
        cudnn_ops_path = os.path.join(cudnn_lib_path, 'libcudnn_ops.so.9.1.0')
        if os.path.exists(cudnn_ops_path):
            try:
                ctypes.CDLL(cudnn_ops_path, mode=ctypes.RTLD_GLOBAL)
            except Exception:
                pass
except Exception as e:
    # 🔒 改善錯誤處理：記錄錯誤而非靜默失敗
    import sys
    print(f"⚠️ cuDNN 預載入警告: {e}", file=sys.stderr)

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import requests
import signal
import threading
import time
from datetime import datetime
from utils.timezone_utils import now_taipei, to_taipei_isoformat

# 安全性導入
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False
    logging.warning("Flask-Limiter 未安裝，速率限制功能將被禁用")

# 導入配置
from config import config

# 導入處理模組
from processing import process_task
from processing.task_processor import cleanup_cuda_memory, unload_ollama_model

# Global variables for storing initialized managers
queue_manager = None
resource_manager = None
model_manager = None
config_service = None
cache_manager = None
limiter = None  # 速率限制器


def get_queue_manager():
    """動態獲取隊列管理器"""
    global queue_manager
    return queue_manager


def get_resource_manager():
    """動態獲取資源管理器"""
    global resource_manager
    return resource_manager


def get_model_manager():
    """動態獲取模型管理器"""
    global model_manager
    return model_manager


def get_config_service():
    """動態獲取配置服務"""
    global config_service
    return config_service


def get_cache_manager():
    """動態獲取緩存管理器"""
    global cache_manager
    return cache_manager


def init_managers():
    """安全地初始化所有管理器"""
    global queue_manager, resource_manager, model_manager, config_service, cache_manager

    services_loaded = []

    try:
        from services.config_service import config_service as cs
        config_service = cs
        services_loaded.append("配置服務")
    except Exception as e:
        logger.error(f"❌ 配置服務初始化失敗: {e}")
        config_service = None

    try:
        from utils.resource_manager import resource_manager as rm
        resource_manager = rm
        services_loaded.append("資源管理器")
    except Exception as e:
        logger.error(f"❌ 資源管理器初始化失敗: {e}")
        resource_manager = None

    try:
        from utils.model_manager import model_manager as mm
        model_manager = mm
        services_loaded.append("模型管理器")
    except Exception as e:
        logger.error(f"❌ 模型管理器初始化失敗: {e}")
        model_manager = None

    try:
        from utils.cache_manager import cache_manager as cm
        cache_manager = cm
        services_loaded.append("緩存管理器")
    except Exception as e:
        logger.error(f"❌ 緩存管理器初始化失敗: {e}")
        cache_manager = None

    try:
        from task_queue import QueueManager
        queue_manager = QueueManager()
        services_loaded.append("隊列管理器")
        # 只記錄隊列摘要信息
        pending = len(queue_manager.queue)
        completed = len(queue_manager.completed)
        if pending > 0 or completed > 0:
            logger.info(f"📊 隊列: {pending} 待處理, {completed} 已完成")
    except ImportError as e:
        logger.warning(f"⚠️ 隊列管理器未找到，將跳過隊列功能: {e}")
        queue_manager = None
    except Exception as e:
        logger.error(f"❌ 隊列管理器初始化失敗: {e}")
        logger.error(f"   錯誤詳情: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        queue_manager = None

    # 顯示服務初始化摘要
    if services_loaded:
        logger.info(f"✅ 已載入 {len(services_loaded)} 個服務")


def register_blueprints_safely(app):
    """安全地註冊所有 blueprints"""
    blueprint_errors = []
    registered_controllers = []

    blueprints = [
        ('controllers.audio_controller', 'audio_bp', '音頻控制器'),
        ('controllers.text_controller', 'text_bp', '文字控制器'),
        ('controllers.task_controller', 'task_bp', '任務控制器'),
        ('controllers.batch_controller', 'batch_bp', '批次控制器'),
        ('controllers.system_controller', 'system_bp', '系統控制器'),
        ('controllers.config_controller', 'config_bp', '配置控制器'),
        ('controllers.network_controller', 'network_bp', '網路控制器'),
        ('controllers.feedback_controller', 'feedback_bp', '回饋控制器'),
        ('controllers.vocabulary_controller', 'vocabulary_bp', '詞彙管理控制器'),
        ('controllers.hot_words_controller', 'hot_words_bp', '熱詞管理控制器'),
        ('external_api.v1.api', 'api_v1', '外部 API v1')
    ]

    for module_name, blueprint_name, display_name in blueprints:
        try:
            module = __import__(module_name, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)

            if module_name == 'controllers.config_controller':
                app.register_blueprint(blueprint, url_prefix='/api')
            elif module_name == 'controllers.feedback_controller':
                app.register_blueprint(blueprint, url_prefix='/api/feedback')
            else:
                app.register_blueprint(blueprint)

            registered_controllers.append(display_name)
        except Exception as e:
            error_msg = f"{display_name}註冊失敗: {e}"
            logger.error(f"❌ {error_msg}")
            blueprint_errors.append(error_msg)

            if module_name == 'controllers.task_controller':
                try:
                    register_fallback_task_routes(app)
                except Exception:
                    pass

    # 只顯示摘要，避免每個 worker 都打印所有控制器
    if registered_controllers:
        logger.info(f"✅ 已註冊 {len(registered_controllers)} 個控制器")

    return blueprint_errors


def start_task_processor():
    """啟動任務處理器工作線程"""
    def task_worker():
        """任務處理工作線程"""
        logger.info("🔄 任務處理器已啟動")
        
        while not _shutdown_event.is_set():
            try:
                qm = get_queue_manager()
                if qm:
                    # 獲取下一個任務
                    task = qm.get_next_task()
                    if task:
                        logger.info(f"📋 開始處理任務: {task['task_id']}")
                        try:
                            process_task(task)
                        except Exception as e:
                            logger.error(f"❌ 任務處理失敗: {task['task_id']} - {str(e)}")
                            # 標記任務失敗
                            try:
                                qm.fail_task(task['task_id'], str(e))
                            except Exception as fail_err:
                                logger.error(f"❌ 標記任務失敗時出錯: {fail_err}")
                    else:
                        # 沒有任務，使用 Event.wait 替代 sleep 以便快速響應關閉
                        _shutdown_event.wait(timeout=5)
                else:
                    logger.warning("⚠️ 隊列管理器不可用，任務處理器休眠")
                    _shutdown_event.wait(timeout=10)
                
            except Exception as e:
                logger.error(f"❌ 任務處理器錯誤: {str(e)}")
                _shutdown_event.wait(timeout=5)
        
        logger.info("🛑 任務處理器已停止")
    
    # 在守護線程中運行任務處理器
    worker_thread = threading.Thread(target=task_worker, daemon=True)
    worker_thread.start()
    logger.info("✅ 任務處理器線程已啟動")


def register_fallback_task_routes(app):
    """註冊降級任務路由"""
    @app.route('/api/task/queue/status', methods=['GET'])
    def emergency_queue_status():
        try:
            qm = get_queue_manager()
            if qm:
                status = qm.get_queue_status()
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
            return jsonify({
                'error': '隊列狀態檢查失敗',
                'message': str(e)
            }), 500

    @app.route('/api/task/reset', methods=['POST'])
    def reset_stuck_task():
        """重置卡住的任務處理器"""
        try:
            qm = get_queue_manager()
            if not qm:
                return jsonify({'error': '隊列管理器未初始化'}), 500

            # 獲取當前卡住的任務
            current_task = qm.processor.get_current_task()

            # 強制清除處理狀態
            with qm.processor.lock:
                if qm.processor.processing_task:
                    task_id = qm.processor.processing_task.get('task_id', '未知')
                    logger.warning(f"🔧 強制清除卡住的任務: {task_id}")
                    qm.processor.processing_task = None
                    qm.processor.progress = {}

            return jsonify({
                'success': True,
                'message': '任務處理器已重置',
                'cleared_task': current_task
            })

        except Exception as e:
            logger.error(f"❌ 重置任務處理器失敗: {str(e)}")
            return jsonify({
                'error': '重置失敗',
                'message': str(e)
            }), 500


# 設置日誌
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 🛑 Graceful shutdown 標記
_shutdown_event = threading.Event()


def _graceful_shutdown(signum, frame):
    """處理 SIGTERM/SIGINT，優雅地關閉服務"""
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logger.info(f"🛑 收到 {sig_name} 信號，開始優雅關閉...")
    _shutdown_event.set()

    # 1. 標記正在處理的任務為失敗
    qm = get_queue_manager()
    if qm and hasattr(qm, 'processor') and qm.processor.processing_task:
        task_id = qm.processor.processing_task.get('task_id', 'unknown')
        logger.info(f"🛑 標記處理中的任務為失敗: {task_id}")
        try:
            qm.fail_task(task_id, f"伺服器收到 {sig_name} 信號正在關閉")
        except Exception as e:
            logger.error(f"❌ 標記任務失敗時出錯: {e}")

    # 2. 清理 GPU 記憶體
    try:
        cleanup_cuda_memory()
        logger.info("🧹 GPU 記憶體已清理")
    except Exception as e:
        logger.error(f"❌ GPU 記憶體清理失敗: {e}")

    # 3. 卸載 Ollama 模型
    try:
        unload_ollama_model()
        logger.info("🧹 Ollama 模型已卸載")
    except Exception as e:
        logger.error(f"❌ Ollama 模型卸載失敗: {e}")

    # 4. 關閉 ModelManager
    mm = get_model_manager()
    if mm:
        try:
            mm.unload_all()
            logger.info("🧹 所有模型已卸載")
        except Exception as e:
            logger.error(f"❌ 模型卸載失敗: {e}")

    logger.info("🛑 優雅關閉完成")
    raise SystemExit(0)


# 註冊信號處理器（僅在主線程中）
if threading.current_thread() is threading.main_thread():
    signal.signal(signal.SIGTERM, _graceful_shutdown)
    signal.signal(signal.SIGINT, _graceful_shutdown)


def create_app():
    """創建 Flask 應用程式"""
    global limiter

    app = Flask(__name__)

    app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
    app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER

    # 🔒 安全的 CORS 配置
    # 從環境變數讀取允許的來源
    allowed_origins = os.getenv('CORS_ORIGINS', '*')
    is_production = os.getenv('DOCKER_ENV') == 'true' or os.getenv('FLASK_ENV') == 'production'

    if allowed_origins != '*':
        allowed_origins = [origin.strip() for origin in allowed_origins.split(',')]
        logger.info(f"🔒 CORS 限制已啟用: {allowed_origins}")
        CORS(app,
             origins=allowed_origins,
             supports_credentials=True,
             allow_headers=['Content-Type', 'Authorization', 'X-Requested-With', 'X-Admin-Password'],
             methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    elif is_production:
        # 🔒 生產環境警告：使用 * 有安全風險
        logger.warning("⚠️ 生產環境使用 CORS_ORIGINS=* 有安全風險！建議設置具體的允許來源")
        logger.warning("   範例: CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com")
        CORS(app,
             supports_credentials=True,
             allow_headers=['Content-Type', 'Authorization', 'X-Requested-With', 'X-Admin-Password'],
             methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    else:
        logger.info("🔧 開發環境: CORS 允許所有來源")
        CORS(app)

    # 初始化管理器
    init_managers()

    # 註冊blueprints
    blueprint_errors = register_blueprints_safely(app)

    # 🔒 速率限制配置（在註冊blueprints後設置，以便正確豁免端點）
    # 注意：已大幅放寬限制以支援 Cloudflare Tunnel 多用戶同時訪問
    if LIMITER_AVAILABLE:
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=["10000 per day", "1000 per hour"],  # 大幅放寬：1000/hour, 10000/day
            storage_uri="memory://"
        )

        # 豁免任務狀態查詢端點（需要頻繁輪詢）
        @limiter.request_filter
        def exempt_task_status_endpoints():
            """豁免任務狀態查詢端點的速率限制（不豁免上傳）"""
            return request.endpoint in [
                'task.get_task_status',
                'task.get_global_queue_status',
                'task.get_task_progress',
                'task.verify_task'
                # 🔒 安全修復：上傳端點不再豁免，使用專用速率限制
            ]

        # 🔒 為上傳端點設置專用速率限制（防止 DoS）
        @app.before_request
        def apply_upload_rate_limit():
            """對上傳端點應用專用速率限制"""
            if request.endpoint in ['audio.upload_audio', 'audio.upload_video']:
                # 每 IP 每小時最多 50 次上傳，每分鐘最多 10 次
                try:
                    limiter.limit("50 per hour; 10 per minute")(lambda: None)()
                except Exception as e:
                    if "rate limit" in str(e).lower():
                        from flask import jsonify
                        logger.warning(f"🔒 上傳速率限制觸發: {request.remote_addr}")
                        return jsonify({
                            'error': '上傳請求過於頻繁，請稍後再試',
                            'retry_after': 60
                        }), 429

        logger.info("🔒 速率限制已啟用: 1000/hour 通用, 50/hour 上傳 (任務狀態端點已豁免)")
    else:
        logger.warning("⚠️ Flask-Limiter 未安裝，速率限制功能禁用")

    if blueprint_errors:
        logger.warning(f"⚠️ 部分控制器註冊失敗: {len(blueprint_errors)} 個")
    else:
        logger.info("✅ 所有控制器註冊成功")

    register_error_handlers(app)
    register_health_check(app)
    register_basic_routes(app)
    
    # 啟動任務處理器
    start_task_processor()

    # 啟動文件清理調度器
    start_cleanup_scheduler()

    return app


def start_cleanup_scheduler():
    """啟動定期文件清理調度器"""
    def cleanup_worker():
        """文件清理工作線程 - 每小時執行一次"""
        from utils.file_cleaner import FileCleanupManager

        logger.info("🧹 文件清理調度器已啟動（每小時清理超過 24 小時的舊文件）")

        # 首次啟動時等待 5 分鐘，讓系統穩定
        time.sleep(300)

        while True:
            try:
                cleaner = FileCleanupManager(config.UPLOAD_FOLDER)
                result = cleaner.cleanup_old_files(max_age_hours=24)

                if result['cleaned_count'] > 0:
                    logger.info(f"🧹 定期清理: 刪除 {result['cleaned_count']} 個文件，"
                               f"釋放 {result['cleaned_size_mb']:.2f} MB")

            except Exception as e:
                logger.error(f"❌ 定期清理錯誤: {e}")

            # 每小時執行一次
            time.sleep(3600)

    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    logger.info("✅ 文件清理調度器線程已啟動")


def register_error_handlers(app):
    """註冊全局錯誤處理器"""

    @app.errorhandler(413)
    def file_too_large(error):
        max_mb = config.MAX_CONTENT_LENGTH // (1024 * 1024)
        return jsonify({
            'error': f'文件過大！最大允許上傳 {max_mb}MB',
            'max_size_mb': max_mb,
            'code': 'FILE_TOO_LARGE'
        }), 413

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': '請求格式錯誤',
            'code': 'BAD_REQUEST'
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': '接口不存在'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': '內部服務器錯誤'}), 500


def register_health_check(app):
    """註冊健康檢查端點"""

    @app.route('/api/health', methods=['GET'])
    def health_check():
        try:
            health_status = {
                'status': 'healthy',
                'timestamp': to_taipei_isoformat(),
                'components': {
                    'queue_manager': 'available' if queue_manager else 'unavailable',
                    'resource_manager': 'available' if resource_manager else 'unavailable',
                    'model_manager': 'available' if model_manager else 'unavailable',
                    'config_service': 'available' if config_service else 'unavailable'
                }
            }

            critical_components = ['config_service']
            for component in critical_components:
                if health_status['components'][component] == 'unavailable':
                    health_status['status'] = 'degraded'

            return jsonify(health_status)
        
        except Exception as e:
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500


def register_basic_routes(app):
    """註冊基本路由"""

    @app.route('/api/info', methods=['GET'])
    def info():
        return jsonify({
            'service': 'LeoQxAIBox Voice Text Processor',
            'version': '2.0.0',
            'description': '智能語音轉文字和文字整理系統',
            'features': [
                '語音識別 (Whisper)',
                'AI 文字整理',
                '任務隊列管理'
            ]
        })

    @app.route('/api/whisper/models', methods=['GET'])
    def get_whisper_models():
        # 始終使用配置中的固定模型
        model_id = config.WHISPER_MODEL_FIXED if config.WHISPER_MODEL_FIXED else config.DEFAULT_WHISPER_MODEL

        # 定義模型信息對應表
        model_info = {
            'breeze-asr-1.2g': {
                'name': 'Breeze ASR-1.2G',
                'size': '~1.2 GB',
                'description': '基於 Whisper 微調，專為中文和中英混用優化'
            },
            'tiny': {
                'name': 'Tiny',
                'size': '~39 MB',
                'description': '最快的模型，適合快速測試'
            },
            'base': {
                'name': 'Base',
                'size': '~142 MB',
                'description': '平衡速度和準確度'
            },
            'small': {
                'name': 'Small',
                'size': '~483 MB',
                'description': '較高的準確度'
            },
            'medium': {
                'name': 'Medium',
                'size': '~1.5 GB',
                'description': '高準確度，需要更多資源'
            },
            'large': {
                'name': 'Large',
                'size': '~3.1 GB',
                'description': '最高準確度，但需要更多時間和資源'
            },
            'large-v3': {
                'name': 'Large V3',
                'size': '~3.1 GB',
                'description': 'Whisper Large V3，最新版本，最高準確度'
            },
            'large-v3-turbo': {
                'name': 'Large V3 Turbo',
                'size': '~1.6 GB',
                'description': 'Whisper Large V3 Turbo，速度快 4 倍，準確度接近 Large'
            },
            'turbo': {
                'name': 'Turbo',
                'size': '~1.6 GB',
                'description': 'Whisper Turbo，速度優先'
            }
        }

        # 獲取模型信息，如果沒有找到則使用預設值
        info = model_info.get(model_id, {
            'name': model_id,
            'size': '未知',
            'description': '自定義模型'
        })

        # 返回固定模型
        fixed_model = {
            'id': model_id,
            'name': info['name'],
            'display_name': f"{info['name']} (系統配置)",
            'size': info['size'],
            'recommended': True,
            'locked': True,
            'description': info['description']
        }

        return jsonify({
            'status': 'success',
            'models': [fixed_model],
            'default_model': model_id,
            'total_count': 1,
            'fixed_model': model_id
        })

    @app.route('/api/ai/models', methods=['GET'])
    def get_ai_models():
        try:
            # 始終使用配置中的固定模型
            current_model = config.get_current_ai_model()

            # 檢查 Ollama/vLLM 連接狀態
            service_connected = False
            if config.AI_ENGINE == 'vllm':
                try:
                    response = requests.get(f"{config.VLLM_URL}/v1/models", timeout=5)
                    service_connected = response.status_code == 200
                except:
                    pass
            else:  # ollama
                try:
                    response = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
                    service_connected = response.status_code == 200
                except:
                    pass

            # 定義模型信息對應表
            model_info = {
                'gpt-oss:20b': {'size': '~13 GB', 'description': '高性能語言模型'},
                'qwen2.5-coder:14b': {'size': '~9.0 GB', 'description': 'Qwen 2.5 程式碼優化模型'},
                'deepseek-r1:14b': {'size': '~9.0 GB', 'description': 'DeepSeek 推理模型'},
                'phi4:14b': {'size': '~9.1 GB', 'description': 'Microsoft Phi-4 模型'},
                'qwq:32b': {'size': '~19 GB', 'description': '大型語言模型'},
                'llama3.1:8b': {'size': '~4.7 GB', 'description': 'Meta Llama 3.1 模型'},
                'phi4-mini:3.8b': {'size': '~2.3 GB', 'description': 'Phi-4 輕量版'},
                'TwinkleAI/Llama-3.2-3B-F1-Resoning-Instruct:3b': {'size': '~2.0 GB', 'description': 'Llama 3.2 推理優化版'},
                'twinkle-ai/Llama-3.2-3B-F1-Instruct': {'size': '~2.0 GB', 'description': 'Llama 3.2 指令優化版'}
            }

            # 獲取模型信息
            info = model_info.get(current_model, {
                'size': '未知',
                'description': '自定義 AI 模型'
            })

            # 返回固定模型
            fixed_model = {
                'id': current_model,
                'name': current_model,
                'display_name': f'{current_model} (系統配置)',
                'size': info['size'],
                'type': config.AI_ENGINE,
                'installed': service_connected,
                'recommended': True,
                'locked': True,
                'description': info['description']
            }

            return jsonify({
                'status': 'success',
                'models': [fixed_model],
                'total_count': 1,
                'service_connected': service_connected,
                'ai_engine': config.AI_ENGINE,
                'fixed_model': current_model
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/ollama/status', methods=['GET'])
    def get_ollama_status():
        """檢查 Ollama 服務狀態"""
        try:
            ollama_url = f"{config.OLLAMA_URL}/api/tags"
            response = requests.get(ollama_url, timeout=5)
            
            if response.status_code == 200:
                ollama_models = response.json().get('models', [])
                return jsonify({
                    'status': 'connected',
                    'message': '',
                    'model_count': len(ollama_models),
                    'models': [model.get('name', '') for model in ollama_models],
                    'server_url': config.OLLAMA_URL,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Ollama 服務響應異常: {response.status_code}',
                    'server_url': config.OLLAMA_URL,
                    'timestamp': datetime.now().isoformat()
                }), 503

        except Exception as e:
            return jsonify({
                'status': 'disconnected',
                'message': f'無法連接到 Ollama 服務: {str(e)}',
                'server_url': config.OLLAMA_URL,
                'timestamp': datetime.now().isoformat()
            }), 503


# 主要應用程式實例
app = create_app()

if __name__ == '__main__':
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )
