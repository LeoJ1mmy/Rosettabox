"""
路由管理器 - 統一管理所有路由和依賴注入
"""
import logging
from flask import Flask, jsonify
from typing import Dict, Any, Optional
import traceback

logger = logging.getLogger(__name__)

class RouteManager:
    """統一路由管理器"""
    
    def __init__(self):
        self.blueprints = {}
        self.dependencies = {}
        self.error_handlers = {}
        self.middleware = []
        
    def register_dependency(self, name: str, instance: Any):
        """註冊依賴"""
        self.dependencies[name] = instance
        logger.info(f"✅ 依賴已註冊: {name}")
        
    def get_dependency(self, name: str) -> Optional[Any]:
        """獲取依賴"""
        return self.dependencies.get(name)
        
    def register_blueprint_safely(self, app: Flask, blueprint, url_prefix: str = None):
        """安全註冊 Blueprint"""
        try:
            # 注入依賴到 Blueprint
            if hasattr(blueprint, 'inject_dependencies'):
                blueprint.inject_dependencies(self.dependencies)
                
            # 註冊 Blueprint
            if url_prefix:
                app.register_blueprint(blueprint, url_prefix=url_prefix)
            else:
                app.register_blueprint(blueprint)
                
            self.blueprints[blueprint.name] = blueprint
            logger.info(f"✅ Blueprint 已註冊: {blueprint.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Blueprint 註冊失敗 {blueprint.name}: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
            
    def register_error_handlers(self, app: Flask):
        """註冊統一錯誤處理器"""
        
        @app.errorhandler(400)
        def handle_bad_request(error):
            return jsonify({
                'error': '請求格式錯誤',
                'code': 'BAD_REQUEST',
                'details': str(error)
            }), 400
            
        @app.errorhandler(401)
        def handle_unauthorized(error):
            return jsonify({
                'error': '未授權訪問',
                'code': 'UNAUTHORIZED'
            }), 401
            
        @app.errorhandler(403)
        def handle_forbidden(error):
            return jsonify({
                'error': '禁止訪問',
                'code': 'FORBIDDEN'
            }), 403
            
        @app.errorhandler(404)
        def handle_not_found(error):
            return jsonify({
                'error': '接口不存在',
                'code': 'NOT_FOUND'
            }), 404
            
        @app.errorhandler(413)
        def handle_file_too_large(error):
            from config import config
            max_mb = config.MAX_CONTENT_LENGTH // (1024*1024)
            return jsonify({
                'error': f'文件過大！最大允許上傳 {max_mb}MB',
                'code': 'FILE_TOO_LARGE',
                'max_size_mb': max_mb
            }), 413
            
        @app.errorhandler(500)
        def handle_internal_error(error):
            logger.error(f"內部服務器錯誤: {str(error)}")
            return jsonify({
                'error': '內部服務器錯誤',
                'code': 'INTERNAL_ERROR'
            }), 500
            
        @app.errorhandler(503)
        def handle_service_unavailable(error):
            return jsonify({
                'error': '服務暫時不可用',
                'code': 'SERVICE_UNAVAILABLE'
            }), 503
            
        logger.info("✅ 統一錯誤處理器已註冊")
        
    def register_middleware(self, app: Flask):
        """註冊中間件"""
        
        @app.before_request
        def log_request():
            from flask import request
            if not request.path.startswith('/static'):
                logger.debug(f"{request.method} {request.path}")
                
        @app.after_request
        def add_security_headers(response):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            return response
            
        @app.teardown_appcontext
        def cleanup_context(error):
            if error:
                logger.error(f"應用上下文錯誤: {str(error)}")
                
        logger.info("✅ 中間件已註冊")
        
    def health_check(self) -> Dict[str, Any]:
        """系統健康檢查"""
        health_status = {
            'status': 'healthy',
            'blueprints': {},
            'dependencies': {},
            'errors': []
        }
        
        # 檢查 Blueprints
        for name, blueprint in self.blueprints.items():
            try:
                health_status['blueprints'][name] = 'ok'
            except Exception as e:
                health_status['blueprints'][name] = f'error: {str(e)}'
                health_status['errors'].append(f'Blueprint {name}: {str(e)}')
                
        # 檢查依賴
        for name, dependency in self.dependencies.items():
            try:
                if hasattr(dependency, 'health_check'):
                    health_status['dependencies'][name] = dependency.health_check()
                else:
                    health_status['dependencies'][name] = 'ok'
            except Exception as e:
                health_status['dependencies'][name] = f'error: {str(e)}'
                health_status['errors'].append(f'Dependency {name}: {str(e)}')
                
        # 如果有錯誤，整體狀態為不健康
        if health_status['errors']:
            health_status['status'] = 'unhealthy'
            
        return health_status

# 全局路由管理器實例
route_manager = RouteManager()