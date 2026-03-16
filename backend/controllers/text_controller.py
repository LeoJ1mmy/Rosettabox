"""
文字處理控制器 - 處理文字整理相關的 API 請求
"""
from flask import Blueprint, request, jsonify
import logging
from utils.api_response import APIResponse, api_exception_handler, validate_request_json, RequestValidator

# 動態導入避免循環依賴
def get_services():
    """動態獲取服務"""
    try:
        from services.text_service import text_service
        from services.config_service import config_service
        from utils.cache_manager import cache_manager
        return text_service, config_service, cache_manager
    except ImportError as e:
        logger.error(f"服務導入失敗: {e}")
        return None, None, None

def get_queue_manager():
    """動態獲取隊列管理器"""
    try:
        import app
        return getattr(app, 'queue_manager', None)
    except Exception:
        return None

logger = logging.getLogger(__name__)

text_bp = Blueprint('text', __name__, url_prefix='/api/text')

@text_bp.route('/engine/info', methods=['GET'])
@api_exception_handler
def get_engine_info():
    """獲取當前 AI 引擎資訊"""
    text_service, _, _ = get_services()
    if not text_service:
        return APIResponse.server_error("服務初始化失敗")
    
    try:
        info = text_service.get_engine_info()
        return APIResponse.success(info, "獲取引擎資訊成功")
    except Exception as e:
        logger.error(f"獲取引擎資訊失敗: {str(e)}")
        return APIResponse.server_error("獲取引擎資訊失敗")

@text_bp.route('/engine/switch', methods=['POST'])
@api_exception_handler
@validate_request_json(required_fields=['engine_type'])
def switch_engine():
    """切換 AI 引擎"""
    data = request.json
    engine_type = data.get('engine_type', '').strip().lower()
    
    if engine_type not in ['ollama', 'vllm']:
        return APIResponse.validation_error("引擎類型必須是 'ollama' 或 'vllm'")
    
    text_service, _, _ = get_services()
    if not text_service:
        return APIResponse.server_error("服務初始化失敗")
    
    try:
        text_service.switch_engine(engine_type)
        info = text_service.get_engine_info()
        return APIResponse.success(info, f"已切換至 {engine_type} 引擎")
    except Exception as e:
        logger.error(f"切換引擎失敗: {str(e)}")
        return APIResponse.server_error(f"切換引擎失敗: {str(e)}")

@text_bp.route('/engine/health', methods=['GET'])
@api_exception_handler
def check_engine_health():
    """檢查當前 AI 引擎健康狀態"""
    text_service, _, _ = get_services()
    if not text_service:
        return APIResponse.server_error("服務初始化失敗")
    
    try:
        health = text_service.ai_engine.check_health()
        engine_info = text_service.get_engine_info()
        
        return APIResponse.success({
            "healthy": health,
            "engine_type": engine_info.get("engine_type"),
            "url": engine_info.get("url"),
            "model": engine_info.get("model")
        }, "引擎健康檢查完成")
    except Exception as e:
        logger.error(f"引擎健康檢查失敗: {str(e)}")
        return APIResponse.server_error("引擎健康檢查失敗")

@text_bp.route('/process', methods=['POST'])
@api_exception_handler
@validate_request_json(
    required_fields=['text', 'user_id'],
    optional_fields=['processing_mode', 'detail_level', 'ai_model', 'custom_mode_prompt', 'custom_detail_prompt', 'custom_format_template', 'email_enabled', 'email_address', 'selected_tags', 'custom_prompt', 'enable_clean_filler']
)
def process_text():
    """純文字處理"""
    data = request.json
    text = data.get('text', '').strip()
    user_id = data.get('user_id', '').strip()
    
    # 驗證輸入
    if len(text) < 10:
        return APIResponse.validation_error("文字內容至少需要 10 個字符")
    
    if len(text) > 100000:
        return APIResponse.validation_error("文字內容過長，最多 100,000 個字符")
    
    if not RequestValidator.validate_user_id(user_id):
        return APIResponse.validation_error("無效的用戶 ID 格式")
    
    # 驗證可選參數
    processing_mode = data.get('processing_mode', 'default')
    detail_level = data.get('detail_level', 'normal')
    ai_model = data.get('ai_model', 'phi4-mini:3.8b')
    
    if not RequestValidator.validate_processing_mode(processing_mode):
        return APIResponse.validation_error(f"無效的處理模式: {processing_mode}")
    
    if not RequestValidator.validate_detail_level(detail_level):
        return APIResponse.validation_error(f"無效的詳細程度: {detail_level}")
    
    if not RequestValidator.validate_model_name(ai_model):
        return APIResponse.validation_error(f"無效的模型名稱: {ai_model}")
        
    # 動態獲取服務
    text_service, config_service, cache_manager = get_services()
    queue_manager = get_queue_manager()
    
    if not config_service:
        return APIResponse.service_unavailable("配置服務")
    
    if not queue_manager:
        return APIResponse.service_unavailable("任務隊列服務")
        
    # 獲取用戶配置
    user_config = config_service.get_user_config(user_id)
    
    # 重新獲取處理選項，優先使用請求參數，其次使用用戶配置
    processing_mode = data.get('processing_mode', user_config.processing_mode)
    detail_level = data.get('detail_level', user_config.detail_level)
    
    # 對於 AI 模型，優先使用當前引擎的模型，而不是用戶配置
    ai_model = data.get('ai_model')
    if not ai_model:
        from config import config
        ai_model = config.get_current_ai_model()
        
    # 獲取自定義 prompt 參數
    custom_mode_prompt = data.get('custom_mode_prompt')
    custom_detail_prompt = data.get('custom_detail_prompt')
    custom_format_template = data.get('custom_format_template')
    
    # 獲取標籤參數
    selected_tags = data.get('selected_tags', [])
    if selected_tags and not isinstance(selected_tags, list):
        return APIResponse.validation_error("selected_tags 必須是字符串陣列")

    # 獲取自定義 prompt 參數（用於 custom 標籤）
    custom_prompt = data.get('custom_prompt', '')

    # 驗證標籤組合
    if selected_tags:
        from prompt_config import PromptConfig
        is_valid, error_msg = PromptConfig.validate_tag_combination(selected_tags)
        if not is_valid:
            return APIResponse.validation_error(f"標籤組合無效: {error_msg}")

    # 驗證 custom 標籤是否提供了 custom_prompt
    if selected_tags and 'custom' in selected_tags and not custom_prompt:
        return APIResponse.validation_error("選擇 'custom' 標籤時必須提供 custom_prompt 參數")
    
    # 獲取 email 通知參數
    email_enabled = data.get('email_enabled', False)
    email_address = data.get('email_address', '')
    
    # 檢查自定義模式參數
    if processing_mode == 'custom' and not custom_mode_prompt:
        return APIResponse.validation_error('自定義模式需要提供 custom_mode_prompt 參數')
    
    if detail_level == 'custom' and not custom_detail_prompt:
        return APIResponse.validation_error('自定義詳細程度需要提供 custom_detail_prompt 參數')
    
    # 獲取文字清理參數
    enable_clean_filler = data.get('enable_clean_filler', False)

    # 檢查文字長度 - 🔧 修復：增加閾值，避免短文字進入隊列造成問題
    if len(text) > 50000:  # 非常長的文字才需要排隊處理
        task_data = {
            'type': 'text_processing',  # 修復：使用 'type' 字段而不是 'task_type'
            'task_data': {'text': text},
            'processing_config': {
                'processing_mode': processing_mode,
                'detail_level': detail_level,
                'ai_model': ai_model,
                'custom_mode_prompt': custom_mode_prompt,
                'custom_detail_prompt': custom_detail_prompt,
                'custom_format_template': custom_format_template,
                'selected_tags': selected_tags,
                'custom_prompt': custom_prompt,
                'enable_clean_filler': enable_clean_filler
            },
            'user_id': user_id
        }
        
        try:
            task_id = queue_manager.add_to_queue(user_id, f'text_process_{len(text)}', len(text), task_data)
            
            return APIResponse.success(
                data={'task_id': task_id, 'status': 'queued'},
                message='文字過長，已加入處理隊列',
                code=202  # Accepted
            )
        except Exception as e:
            logger.error(f"添加任務到隊列失敗: {e}")
            return APIResponse.internal_error("無法添加任務到處理隊列")
    
    # 直接處理短文字
    if not text_service:
        return APIResponse.service_unavailable("文字處理服務")

    try:
        # 口語贅字清理（如果啟用）
        if enable_clean_filler:
            try:
                from processing.text_refinement import clean_filler_words
                text = clean_filler_words(text)
                logger.info(f"口語贅字清理完成，文字長度: {len(text)}")
            except ImportError:
                logger.warning("text_refinement 模組不可用，跳過口語贅字清理")
            except Exception as e:
                logger.warning(f"口語贅字清理失敗: {e}，使用原始文字")

        # 使用 text_service 進行處理
        result = text_service.process_text_sync(
            text=text,
            model=ai_model,
            mode=processing_mode,
            detail_level=detail_level,
            custom_mode_prompt=custom_mode_prompt,
            custom_detail_prompt=custom_detail_prompt,
            custom_format_template=custom_format_template,
            selected_tags=selected_tags,
            custom_prompt=custom_prompt
        )
        
        # 🔧 強制清理GPU緩存
        from utils.gpu_cleaner import cleanup_gpu
        cleanup_gpu(log_prefix="文字處理完成後 ")
        
        return APIResponse.success(
            data={
                'original_text': text,
                'processed_text': result,
                'processing_mode': processing_mode,
                'detail_level': detail_level,
                'ai_model': ai_model,
                'status': 'completed'
            },
            message='文字處理完成'
        )
        
    except Exception as e:
        logger.error(f"文字處理失敗: {e}")
        
        # 🔧 錯誤情況下也要清理GPU緩存
        from utils.gpu_cleaner import cleanup_gpu
        cleanup_gpu(log_prefix="錯誤處理後 ")
        
        return APIResponse.internal_error(f"文字處理失敗: {str(e)}")

@text_bp.route('/chunk', methods=['POST'])
@api_exception_handler
@validate_request_json(
    required_fields=['text'],
    optional_fields=['max_chars']
)
def chunk_text():
    """文字分塊處理"""
    data = request.json
    text = data.get('text', '').strip()
    max_chars = data.get('max_chars', 2000)
    
    # 驗證輸入
    if len(text) < 10:
        return APIResponse.validation_error("文字內容至少需要 10 個字符")
    
    if not isinstance(max_chars, int) or max_chars < 100 or max_chars > 10000:
        return APIResponse.validation_error("max_chars 必須是 100-10000 之間的整數")
    
    # 獲取服務
    text_service, _, _ = get_services()
    if not text_service:
        return APIResponse.service_unavailable("文字處理服務")
    
    chunks = text_service.chunk_text(text, max_chars)
    
    return APIResponse.success(
        data={
            'chunks': chunks,
            'total_chunks': len(chunks),
            'original_length': len(text),
            'max_chars_per_chunk': max_chars
        },
        message='文字分塊完成'
    )

@text_bp.route('/batch-process', methods=['POST'])
@api_exception_handler
@validate_request_json(
    required_fields=['texts'],
    optional_fields=['processing_mode', 'detail_level', 'ai_model', 'custom_mode_prompt', 'custom_detail_prompt', 'custom_format_template', 'email_enabled', 'email_address']
)
def batch_process_text():
    """批次處理多段文字"""
    data = request.json
    texts = data.get('texts', [])
    
    # 驗證輸入
    if not isinstance(texts, list):
        return APIResponse.validation_error("texts 必須是文字陣列")
    
    if len(texts) == 0:
        return APIResponse.validation_error("texts 陣列不能為空")
    
    if len(texts) > 50:
        return APIResponse.validation_error("批次處理最多支援 50 段文字")
    
    # 驗證每個文字項目
    for i, text in enumerate(texts):
        if not isinstance(text, str):
            return APIResponse.validation_error(f"第 {i+1} 項必須是文字")
        if len(text.strip()) < 10:
            return APIResponse.validation_error(f"第 {i+1} 項文字內容至少需要 10 個字符")
        if len(text) > 50000:
            return APIResponse.validation_error(f"第 {i+1} 項文字內容過長，最多 50,000 個字符")
    
    # 獲取處理選項
    processing_mode = data.get('processing_mode', 'default')
    detail_level = data.get('detail_level', 'normal')
    
    # 對於 AI 模型，優先使用當前引擎的模型
    ai_model = data.get('ai_model')
    if not ai_model:
        from config import config
        ai_model = config.get_current_ai_model()
    
    # 驗證參數
    if not RequestValidator.validate_processing_mode(processing_mode):
        return APIResponse.validation_error(f"無效的處理模式: {processing_mode}")
    
    if not RequestValidator.validate_detail_level(detail_level):
        return APIResponse.validation_error(f"無效的詳細程度: {detail_level}")
    
    if not RequestValidator.validate_model_name(ai_model):
        return APIResponse.validation_error(f"無效的模型名稱: {ai_model}")
    
    # 獲取自定義 prompt 參數
    custom_mode_prompt = data.get('custom_mode_prompt')
    custom_detail_prompt = data.get('custom_detail_prompt')
    custom_format_template = data.get('custom_format_template')
    
    # 檢查自定義模式參數
    if processing_mode == 'custom' and not custom_mode_prompt:
        return APIResponse.validation_error('自定義模式需要提供 custom_mode_prompt 參數')
    
    if detail_level == 'custom' and not custom_detail_prompt:
        return APIResponse.validation_error('自定義詳細程度需要提供 custom_detail_prompt 參數')
    
    # 獲取服務
    text_service, _, _ = get_services()
    if not text_service:
        return APIResponse.service_unavailable("文字處理服務")
    
    # 批次處理
    results = text_service.process_text_batch(
        texts, ai_model, processing_mode, detail_level,
        custom_mode_prompt, custom_detail_prompt, custom_format_template
    )
    
    return APIResponse.success(
        data={
            'results': results,
            'total_processed': len(results),
            'processing_mode': processing_mode,
            'detail_level': detail_level,
            'ai_model': ai_model,
            'total_input_texts': len(texts)
        },
        message='批次文字處理完成'
    )

@text_bp.route('/models', methods=['GET'])
@api_exception_handler
def get_ai_models():
    """獲取可用的 AI 模型列表"""
    text_service, _, _ = get_services()
    if not text_service:
        return APIResponse.service_unavailable("文字處理服務")
    
    models = text_service.get_available_models()
    
    return APIResponse.success(
        data={
            'models': models,
            'total_count': len(models)
        },
        message='已獲取 AI 模型列表'
    )

@text_bp.route('/modes', methods=['GET'])
def get_processing_modes():
    """獲取可用的處理模式"""
    try:
        from prompt_config import PromptConfig
        modes = PromptConfig.get_available_modes()
        descriptions = {mode: PromptConfig.get_mode_description(mode) for mode in modes}
        
        return jsonify({
            'modes': modes,
            'descriptions': descriptions
        })
    except Exception as e:
        logger.error(f"獲取處理模式失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@text_bp.route('/detail-levels', methods=['GET'])
def get_detail_levels():
    """獲取可用的詳細程度等級"""
    try:
        from prompt_config import PromptConfig
        levels = PromptConfig.get_available_detail_levels()
        
        return jsonify({
            'detail_levels': levels
        })
    except Exception as e:
        logger.error(f"獲取詳細程度等級失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@text_bp.route('/custom-prompt/validate', methods=['POST'])
def validate_custom_prompt():
    """驗證自定義 prompt"""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        prompt_type = data.get('type', 'mode')  # mode, detail, format
        
        from prompt_config import PromptConfig
        is_valid, message = PromptConfig.validate_custom_prompt(prompt, prompt_type)
        
        return jsonify({
            'valid': is_valid,
            'message': message,
            'type': prompt_type
        })
    except Exception as e:
        logger.error(f"驗證自定義 prompt 失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@text_bp.route('/custom-prompt/suggestions', methods=['GET'])
def get_custom_prompt_suggestions():
    """獲取自定義 prompt 建議"""
    try:
        from prompt_config import PromptConfig
        suggestions = PromptConfig.get_custom_prompt_suggestions()
        
        return jsonify({
            'suggestions': suggestions
        })
    except Exception as e:
        logger.error(f"獲取自定義 prompt 建議失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@text_bp.route('/custom-prompt/templates', methods=['GET'])
def get_custom_prompt_templates():
    """獲取自定義 prompt 模板"""
    try:
        template_type = request.args.get('type', 'all')  # all, mode, detail, format
        
        from prompt_config import PromptConfig
        suggestions = PromptConfig.get_custom_prompt_suggestions()
        
        # 根據類型過濾模板
        if template_type == 'all':
            templates = suggestions
        elif template_type == 'mode':
            templates = {
                "模式範例": suggestions.get("模式範例 (Mode Examples)", {}),
                "行業專用": suggestions.get("行業專用範例 (Industry-Specific Examples)", {}),
                "特殊用途": suggestions.get("特殊用途範例 (Special Purpose Examples)", {})
            }
        elif template_type == 'detail':
            templates = {
                "詳細程度範例": suggestions.get("詳細程度範例 (Detail Level Examples)", {})
            }
        elif template_type == 'format':
            templates = {
                "格式模板範例": suggestions.get("格式模板範例 (Format Template Examples)", {})
            }
        else:
            templates = suggestions
        
        return jsonify({
            'templates': templates,
            'type': template_type,
            'count': sum(len(v) if isinstance(v, dict) else 1 for v in templates.values())
        })
    except Exception as e:
        logger.error(f"獲取自定義 prompt 模板失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@text_bp.route('/custom-prompt/analyze', methods=['POST'])
def analyze_custom_prompt():
    """分析自定義 prompt 的特性和建議"""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({'error': '缺少 prompt 內容'}), 400
        
        from prompt_config import PromptConfig
        import re
        
        # 基本統計
        stats = {
            'length': len(prompt),
            'words': len(prompt.split()),
            'lines': len(prompt.split('\n')),
            'chinese_chars': sum(1 for char in prompt if '\u4e00' <= char <= '\u9fff'),
            'english_words': len(re.findall(r'\b[a-zA-Z]+\b', prompt))
        }
        
        # 內容分析
        analysis = {
            'has_structure': any(indicator in prompt for indicator in ['#', '##', '###', '*', '•', ':', '：']),
            'has_placeholders': bool(re.search(r'\[.*?\]|\{.*?\}|<.*?>|【.*?】|\.\.\.', prompt)),
            'has_instructions': any(keyword in prompt.lower() for keyword in [
                '整理', '分析', '摘要', '處理', 'analyze', 'summarize', 'organize'
            ]),
            'complexity_level': 'simple' if len(prompt.split()) < 10 else 'medium' if len(prompt.split()) < 50 else 'complex'
        }
        
        # 驗證各種類型
        validations = {
            'as_mode': PromptConfig.validate_custom_prompt(prompt, 'mode'),
            'as_detail': PromptConfig.validate_custom_prompt(prompt, 'detail'), 
            'as_format': PromptConfig.validate_custom_prompt(prompt, 'format')
        }
        
        # 生成建議
        suggestions = []
        if not analysis['has_structure']:
            suggestions.append("建議添加結構化元素（如標題、列表符號）來提高可讀性")
        if not analysis['has_placeholders'] and not validations['as_format'][0]:
            suggestions.append("如用作格式模板，建議添加佔位符來標示變量位置")
        if stats['length'] > 1000:
            suggestions.append("prompt 較長，建議簡化以提高 AI 理解效果")
        if stats['chinese_chars'] > 0 and stats['english_words'] > 0:
            if stats['chinese_chars'] / stats['length'] < 0.7:
                suggestions.append("建議保持語言一致性，避免過多中英混用")
        
        return jsonify({
            'stats': stats,
            'analysis': analysis,
            'validations': {k: {'valid': v[0], 'message': v[1]} for k, v in validations.items()},
            'suggestions': suggestions,
            'recommended_use': 'mode' if validations['as_mode'][0] else 'detail' if validations['as_detail'][0] else 'format' if validations['as_format'][0] else 'general'
        })
        
    except Exception as e:
        logger.error(f"分析自定義 prompt 失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@text_bp.route('/custom-prompt/preview', methods=['POST'])
def preview_custom_prompt():
    """預覽自定義 prompt 的效果"""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        sample_text = data.get('sample_text', '')
        prompt_type = data.get('type', 'mode')
        
        if not prompt:
            return jsonify({'error': '缺少 prompt 內容'}), 400
        
        # 如果沒有提供示例文字，使用預設的
        if not sample_text:
            sample_text = """這是一段示例文字，用於測試自定義 prompt 的效果。
            這段文字包含了一些基本的信息和內容，可以用來演示不同的處理方式。
            內容涵蓋了技術討論、問題分析和解決方案建議等方面。"""
        
        from prompt_config import PromptConfig
        
        # 根據類型生成完整的 prompt - 固定使用 DETAILED 模式
        if prompt_type == 'mode':
            full_prompt = PromptConfig.generate_prompt(
                sample_text,
                PromptConfig.ProcessingMode.CUSTOM,
                PromptConfig.DetailLevel.DETAILED,
                custom_mode_prompt=prompt
            )
        elif prompt_type == 'detail':
            full_prompt = PromptConfig.generate_prompt(
                sample_text,
                PromptConfig.ProcessingMode.DEFAULT,
                PromptConfig.DetailLevel.DETAILED,
                custom_detail_prompt=prompt
            )
        elif prompt_type == 'format':
            full_prompt = PromptConfig.generate_prompt(
                sample_text,
                PromptConfig.ProcessingMode.CUSTOM,
                PromptConfig.DetailLevel.DETAILED,
                custom_mode_prompt="請整理以下內容",
                custom_format_template=prompt
            )
        else:
            full_prompt = prompt + "\n\n待處理內容：\n" + sample_text
        
        return jsonify({
            'preview': full_prompt,
            'sample_text': sample_text,
            'prompt_type': prompt_type,
            'estimated_length': len(full_prompt),
            'estimated_tokens': len(full_prompt.split()) * 1.3  # 粗略估算 token 數
        })
        
    except Exception as e:
        logger.error(f"預覽自定義 prompt 失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@text_bp.route('/custom-prompt/ai-validate', methods=['POST'])
def ai_validate_custom_prompt():
    """使用 AI 輔助驗證自定義 prompt"""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        prompt_type = data.get('type', 'mode')
        
        if not prompt:
            return jsonify({'error': '缺少 prompt 內容'}), 400
        
        from prompt_config import PromptConfig
        
        # 使用 AI 進行深度驗證
        ai_result = PromptConfig.validate_custom_prompt_with_ai(prompt, prompt_type)
        
        # 同時進行基本驗證以作對比
        basic_validation = PromptConfig.validate_custom_prompt(prompt, prompt_type)
        
        return jsonify({
            'ai_validation': ai_result,
            'basic_validation': {
                'valid': basic_validation[0],
                'message': basic_validation[1]
            },
            'prompt_type': prompt_type,
            'timestamp': __import__('time').time()
        })
        
    except Exception as e:
        logger.error(f"AI 驗證自定義 prompt 失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@text_bp.route('/custom-prompt/optimize', methods=['POST'])
def optimize_custom_prompt():
    """獲取 prompt 優化建議"""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        prompt_type = data.get('type', 'mode')
        
        if not prompt:
            return jsonify({'error': '缺少 prompt 內容'}), 400
        
        from prompt_config import PromptConfig
        
        # 獲取優化建議
        optimization_result = PromptConfig.get_prompt_optimization_suggestions(prompt, prompt_type)
        
        return jsonify({
            'optimization': optimization_result,
            'original_prompt': prompt,
            'prompt_type': prompt_type
        })
        
    except Exception as e:
        logger.error(f"獲取 prompt 優化建議失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@text_bp.route('/custom-prompt/batch-validate', methods=['POST'])
def batch_validate_custom_prompts():
    """批量驗證多個自定義 prompts"""
    try:
        data = request.json
        prompts = data.get('prompts', [])
        
        if not prompts or not isinstance(prompts, list):
            return jsonify({'error': '缺少 prompts 列表'}), 400
        
        from prompt_config import PromptConfig
        
        results = []
        for i, prompt_data in enumerate(prompts):
            prompt_text = prompt_data.get('prompt', '')
            prompt_type = prompt_data.get('type', 'mode')
            prompt_id = prompt_data.get('id', f'prompt_{i+1}')
            
            if not prompt_text:
                results.append({
                    'id': prompt_id,
                    'valid': False,
                    'message': 'prompt 內容為空',
                    'type': prompt_type
                })
                continue
            
            # 進行驗證
            is_valid, message = PromptConfig.validate_custom_prompt(prompt_text, prompt_type)
            
            results.append({
                'id': prompt_id,
                'valid': is_valid,
                'message': message,
                'type': prompt_type,
                'length': len(prompt_text),
                'word_count': len(prompt_text.split())
            })
        
        # 生成批量統計
        total_count = len(results)
        valid_count = sum(1 for r in results if r['valid'])
        invalid_count = total_count - valid_count
        
        return jsonify({
            'results': results,
            'summary': {
                'total': total_count,
                'valid': valid_count,
                'invalid': invalid_count,
                'success_rate': round(valid_count / total_count * 100, 1) if total_count > 0 else 0
            }
        })
        
    except Exception as e:
        logger.error(f"批量驗證 prompts 失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@text_bp.route('/custom-prompt/export', methods=['POST'])
def export_custom_prompts():
    """導出自定義 prompts 配置"""
    try:
        data = request.json
        prompts = data.get('prompts', [])
        export_format = data.get('format', 'json')  # json, yaml, txt
        
        if not prompts:
            return jsonify({'error': '缺少 prompts 數據'}), 400
        
        import time
        timestamp = int(time.time())
        
        if export_format == 'json':
            export_data = {
                'metadata': {
                    'exported_at': timestamp,
                    'version': '1.0',
                    'total_prompts': len(prompts)
                },
                'prompts': prompts
            }
            
            return jsonify({
                'data': export_data,
                'filename': f'custom_prompts_{timestamp}.json',
                'format': 'json',
                'size': len(str(export_data))
            })
            
        elif export_format == 'txt':
            txt_content = f"自定義 Prompt 配置導出\n"
            txt_content += f"導出時間: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}\n"
            txt_content += f"總計 {len(prompts)} 個 prompts\n\n"
            txt_content += "=" * 50 + "\n\n"
            
            for i, prompt_data in enumerate(prompts, 1):
                txt_content += f"Prompt {i}:\n"
                txt_content += f"類型: {prompt_data.get('type', '未知')}\n"
                txt_content += f"名稱: {prompt_data.get('name', f'Prompt {i}')}\n"
                txt_content += f"內容: {prompt_data.get('prompt', '')}\n"
                txt_content += "-" * 30 + "\n\n"
            
            return jsonify({
                'data': txt_content,
                'filename': f'custom_prompts_{timestamp}.txt',
                'format': 'txt',
                'size': len(txt_content)
            })
            
        else:
            return jsonify({'error': f'不支持的導出格式: {export_format}'}), 400
        
    except Exception as e:
        logger.error(f"導出 prompts 失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ===== 標籤相關 API 端點 =====

@text_bp.route('/tags', methods=['GET'])
@api_exception_handler
def get_available_tags():
    """獲取所有可用的摘要標籤"""
    try:
        from prompt_config import PromptConfig
        tags = PromptConfig.get_available_tags()

        return APIResponse.success(
            data={
                'tags': tags,
                'total_tags': len(tags)
            },
            message='已獲取可用的摘要標籤'
        )

    except Exception as e:
        logger.error(f"獲取標籤失敗: {str(e)}")
        return APIResponse.internal_error(f"獲取標籤失敗: {str(e)}")

@text_bp.route('/tags/validate', methods=['POST'])
@api_exception_handler
@validate_request_json(
    required_fields=['tags'],
    optional_fields=[]
)
def validate_tag_combination():
    """驗證標籤組合的合理性"""
    try:
        data = request.json
        selected_tags = data.get('tags', [])
        
        # 驗證輸入
        if not isinstance(selected_tags, list):
            return APIResponse.validation_error("tags 必須是字符串陣列")
        
        if len(selected_tags) > 10:
            return APIResponse.validation_error("一次最多只能驗證 10 個標籤")
        
        from prompt_config import PromptConfig
        is_valid, message = PromptConfig.validate_tag_combination(selected_tags)
        
        return APIResponse.success(
            data={
                'valid': is_valid,
                'message': message,
                'selected_tags': selected_tags,
                'tag_count': len(selected_tags)
            },
            message='標籤組合驗證完成'
        )
        
    except Exception as e:
        logger.error(f"驗證標籤組合失敗: {str(e)}")
        return APIResponse.internal_error(f"驗證標籤組合失敗: {str(e)}")

@text_bp.route('/tags/suggestions', methods=['GET'])
@api_exception_handler
def get_tag_suggestions():
    """根據處理模式獲取推薦標籤"""
    try:
        mode = request.args.get('mode', 'default')

        # 驗證模式
        if not RequestValidator.validate_processing_mode(mode):
            return APIResponse.validation_error(f"無效的處理模式: {mode}")

        from prompt_config import PromptConfig, ProcessingMode

        # 轉換為枚舉
        try:
            mode_enum = ProcessingMode(mode)
        except ValueError:
            mode_enum = ProcessingMode.DEFAULT

        suggested_tag_ids = PromptConfig.get_tag_suggestions(mode_enum)

        # 獲取標籤詳細信息
        all_tags = PromptConfig.get_available_tags()
        detailed_suggestions = [tag for tag in all_tags if tag['id'] in suggested_tag_ids]

        return APIResponse.success(
            data={
                'mode': mode,
                'suggested_tags': detailed_suggestions,
                'tag_ids': suggested_tag_ids,
                'total_suggestions': len(suggested_tag_ids)
            },
            message=f'已獲取 {mode} 模式的推薦標籤'
        )

    except Exception as e:
        logger.error(f"獲取標籤建議失敗: {str(e)}")
        return APIResponse.internal_error(f"獲取標籤建議失敗: {str(e)}")

@text_bp.route('/tags/preview', methods=['POST'])
@api_exception_handler
@validate_request_json(
    required_fields=['tags'],
    optional_fields=['sample_text', 'mode', 'detail_level']
)
def preview_tag_prompt():
    """預覽標籤組合生成的 prompt 效果"""
    try:
        data = request.json
        selected_tags = data.get('tags', [])
        sample_text = data.get('sample_text', '')
        mode = data.get('mode', 'default')
        detail_level = data.get('detail_level', 'normal')
        
        # 驗證輸入
        if not isinstance(selected_tags, list):
            return APIResponse.validation_error("tags 必須是字符串陣列")
        
        if not selected_tags:
            return APIResponse.validation_error("至少需要選擇一個標籤")
        
        # 如果沒有提供示例文字，使用預設的
        if not sample_text:
            sample_text = """這是一段示例文字，用於測試標籤組合的效果。
            內容包含了技術討論、重要決策和行動項目等多種類型的信息。
            可以用來演示不同標籤組合對處理結果的影響。"""
        
        from prompt_config import PromptConfig, ProcessingMode, DetailLevel

        # 轉換為枚舉
        try:
            mode_enum = ProcessingMode(mode)
            # 固定使用 DETAILED 模式
            detail_enum = DetailLevel.DETAILED
        except ValueError:
            mode_enum = ProcessingMode.DEFAULT
            detail_enum = DetailLevel.DETAILED
        
        # 生成完整的 prompt
        full_prompt = PromptConfig.generate_prompt(
            text=sample_text,
            mode=mode_enum,
            detail_level=detail_enum,
            selected_tags=selected_tags
        )
        
        # 生成標籤指令部分
        tag_instructions = PromptConfig.generate_tag_instructions(selected_tags)
        
        return APIResponse.success(
            data={
                'full_prompt': full_prompt,
                'tag_instructions': tag_instructions,
                'selected_tags': selected_tags,
                'sample_text': sample_text,
                'mode': mode,
                'detail_level': detail_level,
                'estimated_length': len(full_prompt),
                'estimated_tokens': len(full_prompt.split()) * 1.3
            },
            message='標籤組合 prompt 預覽生成完成'
        )
        
    except Exception as e:
        logger.error(f"預覽標籤 prompt 失敗: {str(e)}")
        return APIResponse.internal_error(f"預覽標籤 prompt 失敗: {str(e)}")

@text_bp.route('/tags/categories', methods=['GET'])
@api_exception_handler
def get_tag_categories():
    """獲取標籤分類信息（簡化版 - 無分類）"""
    try:
        from prompt_config import PromptConfig
        all_tags = PromptConfig.get_available_tags()

        return APIResponse.success(
            data={
                'tags': all_tags,
                'total_tags': len(all_tags)
            },
            message='已獲取標籤信息'
        )

    except Exception as e:
        logger.error(f"獲取標籤失敗: {str(e)}")
        return APIResponse.internal_error(f"獲取標籤失敗: {str(e)}")

@text_bp.route('/tags/<tag_id>', methods=['GET'])
@api_exception_handler
def get_tag_details(tag_id):
    """獲取特定標籤的詳細信息"""
    try:
        from prompt_config import PromptConfig, SummaryTag

        # 驗證標籤 ID
        try:
            tag_enum = SummaryTag(tag_id)
        except ValueError:
            return APIResponse.validation_error(f"無效的標籤 ID: {tag_id}")

        if tag_enum not in PromptConfig.TAG_CONFIG:
            return APIResponse.validation_error(f"標籤配置不存在: {tag_id}")

        tag_config = PromptConfig.TAG_CONFIG[tag_enum]

        return APIResponse.success(
            data={
                'id': tag_id,
                'name': tag_config['display_name'],
                'description': tag_config['description'],
                'icon': tag_config.get('icon', ''),
                'prompt_instruction': tag_config['prompt_instruction']
            },
            message=f'已獲取標籤 {tag_id} 的詳細信息'
        )
        
    except Exception as e:
        logger.error(f"獲取標籤詳細信息失敗: {str(e)}")
        return APIResponse.internal_error(f"獲取標籤詳細信息失敗: {str(e)}")


@text_bp.route('/test/summary', methods=['POST'])
@api_exception_handler
def test_ai_summary():
    """
    測試 AI 摘要功能 - 直接測試文本處理

    Request Body:
    {
        "text": "原始文本內容（Whisper 轉錄結果）",
        "tags": ["tag1", "tag2"],  // 可選，標籤 ID 列表
        "mode": "default",  // 可選，處理模式 (default, meeting, lecture, interview)
        "detail_level": "normal",  // 可選，詳細程度 (simple, normal, detailed, comprehensive, executive)
        "ai_model": "gpt-oss:20b",  // 可選，AI 模型
        "custom_prompt": ""  // 可選，自定義 prompt
    }

    Response:
    {
        "success": true,
        "data": {
            "summary": "AI 生成的摘要",
            "original_length": 12345,
            "summary_length": 3456,
            "tags_used": ["tag1", "tag2"],
            "mode": "default",
            "detail_level": "normal",
            "model": "gpt-oss:20b",
            "processing_time": 15.3
        },
        "message": "測試成功"
    }
    """
    try:
        # 驗證請求
        data = request.get_json()
        if not data:
            return APIResponse.bad_request("請求體不能為空")

        # 獲取必需參數
        text = data.get('text', '').strip()
        if not text:
            return APIResponse.bad_request("text 參數不能為空")

        # 獲取可選參數
        tags = data.get('tags', [])
        mode = data.get('mode', 'default')
        detail_level = data.get('detail_level', 'normal')
        ai_model = data.get('ai_model', None)  # None = 使用默認模型
        custom_prompt = data.get('custom_prompt', '').strip()

        logger.info(f"🧪 測試 AI 摘要 - 文本長度: {len(text)}, 標籤: {tags}, 模式: {mode}, 詳細度: {detail_level}")

        # 驗證標籤（如果有提供）
        if tags:
            from prompt_config.prompt_config import PromptConfig
            is_valid, error_msg = PromptConfig.validate_tag_combination(tags)
            if not is_valid:
                return APIResponse.bad_request(f"標籤組合無效: {error_msg}")

        # 記錄開始時間
        import time
        start_time = time.time()

        # 調用 AI 處理函數
        from processing.text_processing import organize_text_with_ai

        summary = organize_text_with_ai(
            text=text,
            mode=mode,
            detail_level=detail_level,
            selected_tags=tags if tags else None,
            custom_prompt=custom_prompt if custom_prompt else None,
            ai_model=ai_model
        )

        # 計算處理時間
        processing_time = round(time.time() - start_time, 2)

        # 檢查結果
        if not summary or summary.strip() == '':
            logger.warning("⚠️ AI 返回空結果")
            return APIResponse.server_error("AI 處理失敗，返回空結果")

        # 檢查是否為 prompt echo（AI 直接回顯）
        if summary.strip() == text.strip():
            logger.warning("⚠️ AI 回應與原文完全相同（可能是 prompt echo）")
            return APIResponse.server_error("AI 處理異常，輸出與輸入相同")

        logger.info(f"✅ 測試成功 - 摘要長度: {len(summary)}, 處理時間: {processing_time}秒")

        # 返回結果
        return APIResponse.success(
            data={
                'summary': summary,
                'original_length': len(text),
                'summary_length': len(summary),
                'tags_used': tags,
                'mode': mode,
                'detail_level': detail_level,
                'model': ai_model or 'default',
                'processing_time': processing_time,
                'compression_ratio': round(len(summary) / len(text) * 100, 2) if len(text) > 0 else 0
            },
            message=f"測試成功，處理時間 {processing_time} 秒"
        )

    except ValueError as e:
        logger.error(f"參數驗證失敗: {str(e)}")
        return APIResponse.bad_request(f"參數錯誤: {str(e)}")
    except Exception as e:
        logger.error(f"測試 AI 摘要失敗: {str(e)}", exc_info=True)
        return APIResponse.internal_error(f"測試失敗: {str(e)}")