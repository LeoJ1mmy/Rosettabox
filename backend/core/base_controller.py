"""
基礎控制器 - 所有控制器的父類
"""
import logging
from flask import Blueprint, jsonify, request
from typing import Dict, Any, Optional
import traceback

logger = logging.getLogger(__name__)

class BaseController:
    """基礎控制器類"""
    
    def __init__(self, name: str, url_prefix: str = None):
        self.name = name
        self.blueprint = Blueprint(name, __name__, url_prefix=url_prefix)
        self.dependencies = {}
        
    def inject_dependencies(self, dependencies: Dict[str, Any]):
        """注入依賴"""
        self.dependencies = dependencies
        logger.debug(f"依賴已注入到 {self.name}: {list(dependencies.keys())}")
        
    def get_dependency(self, name: str) -> Optional[Any]:
        """獲取依賴"""
        dependency = self.dependencies.get(name)
        if dependency is None:
            logger.warning(f"依賴 {name} 未找到在 {self.name} 中")
        return dependency
        
    def safe_execute(self, func, *args, **kwargs):
        """安全執行函數，統一錯誤處理"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"控制器 {self.name} 執行失敗: {str(e)}")
            logger.debug(traceback.format_exc())
            return jsonify({'error': str(e)}), 500
            
    def validate_user_id(self, required: bool = True) -> Optional[str]:
        """驗證用戶ID"""
        user_id = None
        
        # 從表單或JSON中獲取用戶ID
        if request.method == 'POST':
            if request.is_json:
                user_id = request.json.get('user_id') if request.json else None
            else:
                user_id = request.form.get('user_id')
        else:
            user_id = request.args.get('user_id')
            
        if required and not user_id:
            raise ValueError('缺少用戶ID')
            
        return user_id
        
    def validate_request_data(self, required_fields: list = None) -> Dict[str, Any]:
        """驗證請求數據"""
        if request.method == 'GET':
            data = dict(request.args)
        elif request.is_json:
            data = request.json or {}
        else:
            data = dict(request.form)
            
        # 檢查必需字段
        if required_fields:
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                raise ValueError(f'缺少必需字段: {", ".join(missing_fields)}')
                
        return data
        
    def create_success_response(self, data: Any = None, message: str = None) -> Dict[str, Any]:
        """創建成功響應"""
        response = {'status': 'success'}
        if data is not None:
            response['data'] = data
        if message:
            response['message'] = message
        return response
        
    def create_error_response(self, message: str, code: str = None, status_code: int = 400):
        """創建錯誤響應"""
        response = {
            'status': 'error',
            'message': message
        }
        if code:
            response['code'] = code
        return jsonify(response), status_code
        
    def register_routes(self):
        """註冊路由 - 子類需要實現"""
        raise NotImplementedError("子類必須實現 register_routes 方法")
        
    def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        return {
            'controller': self.name,
            'status': 'healthy',
            'dependencies': {
                name: 'available' if dep else 'unavailable' 
                for name, dep in self.dependencies.items()
            }
        }