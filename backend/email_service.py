#!/usr/bin/env python3
"""
Email 服務模組
用於發送處理結果和通知
"""

import smtplib
import logging
import csv
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional, List, Dict, Any
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailService:
    """Email 服務類"""
    
    def __init__(self):
        from config import config
        from network_manager import network_manager
        
        self.app_config = config
        self.network_manager = network_manager
        self.enabled = self._is_service_enabled()
        
        if self.enabled:
            logger.info("📧 Email 服務已啟用")
        else:
            logger.info("📧 Email 服務已禁用")
    
    def _is_service_enabled(self) -> bool:
        """檢查Email服務是否可用"""
        # 必須同時滿足：網路模式啟用、Email啟用、有網路連接、有完整配置
        return (
            self.app_config.NETWORK_MODE_ENABLED and 
            self.app_config.EMAIL_ENABLED and
            self.network_manager.check_internet_connection() and
            bool(self.app_config.EMAIL_USERNAME) and
            bool(self.app_config.EMAIL_PASSWORD) and
            bool(self.app_config.EMAIL_TO_ADDRESS)
        )
    
    def is_enabled(self) -> bool:
        """檢查 Email 服務是否啟用"""
        return self._is_service_enabled()
    
    def send_processing_result(self, 
                             to_email: str, 
                             task_id: str, 
                             filename: str, 
                             result: Dict[str, Any],
                             processing_config: Dict[str, Any] = None,
                             attachments: Optional[List[str]] = None) -> bool:
        """發送處理結果"""
        if not self.is_enabled():
            logger.warning("Email 服務未啟用或配置不完整")
            return False
        
        try:
            # 創建郵件
            msg = MIMEMultipart()
            msg['From'] = f"{self.app_config.EMAIL_FROM_NAME} <{self.app_config.EMAIL_USERNAME}>"
            msg['To'] = to_email
            msg['Subject'] = f"語音處理完成 - {filename}"
            
            # 創建郵件內容
            body = self._create_result_email_body(task_id, filename, result, processing_config or {})
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            # 創建文字檔附件
            text_attachments = self._create_text_attachments(task_id, filename, result, processing_config or {})
            for attachment_info in text_attachments:
                self._add_text_attachment(msg, attachment_info['filename'], attachment_info['content'])

            # 創建 CSV 摘要附件
            csv_attachment = self._create_csv_attachment(task_id, filename, result, processing_config or {})
            if csv_attachment:
                self._add_text_attachment(msg, csv_attachment['filename'], csv_attachment['content'])

            # 添加附件
            if attachments:
                for attachment_path in attachments:
                    if os.path.exists(attachment_path):
                        self._add_attachment(msg, attachment_path)
            
            # 發送郵件
            return self._send_email(msg, to_email)
            
        except Exception as e:
            logger.error(f"發送處理結果郵件失敗: {e}")
            return False
    
    def send_notification(self, 
                         to_email: str, 
                         subject: str, 
                         message: str,
                         attachments: Optional[List[str]] = None) -> bool:
        """發送通知郵件"""
        if not self.is_enabled():
            logger.warning("Email 服務未啟用或配置不完整")
            return False
        
        try:
            # 創建郵件
            msg = MIMEMultipart()
            msg['From'] = f"{self.app_config.EMAIL_FROM_NAME} <{self.app_config.EMAIL_USERNAME}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # 創建郵件內容
            msg.attach(MIMEText(message, 'html', 'utf-8'))
            
            # 添加附件
            if attachments:
                for attachment_path in attachments:
                    if os.path.exists(attachment_path):
                        self._add_attachment(msg, attachment_path)
            
            # 發送郵件
            return self._send_email(msg, to_email)
            
        except Exception as e:
            logger.error(f"發送通知郵件失敗: {e}")
            return False
    
    def send_error_notification(self,
                               to_email: str,
                               task_id: str,
                               filename: str,
                               error_message: str,
                               processing_config: Dict[str, Any] = None) -> bool:
        """發送錯誤通知郵件"""
        if not self.is_enabled():
            logger.warning("Email 服務未啟用或配置不完整")
            return False

        try:
            # 創建郵件
            msg = MIMEMultipart()
            msg['From'] = f"{self.app_config.EMAIL_FROM_NAME} <{self.app_config.EMAIL_USERNAME}>"
            msg['To'] = to_email
            msg['Subject'] = f"處理失敗通知 - {filename}"

            # 創建郵件內容
            body = self._create_error_email_body(task_id, filename, error_message, processing_config or {})
            msg.attach(MIMEText(body, 'html', 'utf-8'))

            # 發送郵件
            return self._send_email(msg, to_email)

        except Exception as e:
            logger.error(f"發送錯誤通知郵件失敗: {e}")
            return False

    def send_batch_processing_result(self,
                                     to_email: str,
                                     task_id: str,
                                     batch_result: Dict[str, Any],
                                     processing_config: Dict[str, Any] = None) -> bool:
        """發送批次處理結果郵件"""
        if not self.is_enabled():
            logger.warning("Email 服務未啟用或配置不完整")
            return False

        try:
            batch_info = batch_result.get('batch_info', {})
            files = batch_result.get('files', [])

            # 創建郵件
            msg = MIMEMultipart()
            msg['From'] = f"{self.app_config.EMAIL_FROM_NAME} <{self.app_config.EMAIL_USERNAME}>"
            msg['To'] = to_email
            msg['Subject'] = f"批次處理完成 - {batch_info.get('total_files', 0)} 個檔案"

            # 創建郵件內容
            body = self._create_batch_email_body(task_id, batch_result, processing_config or {})
            msg.attach(MIMEText(body, 'html', 'utf-8'))

            # 為每個檔案創建文字附件
            for i, file_result in enumerate(files):
                if 'error' not in file_result:
                    filename = file_result.get('filename', f'file_{i+1}')
                    transcription = file_result.get('transcription', '')
                    ai_summary = file_result.get('ai_summary', '')
                    # 創建文字內容
                    content = f"""
{'=' * 60}
RosettaBox 語音處理結果 - {filename}
{'=' * 60}

檔案: {filename}
處理時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
任務 ID: {task_id}

{'=' * 60}
語音識別結果
{'=' * 60}

{transcription}

"""
                    if ai_summary:
                        content += f"""
{'=' * 60}
AI 智能摘要
{'=' * 60}

{ai_summary}

"""

                    content += f"""
{'=' * 60}
此文件由 RosettaBox 語音處理系統自動生成
{'=' * 60}
"""

                    # 添加為附件
                    safe_filename = filename.rsplit('_', 1)[-1] if '_' in filename else filename
                    attachment_name = f"{i+1}_{safe_filename.replace('.', '_')}.txt"
                    self._add_text_attachment(msg, attachment_name, content)

            # 發送郵件
            return self._send_email(msg, to_email)

        except Exception as e:
            logger.error(f"發送批次處理結果郵件失敗: {e}")
            return False
    
    def _create_error_email_body(self, task_id: str, filename: str, error_message: str, processing_config: Dict[str, Any]) -> str:
        """創建錯誤通知郵件內容 - 簡潔專業風格"""
        processing_mode = processing_config.get('processing_mode', 'default')
        detail_level = processing_config.get('detail_level', 'normal')

        mode_names = {
            'meeting': '會議記錄',
            'lecture': '講座筆記',
            'default': '通用模式',
            'interview': '訪談整理',
            'custom': '自定義模式'
        }

        detail_names = {
            'simple': '簡潔摘要',
            'normal': '標準詳細',
            'detailed': '完整詳細',
            'custom': '自定義詳細'
        }

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>處理失敗通知 - RosettaBox</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #f1f5f9;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="padding: 40px 20px;">
                <tr>
                    <td align="center">
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width: 600px; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); overflow: hidden;">
                            <!-- Header -->
                            <tr>
                                <td style="background: #1e293b; padding: 32px 40px; text-align: center;">
                                    <p style="margin: 0 0 8px 0; font-size: 14px; color: #ef4444; font-weight: 600; letter-spacing: 0.5px;">處理失敗</p>
                                    <h1 style="margin: 0; font-size: 20px; font-weight: 600; color: #ffffff;">{filename}</h1>
                                </td>
                            </tr>

                            <!-- Error message -->
                            <tr>
                                <td style="padding: 32px 40px 24px;">
                                    <div style="background: #fef2f2; border-left: 4px solid #ef4444; padding: 16px 20px; border-radius: 0 8px 8px 0;">
                                        <p style="margin: 0 0 8px 0; font-size: 12px; font-weight: 600; color: #991b1b; text-transform: uppercase; letter-spacing: 0.5px;">錯誤訊息</p>
                                        <p style="margin: 0; font-size: 14px; color: #7f1d1d; font-family: monospace; line-height: 1.6; white-space: pre-wrap;">{error_message}</p>
                                    </div>
                                </td>
                            </tr>

                            <!-- Info grid -->
                            <tr>
                                <td style="padding: 0 40px 24px;">
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                        <tr>
                                            <td width="48%" style="background: #f8fafc; border-radius: 8px; padding: 14px 16px;">
                                                <p style="margin: 0 0 4px 0; font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 600;">處理模式</p>
                                                <p style="margin: 0; font-size: 14px; color: #1e293b; font-weight: 500;">{mode_names.get(processing_mode, processing_mode)}</p>
                                            </td>
                                            <td width="4%"></td>
                                            <td width="48%" style="background: #f8fafc; border-radius: 8px; padding: 14px 16px;">
                                                <p style="margin: 0 0 4px 0; font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 600;">發生時間</p>
                                                <p style="margin: 0; font-size: 14px; color: #1e293b; font-weight: 500;">{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>

                            <!-- Suggestions -->
                            <tr>
                                <td style="padding: 0 40px 32px;">
                                    <p style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; color: #1e293b;">解決建議</p>
                                    <ul style="margin: 0; padding-left: 20px; color: #475569; font-size: 13px; line-height: 1.8;">
                                        <li>檢查檔案格式是否受支援（mp3, wav, m4a, flac 等）</li>
                                        <li>確認檔案大小不超過限制</li>
                                        <li>檢查檔案是否完整且未損壞</li>
                                        <li>稍後再次嘗試上傳和處理</li>
                                    </ul>
                                </td>
                            </tr>

                            <!-- Footer -->
                            <tr>
                                <td style="background: #f8fafc; padding: 20px 40px; text-align: center; border-top: 1px solid #e2e8f0;">
                                    <p style="margin: 0; font-size: 12px; color: #64748b;">RosettaBox 語音處理系統 · 任務 ID: {task_id[:8]}</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        return html_body
    
    def _create_result_email_body(self, task_id: str, filename: str, result: Dict[str, Any], processing_config: Dict[str, Any]) -> str:
        """創建處理結果郵件內容 - 簡潔專業風格"""
        processing_mode = result.get('processing_mode', 'default')
        detail_level = result.get('detail_level', 'normal')
        processing_time = result.get('processing_time', 0)

        enable_llm_processing = processing_config.get('enable_llm_processing', True)
        original_text = result.get('original_text', '') or result.get('whisper_result', '')
        organized_text = result.get('organized_text', '') or result.get('ai_summary', '') or result.get('processed_text', '')

        mode_names = {
            'meeting': '會議記錄',
            'lecture': '講座筆記',
            'default': '通用模式',
            'interview': '訪談整理',
            'custom': '自定義模式'
        }

        # 計算附件資訊
        attachments_info = []
        if original_text:
            attachments_info.append(f"語音轉文字結果（{len(original_text)} 字）")
        if enable_llm_processing and organized_text:
            attachments_info.append(f"AI 智能整理（{len(organized_text)} 字）")
        attachments_info.append("摘要結構化資料（CSV）")

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>語音處理完成 - RosettaBox</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #f1f5f9;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="padding: 40px 20px;">
                <tr>
                    <td align="center">
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width: 600px; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); overflow: hidden;">
                            <!-- Header -->
                            <tr>
                                <td style="background: #1e293b; padding: 32px 40px; text-align: center;">
                                    <p style="margin: 0 0 8px 0; font-size: 14px; color: #6366f1; font-weight: 600; letter-spacing: 0.5px;">處理完成</p>
                                    <h1 style="margin: 0; font-size: 20px; font-weight: 600; color: #ffffff;">{filename}</h1>
                                </td>
                            </tr>

                            <!-- Stats -->
                            <tr>
                                <td style="padding: 24px 40px;">
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                        <tr>
                                            <td width="48%" style="background: #f8fafc; border-radius: 8px; padding: 14px 16px;">
                                                <p style="margin: 0 0 4px 0; font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 600;">處理模式</p>
                                                <p style="margin: 0; font-size: 14px; color: #1e293b; font-weight: 500;">{mode_names.get(processing_mode, processing_mode)}</p>
                                            </td>
                                            <td width="4%"></td>
                                            <td width="48%" style="background: #f8fafc; border-radius: 8px; padding: 14px 16px;">
                                                <p style="margin: 0 0 4px 0; font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 600;">處理時間</p>
                                                <p style="margin: 0; font-size: 14px; color: #1e293b; font-weight: 500;">{processing_time:.1f} 秒</p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>

                            <!-- Attachments list -->
                            <tr>
                                <td style="padding: 0 40px 20px;">
                                    <div style="border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
                                        <div style="background: #f8fafc; padding: 12px 16px; border-bottom: 1px solid #e2e8f0;">
                                            <p style="margin: 0; font-size: 13px; font-weight: 600; color: #1e293b;">📎 附件內容</p>
                                        </div>
                                        <div style="padding: 16px;">
                                            <ul style="margin: 0; padding-left: 20px; color: #475569; font-size: 13px; line-height: 1.8;">
                                                {''.join(f'<li>{info}</li>' for info in attachments_info)}
                                            </ul>
                                        </div>
                                    </div>
                                </td>
                            </tr>

                            <!-- Attachment notice -->
                            <tr>
                                <td style="padding: 8px 40px 24px;">
                                    <div style="background: #1e293b; border-radius: 8px; padding: 14px; text-align: center;">
                                        <p style="margin: 0; font-size: 13px; color: #ffffff;">請下載附件查看完整內容</p>
                                    </div>
                                </td>
                            </tr>

                            <!-- Footer -->
                            <tr>
                                <td style="background: #f8fafc; padding: 20px 40px; text-align: center; border-top: 1px solid #e2e8f0;">
                                    <p style="margin: 0; font-size: 12px; color: #64748b;">RosettaBox 語音處理系統 · 任務 ID: {task_id[:8]}</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        return html_body
    
    def _create_batch_email_body(self, task_id: str, batch_result: Dict[str, Any], processing_config: Dict[str, Any]) -> str:
        """創建批次處理結果郵件內容 - 簡潔專業風格"""
        batch_info = batch_result.get('batch_info', {})
        files = batch_result.get('files', [])

        total_files = batch_info.get('total_files', 0)
        successful_files = batch_info.get('successful_files', 0)
        failed_files = batch_info.get('failed_files', 0)
        total_processing_time = batch_info.get('total_processing_time', 0) or batch_result.get('processing_time', 0)

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>批次處理完成 - RosettaBox</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #f1f5f9;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="padding: 40px 20px;">
                <tr>
                    <td align="center">
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width: 600px; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); overflow: hidden;">
                            <!-- Header -->
                            <tr>
                                <td style="background: #1e293b; padding: 32px 40px; text-align: center;">
                                    <p style="margin: 0 0 8px 0; font-size: 14px; color: #6366f1; font-weight: 600; letter-spacing: 0.5px;">批次處理完成</p>
                                    <h1 style="margin: 0; font-size: 20px; font-weight: 600; color: #ffffff;">{total_files} 個檔案已處理</h1>
                                </td>
                            </tr>

                            <!-- Summary stats -->
                            <tr>
                                <td style="padding: 24px 40px;">
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                        <tr>
                                            <td width="31%" style="background: #f8fafc; border-radius: 8px; padding: 16px; text-align: center;">
                                                <p style="margin: 0 0 4px 0; font-size: 24px; font-weight: 700; color: #64748b;">{total_files}</p>
                                                <p style="margin: 0; font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">總計</p>
                                            </td>
                                            <td width="3%"></td>
                                            <td width="31%" style="background: #f8fafc; border-radius: 8px; padding: 16px; text-align: center;">
                                                <p style="margin: 0 0 4px 0; font-size: 24px; font-weight: 700; color: #10b981;">{successful_files}</p>
                                                <p style="margin: 0; font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">成功</p>
                                            </td>
                                            <td width="3%"></td>
                                            <td width="31%" style="background: #f8fafc; border-radius: 8px; padding: 16px; text-align: center;">
                                                <p style="margin: 0 0 4px 0; font-size: 24px; font-weight: 700; color: #ef4444;">{failed_files}</p>
                                                <p style="margin: 0; font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">失敗</p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>

                            <!-- Processing time -->
                            <tr>
                                <td style="padding: 0 40px 16px;">
                                    <div style="background: #f0f9ff; border-radius: 8px; padding: 12px 16px; text-align: center;">
                                        <p style="margin: 0; font-size: 13px; color: #0369a1;">總處理時間: <strong>{total_processing_time:.1f} 秒</strong></p>
                                    </div>
                                </td>
                            </tr>

                            <!-- Section title -->
                            <tr>
                                <td style="padding: 0 40px 12px;">
                                    <p style="margin: 0; font-size: 14px; font-weight: 600; color: #1e293b;">檔案詳情</p>
                                </td>
                            </tr>
        """

        # 為每個檔案添加簡要狀態
        for i, file_result in enumerate(files):
            filename = file_result.get('filename', f'檔案 {i+1}')
            has_error = 'error' in file_result

            if has_error:
                error_msg = file_result.get('error', '未知錯誤')
                html_body += f"""
                            <tr>
                                <td style="padding: 0 40px 12px;">
                                    <div style="border: 1px solid #fecaca; border-radius: 8px; overflow: hidden;">
                                        <div style="background: #fef2f2; padding: 12px 16px;">
                                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                                <tr>
                                                    <td><p style="margin: 0; font-size: 13px; font-weight: 600; color: #1e293b;">{i+1}. {filename}</p></td>
                                                    <td align="right"><span style="color: #ef4444; font-size: 12px; font-weight: 600;">失敗</span></td>
                                                </tr>
                                                <tr>
                                                    <td colspan="2"><p style="margin: 8px 0 0 0; font-size: 12px; color: #7f1d1d;">{error_msg}</p></td>
                                                </tr>
                                            </table>
                                        </div>
                                    </div>
                                </td>
                            </tr>
                """
            else:
                transcription = file_result.get('transcription', '')
                ai_summary = file_result.get('ai_summary', '')
                # 只顯示字數統計，不顯示內容
                info_parts = [f"轉錄 {len(transcription)} 字"]
                if ai_summary:
                    info_parts.append(f"AI 整理 {len(ai_summary)} 字")

                html_body += f"""
                            <tr>
                                <td style="padding: 0 40px 12px;">
                                    <div style="border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
                                        <div style="background: #f8fafc; padding: 12px 16px;">
                                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                                <tr>
                                                    <td><p style="margin: 0; font-size: 13px; font-weight: 600; color: #1e293b;">{i+1}. {filename}</p></td>
                                                    <td align="right"><span style="color: #10b981; font-size: 12px; font-weight: 600;">成功</span></td>
                                                </tr>
                                                <tr>
                                                    <td colspan="2"><p style="margin: 8px 0 0 0; font-size: 12px; color: #64748b;">{' · '.join(info_parts)}</p></td>
                                                </tr>
                                            </table>
                                        </div>
                                    </div>
                                </td>
                            </tr>
                """

        html_body += f"""
                            <!-- Attachment notice -->
                            <tr>
                                <td style="padding: 12px 40px 24px;">
                                    <div style="background: #1e293b; border-radius: 8px; padding: 14px; text-align: center;">
                                        <p style="margin: 0; font-size: 13px; color: #ffffff;">請下載附件查看完整內容（每個檔案獨立一份 .txt）</p>
                                    </div>
                                </td>
                            </tr>

                            <!-- Footer -->
                            <tr>
                                <td style="background: #f8fafc; padding: 20px 40px; text-align: center; border-top: 1px solid #e2e8f0;">
                                    <p style="margin: 0; font-size: 12px; color: #64748b;">RosettaBox 語音處理系統 · 任務 ID: {task_id[:8]}</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        return html_body

    def _create_text_attachments(self, task_id: str, filename: str, result: Dict[str, Any], processing_config: Dict[str, Any]) -> List[Dict[str, str]]:
        """創建文字檔附件"""
        attachments = []
        
        # 檢查用戶勾選的功能
        enable_llm_processing = processing_config.get('enable_llm_processing', True)
        
        # 獲取文字內容
        original_text = result.get('original_text', '') or result.get('whisper_result', '')
        organized_text = result.get('organized_text', '') or result.get('ai_summary', '') or result.get('processed_text', '')
        
        # 基本文件名（移除副檔名）
        base_filename = filename.rsplit('.', 1)[0] if '.' in filename else filename
        
        # 1. 語音轉文字結果（總是包含）
        if original_text:
            content = f"""語音轉文字結果
{'-' * 40}
文件名稱: {filename}
處理模式: {result.get('processing_mode', 'default')}
詳細程度: {result.get('detail_level', 'normal')}
處理時間: {result.get('processing_time', 0):.1f} 秒
任務 ID: {task_id}

{'-' * 40}
原始轉錄內容:
{'-' * 40}

{original_text}

{'-' * 40}
此文件由 RosettaBox 語音處理系統自動生成
生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            attachments.append({
                'filename': f"{base_filename}_語音轉文字.txt",
                'content': content
            })
        
        # 2. AI 智能整理結果（只有勾選時才包含）
        if enable_llm_processing and organized_text:
            content = f"""AI 智能整理結果
{'-' * 40}
文件名稱: {filename}
處理模式: {result.get('processing_mode', 'default')}
詳細程度: {result.get('detail_level', 'normal')}
AI 模型: {result.get('ai_model', '未知')}
處理時間: {result.get('processing_time', 0):.1f} 秒
任務 ID: {task_id}

{'-' * 40}
AI 整理內容:
{'-' * 40}

{organized_text}

{'-' * 40}
此文件由 RosettaBox 語音處理系統自動生成
生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            attachments.append({
                'filename': f"{base_filename}_AI智能整理.txt", 
                'content': content
            })
        
        return attachments

    def _create_csv_attachment(self, task_id: str, filename: str, result: Dict[str, Any], processing_config: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """創建 CSV 摘要附件（元資料 + 內容）"""
        try:
            enable_llm_processing = processing_config.get('enable_llm_processing', True)

            original_text = result.get('original_text', '') or result.get('whisper_result', '')
            organized_text = result.get('organized_text', '') or result.get('ai_summary', '') or result.get('processed_text', '')
            processing_mode = result.get('processing_mode', 'default')
            mode_names = {
                'meeting': '會議記錄',
                'lecture': '講座筆記',
                'default': '通用模式',
                'interview': '訪談整理',
                    'custom': '自定義模式'
            }

            # 建立 CSV 內容（使用 BOM 讓 Excel 正確識別 UTF-8）
            output = io.StringIO()
            output.write('\ufeff')  # UTF-8 BOM
            writer = csv.writer(output)

            # 表頭
            writer.writerow([
                '檔名', '處理模式', 'AI模型', '處理時間(秒)',
                '原始字數', '整理字數',
                '原始轉錄', 'AI整理結果'
            ])

            # 資料列
            writer.writerow([
                filename,
                mode_names.get(processing_mode, processing_mode),
                result.get('ai_model', '未使用'),
                f"{result.get('processing_time', 0):.1f}",
                len(original_text),
                len(organized_text) if enable_llm_processing and organized_text else 0,
                original_text,
                organized_text if enable_llm_processing else ''
            ])

            base_filename = filename.rsplit('.', 1)[0] if '.' in filename else filename
            return {
                'filename': f"{base_filename}_摘要.csv",
                'content': output.getvalue()
            }

        except Exception as e:
            logger.error(f"創建 CSV 附件失敗: {e}")
            return None

    def _add_text_attachment(self, msg: MIMEMultipart, filename: str, content: str):
        """添加文字內容為可下載附件（支援中文檔名）"""
        try:
            from email.header import Header
            from urllib.parse import quote

            # 使用 MIMEBase 而非 MIMEText，確保作為下載附件而非內聯顯示
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(content.encode('utf-8'))
            encoders.encode_base64(part)

            # 使用 RFC 2231 編碼處理中文檔名
            # 同時提供 filename（ASCII fallback）和 filename*（UTF-8 編碼）
            encoded_filename = quote(filename, safe='')
            part.add_header(
                'Content-Disposition',
                'attachment',
                filename=('utf-8', '', filename)  # RFC 2231 格式
            )

            msg.attach(part)

            logger.info(f"已添加文字附件: {filename}")

        except Exception as e:
            logger.error(f"添加文字附件失敗 {filename}: {e}")
    
    def _add_attachment(self, msg: MIMEMultipart, file_path: str):
        """添加附件（支援中文檔名）"""
        try:
            filename = os.path.basename(file_path)

            with open(file_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())

            encoders.encode_base64(part)
            # 使用 RFC 2231 編碼處理中文檔名
            part.add_header(
                'Content-Disposition',
                'attachment',
                filename=('utf-8', '', filename)  # RFC 2231 格式
            )
            msg.attach(part)
            logger.info(f"已添加附件: {file_path}")
        except Exception as e:
            logger.error(f"添加附件失敗 {file_path}: {e}")
    
    def _send_email(self, msg: MIMEMultipart, to_email: str, timeout: int = 30) -> bool:
        """
        發送郵件（帶超時設置）

        Args:
            msg: 郵件內容
            to_email: 收件人地址
            timeout: SMTP 連接超時秒數（預設 30 秒）
        """
        if not self.is_enabled():
            logger.warning("Email服務未啟用或配置不完整，無法發送郵件")
            return False

        try:
            # 連接 SMTP 服務器（帶超時設置，防止無限阻塞導致 524 錯誤）
            server = smtplib.SMTP(
                self.app_config.EMAIL_SMTP_SERVER,
                self.app_config.EMAIL_SMTP_PORT,
                timeout=timeout
            )
            server.starttls()  # 啟用 TLS 加密

            # 登入
            server.login(self.app_config.EMAIL_USERNAME, self.app_config.EMAIL_PASSWORD)

            # 發送郵件
            text = msg.as_string()
            server.sendmail(self.app_config.EMAIL_USERNAME, to_email, text)
            server.quit()

            logger.info(f"郵件發送成功: {to_email}")
            return True

        except smtplib.SMTPException as e:
            logger.error(f"SMTP 發送郵件失敗: {e}")
            return False
        except TimeoutError as e:
            logger.error(f"SMTP 連接超時 ({timeout}s): {e}")
            return False
        except OSError as e:
            # socket.timeout 在某些情況下會是 OSError
            if "timed out" in str(e).lower():
                logger.error(f"SMTP 連接超時 ({timeout}s): {e}")
            else:
                logger.error(f"SMTP 網路錯誤: {e}")
            return False
        except Exception as e:
            logger.error(f"發送郵件失敗: {e}")
            return False
    
    def test_connection(self, timeout: int = 30) -> bool:
        """
        測試 Email 連接（帶超時設置）

        Args:
            timeout: SMTP 連接超時秒數（預設 30 秒）
        """
        if not self.is_enabled():
            return False

        try:
            server = smtplib.SMTP(
                self.app_config.EMAIL_SMTP_SERVER,
                self.app_config.EMAIL_SMTP_PORT,
                timeout=timeout
            )
            server.starttls()
            server.login(self.app_config.EMAIL_USERNAME, self.app_config.EMAIL_PASSWORD)
            server.quit()

            logger.info("Email 連接測試成功")
            return True

        except TimeoutError as e:
            logger.error(f"Email 連接測試超時 ({timeout}s): {e}")
            return False
        except OSError as e:
            if "timed out" in str(e).lower():
                logger.error(f"Email 連接測試超時 ({timeout}s): {e}")
            else:
                logger.error(f"Email 連接測試網路錯誤: {e}")
            return False
        except Exception as e:
            logger.error(f"Email 連接測試失敗: {e}")
            return False

# 全局 Email 服務實例 - 延遲初始化
email_service = None

def get_email_service():
    """獲取 Email 服務實例（延遲初始化）"""
    global email_service
    if email_service is None:
        email_service = EmailService()
    return email_service

def send_processing_result(to_email: str, task_id: str, filename: str, result: Dict[str, Any], processing_config: Dict[str, Any] = None, attachments: Optional[List[str]] = None) -> bool:
    """發送處理結果郵件"""
    return get_email_service().send_processing_result(to_email, task_id, filename, result, processing_config, attachments)

def send_batch_processing_result(to_email: str, task_id: str, batch_result: Dict[str, Any], processing_config: Dict[str, Any] = None) -> bool:
    """發送批次處理結果郵件"""
    return get_email_service().send_batch_processing_result(to_email, task_id, batch_result, processing_config)

def send_notification(to_email: str, subject: str, message: str, attachments: Optional[List[str]] = None) -> bool:
    """發送通知郵件"""
    return get_email_service().send_notification(to_email, subject, message, attachments)

def send_error_notification(to_email: str, task_id: str, filename: str, error_message: str, processing_config: Dict[str, Any] = None) -> bool:
    """發送錯誤通知郵件"""
    return get_email_service().send_error_notification(to_email, task_id, filename, error_message, processing_config)

def is_email_enabled() -> bool:
    """檢查 Email 功能是否啟用"""
    return get_email_service().is_enabled()

def test_email_connection() -> bool:
    """測試 Email 連接"""
    return get_email_service().test_connection()

if __name__ == "__main__":
    # 測試 Email 服務
    print("📧 Email 服務測試")
    print("=" * 30)
    
    if is_email_enabled():
        print("✅ Email 服務已啟用")
        
        if test_email_connection():
            print("✅ Email 連接測試成功")
        else:
            print("❌ Email 連接測試失敗")
    else:
        print("❌ Email 服務未啟用或配置不完整")








