"""
統一 API 響應處理模組
提供標準化的響應格式和錯誤處理
"""
from flask import jsonify
from datetime import datetime
import logging
import traceback
from functools import wraps
from typing import Any, Dict, Optional, Union, List

logger = logging.getLogger(__name__)

class APIResponseCode:
    """API 響應代碼常量"""
    SUCCESS = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    
    INTERNAL_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504

class APIResponse:
    """統一 API 響應處理類"""
    
    @staticmethod
    def success(data: Any = None, message: str = "操作成功", 
                code: int = APIResponseCode.SUCCESS, 
                meta: Optional[Dict] = None) -> tuple:
        """
        成功響應
        
        Args:
            data: 響應數據
            message: 響應消息
            code: HTTP 狀態碼
            meta: 元數據信息
            
        Returns:
            tuple: (response_dict, status_code)
        """
        response = {
            'success': True,
            'code': code,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        
        if meta:
            response['meta'] = meta
            
        return jsonify(response), code
    
    @staticmethod
    def error(message: str = "操作失敗", 
              code: int = APIResponseCode.BAD_REQUEST,
              error_code: Optional[str] = None,
              details: Optional[Dict] = None,
              trace_id: Optional[str] = None) -> tuple:
        """
        錯誤響應
        
        Args:
            message: 錯誤消息
            code: HTTP 狀態碼
            error_code: 業務錯誤代碼
            details: 錯誤詳情
            trace_id: 追蹤 ID
            
        Returns:
            tuple: (response_dict, status_code)
        """
        response = {
            'success': False,
            'code': code,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'error': {
                'code': error_code or f'ERR_{code}',
                'message': message
            }
        }
        
        if details:
            response['error']['details'] = details
            
        if trace_id:
            response['trace_id'] = trace_id
            
        logger.error(f"API Error: {code} - {message} - Details: {details}")
        
        return jsonify(response), code
    
    @staticmethod
    def validation_error(errors: Union[str, List, Dict],
                        message: str = "輸入驗證失敗",
                        details: Optional[Dict] = None) -> tuple:
        """
        驗證錯誤響應

        Args:
            errors: 驗證錯誤信息
            message: 錯誤消息
            details: 額外的錯誤詳情（可選）

        Returns:
            tuple: (response_dict, status_code)
        """
        combined_details = {'validation_errors': errors}
        if details:
            combined_details.update(details)
        return APIResponse.error(
            message=message,
            code=APIResponseCode.UNPROCESSABLE_ENTITY,
            error_code='VALIDATION_ERROR',
            details=combined_details
        )
    
    @staticmethod
    def not_found(resource: str = "資源") -> tuple:
        """
        資源不存在響應
        
        Args:
            resource: 資源名稱
            
        Returns:
            tuple: (response_dict, status_code)
        """
        return APIResponse.error(
            message=f"{resource}不存在",
            code=APIResponseCode.NOT_FOUND,
            error_code='RESOURCE_NOT_FOUND'
        )
    
    @staticmethod
    def unauthorized(message: str = "未授權訪問") -> tuple:
        """
        未授權響應
        
        Args:
            message: 錯誤消息
            
        Returns:
            tuple: (response_dict, status_code)
        """
        return APIResponse.error(
            message=message,
            code=APIResponseCode.UNAUTHORIZED,
            error_code='UNAUTHORIZED'
        )
    
    @staticmethod
    def forbidden(message: str = "禁止訪問") -> tuple:
        """
        禁止訪問響應
        
        Args:
            message: 錯誤消息
            
        Returns:
            tuple: (response_dict, status_code)
        """
        return APIResponse.error(
            message=message,
            code=APIResponseCode.FORBIDDEN,
            error_code='FORBIDDEN'
        )
    
    @staticmethod
    def internal_error(message: str = "內部服務器錯誤", 
                      details: Optional[Dict] = None) -> tuple:
        """
        內部服務器錯誤響應
        
        Args:
            message: 錯誤消息
            details: 錯誤詳情
            
        Returns:
            tuple: (response_dict, status_code)
        """
        return APIResponse.error(
            message=message,
            code=APIResponseCode.INTERNAL_ERROR,
            error_code='INTERNAL_ERROR',
            details=details
        )
    
    @staticmethod
    def service_unavailable(service: str = "服務") -> tuple:
        """
        服務不可用響應
        
        Args:
            service: 服務名稱
            
        Returns:
            tuple: (response_dict, status_code)
        """
        return APIResponse.error(
            message=f"{service}暫時不可用",
            code=APIResponseCode.SERVICE_UNAVAILABLE,
            error_code='SERVICE_UNAVAILABLE'
        )

def api_exception_handler(func):
    """
    API 異常處理裝飾器
    自動捕獲和處理函數中的異常
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            return APIResponse.validation_error(str(e))
        except FileNotFoundError as e:
            return APIResponse.not_found("文件")
        except PermissionError as e:
            return APIResponse.forbidden("權限不足")
        except ConnectionError as e:
            return APIResponse.service_unavailable("外部服務")
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            return APIResponse.internal_error(
                "操作失敗，請稍後重試",
                details={'function': func.__name__, 'error': str(e)} if logger.isEnabledFor(logging.DEBUG) else None
            )
    return wrapper

def validate_request_json(required_fields: List[str] = None, 
                         optional_fields: List[str] = None):
    """
    請求 JSON 驗證裝飾器
    
    Args:
        required_fields: 必需字段列表
        optional_fields: 可選字段列表
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request
            
            if not request.is_json:
                return APIResponse.validation_error("請求必須是 JSON 格式")
            
            data = request.get_json()
            if not data:
                return APIResponse.validation_error("請求體不能為空")
            
            errors = []
            
            # 檢查必需字段
            if required_fields:
                for field in required_fields:
                    if field not in data or data[field] is None:
                        errors.append(f"缺少必需字段: {field}")
                    elif isinstance(data[field], str) and not data[field].strip():
                        errors.append(f"字段不能為空: {field}")
            
            # 檢查未知字段
            if required_fields or optional_fields:
                allowed_fields = set(required_fields or []) | set(optional_fields or [])
                unknown_fields = set(data.keys()) - allowed_fields
                if unknown_fields:
                    errors.append(f"未知字段: {', '.join(unknown_fields)}")
            
            if errors:
                return APIResponse.validation_error(errors)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def validate_file_upload(allowed_extensions: List[str] = None,
                        max_size_mb: int = None):
    """
    文件上傳驗證裝飾器
    
    Args:
        allowed_extensions: 允許的文件擴展名列表
        max_size_mb: 最大文件大小 (MB)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request
            import os
            
            if 'file' not in request.files:
                return APIResponse.validation_error("未找到上傳文件")
            
            file = request.files['file']
            if file.filename == '':
                return APIResponse.validation_error("未選擇文件")
            
            # 檢查文件擴展名
            if allowed_extensions:
                _, ext = os.path.splitext(file.filename.lower())
                ext = ext[1:]  # 移除點號
                if ext not in allowed_extensions:
                    return APIResponse.validation_error(
                        f"不支持的文件類型。允許的類型: {', '.join(allowed_extensions)}"
                    )
            
            # 檢查文件大小
            if max_size_mb:
                file.seek(0, os.SEEK_END)
                size = file.tell()
                file.seek(0)  # 重置文件指針
                
                max_size_bytes = max_size_mb * 1024 * 1024
                if size > max_size_bytes:
                    return APIResponse.validation_error(
                        f"文件過大。最大允許 {max_size_mb}MB，當前文件 {size/(1024*1024):.1f}MB"
                    )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

class RequestValidator:
    """請求驗證器"""
    
    @staticmethod
    def validate_task_id(task_id: str) -> bool:
        """驗證任務 ID 格式"""
        import re
        pattern = r'^[a-zA-Z0-9_-]+$'
        return bool(re.match(pattern, task_id)) and len(task_id) <= 100
    
    @staticmethod
    def validate_user_id(user_id: str) -> bool:
        """驗證用戶 ID 格式"""
        import re
        pattern = r'^[a-zA-Z0-9_-]+$'
        return bool(re.match(pattern, user_id)) and len(user_id) <= 50
    
    @staticmethod
    def validate_model_name(model_name: str) -> bool:
        """驗證模型名稱格式"""
        import re
        pattern = r'^[a-zA-Z0-9._:/-]+$'
        return bool(re.match(pattern, model_name)) and len(model_name) <= 150
    
    @staticmethod
    def validate_processing_mode(mode: str) -> bool:
        """驗證處理模式"""
        valid_modes = ['default', 'auto', 'meeting', 'lecture', 'interview', 'transcribe', 'speaker_alignment', 'custom']
        return mode in valid_modes
    
    @staticmethod
    def validate_detail_level(level: str) -> bool:
        """驗證詳細程度"""
        valid_levels = ['simple', 'normal', 'detailed', 'comprehensive', 'executive', 'custom']
        return level in valid_levels
    
    @staticmethod
    def validate_client_name(client_name: str) -> bool:
        """驗證客戶端名稱格式"""
        import re
        # 允許字母、數字、空格、短橫線和下劃線
        pattern = r'^[a-zA-Z0-9\s_-]+$'
        return (bool(re.match(pattern, client_name)) 
                and len(client_name.strip()) >= 1 
                and len(client_name) <= 100)

def rate_limit(max_requests: int = 60, window_seconds: int = 60):
    """
    簡單的速率限制裝飾器
    
    Args:
        max_requests: 最大請求數
        window_seconds: 時間窗口 (秒)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request
            import time
            
            # 這裡可以實現基於 IP 或用戶的速率限制
            # 簡化版本，實際應用中可以使用 Redis 等
            client_ip = request.remote_addr
            current_time = time.time()
            
            # 實際實現中應該使用持久化存儲
            # 這裡僅作示例
            
            return func(*args, **kwargs)
        return wrapper
    return decorator