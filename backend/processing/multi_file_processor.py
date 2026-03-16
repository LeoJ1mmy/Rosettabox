"""
多檔案批次處理器 - 專門處理多檔案上傳任務
"""
import logging
import os
from typing import Dict, List, Any, Optional

from .task_processor import TaskCancelledException, check_task_cancelled

logger = logging.getLogger(__name__)

def process_multi_file_audio_task(task):
    """處理多檔案音頻批次任務"""
    import time
    task_id = None
    start_time = time.time()  # 記錄處理開始時間
    try:
        # 支援多種 task_id 字段名稱
        task_id = task.get('task_id') or task.get('id') or task.get('taskId')
        if not task_id:
            raise ValueError("任務中未找到 task_id 字段")

        # 🔧 修復：處理前檢查取消狀態
        check_task_cancelled(task_id, "批次處理開始")
            
        # 支持多檔案和單檔案處理
        # 修復：從 task_data 中獲取 files 數組
        task_data = task.get('task_data', {})
        files = task_data.get('files', []) or task.get('files', [])

        if not files:
            # 向後相容：如果沒有 files 字段，嘗試使用單檔案欄位
            filename = task.get('filename') or task.get('file_path') or task.get('filePath')
            if filename:
                files = [{'filename': filename, 'original_name': filename}]
            else:
                raise ValueError("任務中未找到 files 或 filename 字段")
        
        # 優先從 task_data 中獲取配置，其次從 task 根層級獲取
        config_data = task_data.get('processing_config', {}) or task.get('processing_config', {}) or task.get('config', {})
        user_id = task_data.get('user_id') or task.get('user_id')
        
        logger.info(f"📦 處理批次任務: {task_id}, 檔案數量: {len(files)}")
        
        # 動態導入避免循環依賴
        try:
            import app
            config_service = app.get_config_service()
            qm = app.get_queue_manager()
        except:
            config_service = None
            qm = None
        
        # 🆕 初始化批次緩存服務
        try:
            from services.batch_cache_service import batch_cache_service
            
            # 創建批次緩存條目
            batch_cache_service.create_batch_cache(
                batch_id=task_id,
                user_id=user_id,
                total_files=len(files),
                config=config_data
            )
            logger.info(f"🔄 已創建批次緩存: {task_id}")
        except Exception as e:
            logger.warning(f"⚠️ 批次緩存初始化失敗: {e}")
            batch_cache_service = None
        
        if config_service:
            user_config = config_service.get_user_config(user_id)
        else:
            from dataclasses import dataclass
            @dataclass
            class DefaultConfig:
                whisper_model: str = 'base'
                enable_llm_processing: bool = True
                processing_mode: str = 'default'
                detail_level: str = 'normal'
                ai_model: str = 'phi4-mini:3.8b'
                speaker_count_mode: str = 'auto'
                estimated_speakers: int = 2
            user_config = DefaultConfig()
        
        final_config = {
            'whisper_model': config_data.get('whisper_model', user_config.whisper_model),
            'enable_llm': config_data.get('enable_llm', user_config.enable_llm_processing),
            'processing_mode': config_data.get('processing_mode', user_config.processing_mode),
            'detail_level': config_data.get('detail_level', user_config.detail_level),
            'ai_model': config_data.get('ai_model', user_config.ai_model),
            'speaker_count_mode': config_data.get('speaker_count_mode', user_config.speaker_count_mode),
            'estimated_speakers': config_data.get('estimated_speakers', user_config.estimated_speakers),
            'custom_mode_prompt': config_data.get('custom_mode_prompt'),
            'custom_detail_prompt': config_data.get('custom_detail_prompt'),
            'custom_format_template': config_data.get('custom_format_template'),
            'selected_tags': config_data.get('selected_tags', []),
            'custom_prompt': config_data.get('custom_prompt'),  # 🔧 修復：添加 custom_prompt 支持
            'email_enabled': config_data.get('email_enabled', False),
            'email_address': config_data.get('email_address')
        }
        
        if qm:
            qm.update_task_progress(task_id, "🔍 準備批次處理", 5)
        
        # 處理所有檔案
        all_results = []
        total_files = len(files)
        
        for i, file_info in enumerate(files):
            # 🔧 修復：每個檔案處理前檢查取消狀態
            check_task_cancelled(task_id, f"處理檔案 {i+1}/{total_files} 前")

            filename = file_info['filename']
            original_name = file_info.get('original_name', filename)

            logger.info(f"📁 處理檔案 {i+1}/{total_files}: {original_name}")

            if qm:
                progress = int(10 + (i * 75 / total_files))  # 10-85% 為處理進度
                qm.update_task_progress(task_id, f"🎤 處理中 ({i+1}/{total_files}): {original_name}", progress)

            # 處理單個檔案
            try:
                from .task_processor import process_single_audio_file
                single_result = process_single_audio_file(filename, final_config, task_id, original_name)
                single_result['file_info'] = file_info
                all_results.append(single_result)
                
                # 🆕 將完成的檔案結果加入批次緩存
                if batch_cache_service:
                    batch_cache_service.add_file_result(task_id, single_result)
                
                logger.info(f"✅ 檔案處理完成: {original_name}")
            except Exception as e:
                logger.error(f"❌ 檔案處理失敗 {original_name}: {str(e)}")
                error_result = {
                    'filename': original_name,
                    'error': str(e),
                    'transcription': '',
                    'ai_summary': '',
                    'file_info': file_info
                }
                all_results.append(error_result)
                
                # 🆕 將失敗的檔案結果也加入批次緩存
                if batch_cache_service:
                    batch_cache_service.add_file_result(task_id, error_result)
        
        if qm:
            qm.update_task_progress(task_id, "📊 整合結果", 90)

        # 計算總處理時間
        total_processing_time = time.time() - start_time

        # 整合所有結果
        batch_result = {
            'task_id': task_id,
            'batch_info': {
                'total_files': total_files,
                'successful_files': len([r for r in all_results if 'error' not in r]),
                'failed_files': len([r for r in all_results if 'error' in r]),
                'total_processing_time': total_processing_time  # 總處理時間（秒）
            },
            'files': all_results,
            'config': final_config,
            'user_id': user_id,
            'processing_time': total_processing_time  # 兼容單檔案格式
        }
        
        # Email 通知將由 queue_manager 自動處理
        # 不需要在這裡發送，queue_manager._send_completion_notification 會自動檢測批次結果並發送對應的 email
        logger.info(f"📧 批次結果已準備完成，Email 將由隊列管理器自動發送")
        
        # 🔧 修復：完成前再次檢查取消狀態
        check_task_cancelled(task_id, "批次處理完成前")

        if qm:
            qm.update_task_progress(task_id, "✅ 批次處理完成", 100)
            # 🔧 修復：只有在任務未被取消時才標記完成
            if not qm.is_task_cancelled(task_id):
                qm.complete_task(task_id, batch_result)
                logger.info(f"🎉 批次任務完成: {task_id}, 成功: {batch_result['batch_info']['successful_files']}, 失敗: {batch_result['batch_info']['failed_files']}")
            else:
                logger.info(f"🚫 任務 {task_id} 已被取消，跳過完成標記")

        # 清理GPU記憶體
        from .task_processor import cleanup_cuda_memory, unload_ollama_model
        cleanup_cuda_memory()
        unload_ollama_model()

    except TaskCancelledException:
        # 🔧 修復：任務取消是正常流程
        logger.info(f"🚫 批次處理任務 {task_id} 已被取消，正常終止")
        # 清理GPU記憶體
        from .task_processor import cleanup_cuda_memory, unload_ollama_model
        cleanup_cuda_memory()
        unload_ollama_model()
    except Exception as e:
        logger.error(f"❌ 批次任務失敗: {task_id or '未知'} - {str(e)}")

        # 動態導入避免循環依賴
        try:
            import app
            qm = app.get_queue_manager()
        except:
            qm = None

        # 🔧 修復：只有在任務未被取消時才標記失敗
        if qm and task_id and not qm.is_task_cancelled(task_id):
            qm.fail_task(task_id, str(e))

        # 清理GPU記憶體
        from .task_processor import cleanup_cuda_memory, unload_ollama_model
        cleanup_cuda_memory()
        unload_ollama_model()

# Note: Batch email notification is now handled automatically by queue_manager._send_completion_notification()
# The function detects batch results and calls email_service.send_batch_processing_result()
# No need for a separate send_batch_email_notification function here