import logging
from datetime import datetime
import os
import sys
from utils.timezone_utils import format_taipei_time

# 添加父目錄到 Python 路徑，以便導入 email_service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from email_service import email_service
except ImportError:
    email_service = None

logger = logging.getLogger(__name__)

class FeedbackService:
    def __init__(self):
        self.recipient_email = 'leopilot101@gmail.com'
        self.email_service = email_service
        
    def send_feedback(self, feedback_data):
        try:
            # 創建郵件內容
            subject = self._create_subject(feedback_data)
            body = self._create_body(feedback_data)
            
            # 使用現有的郵件服務
            if self.email_service and self.email_service.is_enabled():
                success = self.email_service.send_notification(
                    to_email=self.recipient_email,
                    subject=subject,
                    message=body
                )
                
                if success:
                    logger.info("回饋郵件發送成功")
                    return {
                        'success': True,
                        'message': '回饋已成功發送'
                    }
                else:
                    logger.error("郵件發送失敗")
                    return self._log_feedback(feedback_data, subject, body)
            else:
                # 如果郵件服務未啟用，記錄到日誌
                logger.warning("郵件服務未啟用，將記錄到日誌")
                return self._log_feedback(feedback_data, subject, body)
                
        except Exception as e:
            logger.error(f"發送回饋郵件失敗: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    
    def _log_feedback(self, feedback_data, subject, body):
        try:
            # 如果沒有配置SMTP，將回饋記錄到日誌文件
            log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            log_file = os.path.join(log_dir, 'feedback.log')
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"時間: {format_taipei_time()}\n")
                f.write(f"主題: {subject}\n")
                f.write(f"內容:\n{body}\n")
                f.write(f"{'='*50}\n")
            
            logger.info(f"回饋已記錄到日誌文件: {log_file}")
            return {
                'success': True,
                'message': '回饋已記錄（郵件服務未配置）'
            }
            
        except Exception as e:
            logger.error(f"記錄回饋失敗: {str(e)}")
            return {
                'success': False,
                'error': f"記錄回饋失敗: {str(e)}"
            }
    
    def _create_subject(self, feedback_data):
        type_map = {
            'bug': '故障回報',
            'suggestion': '功能建議',
            'improvement': '改進建議',
            'other': '其他回饋'
        }
        
        feedback_type = type_map.get(feedback_data['type'], '回饋')
        subject = feedback_data.get('subject', '')
        
        if subject:
            return f"[語音文字處理器] {feedback_type}: {subject}"
        else:
            return f"[語音文字處理器] {feedback_type}"
    
    def _create_body(self, feedback_data):
        timestamp = format_taipei_time()
        
        type_map = {
            'bug': '故障回報',
            'suggestion': '功能建議', 
            'improvement': '改進建議',
            'other': '其他回饋'
        }
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #2c3e50;">語音文字處理器 - 用戶回饋</h2>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0;">
                <strong>回饋類型:</strong> {type_map.get(feedback_data['type'], '其他')}<br>
                <strong>提交時間:</strong> {timestamp}<br>
                {f"<strong>主題:</strong> {feedback_data.get('subject', 'N/A')}<br>" if feedback_data.get('subject') else ""}
                {f"<strong>用戶Email:</strong> {feedback_data.get('user_email', 'N/A')}<br>" if feedback_data.get('user_email') else ""}
            </div>
            
            <div style="margin: 20px 0;">
                <h3 style="color: #2c3e50;">詳細內容:</h3>
                <div style="background-color: #ffffff; padding: 15px; border: 1px solid #dee2e6; white-space: pre-wrap;">
{feedback_data['message']}
                </div>
            </div>
            
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #dee2e6;">
            
            <p style="color: #6c757d; font-size: 12px;">
                此郵件由語音文字處理器系統自動發送<br>
                時間: {timestamp}
            </p>
        </body>
        </html>
        """
        
        return body