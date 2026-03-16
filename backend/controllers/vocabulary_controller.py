"""
詞彙管理 API 控制器
提供詞彙表的 CRUD 操作和 prompt 生成功能
"""
from flask import Blueprint, request, jsonify, send_file
import logging
from typing import Dict, List
import io
import json

logger = logging.getLogger(__name__)

# 創建 blueprint
vocabulary_bp = Blueprint('vocabulary', __name__, url_prefix='/api/vocabulary')


def get_vocabulary_config():
    """獲取詞彙配置實例"""
    try:
        from vocabulary.vocabulary_config import vocabulary_config
        return vocabulary_config
    except Exception as e:
        logger.error(f"無法載入詞彙配置: {e}")
        return None


def get_prompt_generator():
    """獲取 prompt 生成器實例"""
    try:
        from vocabulary.vocabulary_prompt_generator import prompt_generator
        return prompt_generator
    except Exception as e:
        logger.error(f"無法載入 prompt 生成器: {e}")
        return None


@vocabulary_bp.route('/terms', methods=['GET'])
def get_all_terms():
    """獲取所有術語"""
    try:
        vocab_config = get_vocabulary_config()
        if not vocab_config:
            return jsonify({'error': '詞彙配置不可用'}), 500

        terms = vocab_config.get_all_terms()

        # 轉換為前端友好的格式
        terms_list = []
        for term, config in terms.items():
            terms_list.append({
                'term': term,
                'corrections': config.get('corrections', []),
                'context': config.get('context', []),
                'priority': config.get('priority', 5),
                'case_sensitive': config.get('case_sensitive', False)
            })

        # 按優先級排序
        terms_list.sort(key=lambda x: x['priority'], reverse=True)

        return jsonify({
            'success': True,
            'terms': terms_list,
            'total_count': len(terms_list)
        })

    except Exception as e:
        logger.error(f"獲取術語列表失敗: {e}")
        return jsonify({'error': str(e)}), 500


@vocabulary_bp.route('/terms/<string:term>', methods=['GET'])
def get_term(term: str):
    """獲取特定術語的詳細信息"""
    try:
        vocab_config = get_vocabulary_config()
        if not vocab_config:
            return jsonify({'error': '詞彙配置不可用'}), 500

        term_config = vocab_config.get_term(term)
        if not term_config:
            return jsonify({'error': f'術語不存在: {term}'}), 404

        return jsonify({
            'success': True,
            'term': term,
            'config': term_config
        })

    except Exception as e:
        logger.error(f"獲取術語失敗: {e}")
        return jsonify({'error': str(e)}), 500


@vocabulary_bp.route('/terms', methods=['POST'])
def add_term():
    """添加新術語"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '缺少請求數據'}), 400

        # 驗證必需字段
        term = data.get('term')
        corrections = data.get('corrections', [])

        if not term:
            return jsonify({'error': '缺少術語名稱'}), 400

        if not corrections:
            return jsonify({'error': '缺少錯誤拼寫列表'}), 400

        # 可選字段
        context = data.get('context', [])
        priority = data.get('priority', 5)
        case_sensitive = data.get('case_sensitive', False)

        vocab_config = get_vocabulary_config()
        if not vocab_config:
            return jsonify({'error': '詞彙配置不可用'}), 500

        # 檢查術語是否已存在
        if vocab_config.get_term(term):
            return jsonify({'error': f'術語已存在: {term}'}), 409

        # 添加術語
        success = vocab_config.add_term(
            term=term,
            corrections=corrections,
            context=context,
            priority=priority,
            case_sensitive=case_sensitive
        )

        if success:
            return jsonify({
                'success': True,
                'message': f'術語已添加: {term}',
                'term': term
            }), 201
        else:
            return jsonify({'error': '添加術語失敗'}), 500

    except Exception as e:
        logger.error(f"添加術語失敗: {e}")
        return jsonify({'error': str(e)}), 500


@vocabulary_bp.route('/terms/<string:term>', methods=['PUT'])
def update_term(term: str):
    """更新術語配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '缺少請求數據'}), 400

        vocab_config = get_vocabulary_config()
        if not vocab_config:
            return jsonify({'error': '詞彙配置不可用'}), 500

        # 檢查術語是否存在
        if not vocab_config.get_term(term):
            return jsonify({'error': f'術語不存在: {term}'}), 404

        # 更新術語
        success = vocab_config.update_term(term, **data)

        if success:
            return jsonify({
                'success': True,
                'message': f'術語已更新: {term}',
                'term': term
            })
        else:
            return jsonify({'error': '更新術語失敗'}), 500

    except Exception as e:
        logger.error(f"更新術語失敗: {e}")
        return jsonify({'error': str(e)}), 500


@vocabulary_bp.route('/terms/<string:term>', methods=['DELETE'])
def delete_term(term: str):
    """刪除術語"""
    try:
        vocab_config = get_vocabulary_config()
        if not vocab_config:
            return jsonify({'error': '詞彙配置不可用'}), 500

        success = vocab_config.remove_term(term)

        if success:
            return jsonify({
                'success': True,
                'message': f'術語已刪除: {term}'
            })
        else:
            return jsonify({'error': f'術語不存在: {term}'}), 404

    except Exception as e:
        logger.error(f"刪除術語失敗: {e}")
        return jsonify({'error': str(e)}), 500


@vocabulary_bp.route('/prompt/generate', methods=['POST'])
def generate_prompt():
    """生成 Whisper initial_prompt"""
    try:
        data = request.get_json() or {}

        terms = data.get('terms')  # 指定術語列表，None 表示自動選擇
        max_terms = data.get('max_terms', 15)
        context_aware = data.get('context_aware', True)
        language = data.get('language', 'english')
        template = data.get('template')

        prompt_gen = get_prompt_generator()
        if not prompt_gen:
            return jsonify({'error': 'Prompt 生成器不可用'}), 500

        # 生成 prompt
        prompt = prompt_gen.generate_prompt(
            terms=terms,
            max_terms=max_terms,
            context_aware=context_aware,
            template=template,
            language=language
        )

        # 獲取統計信息
        stats = prompt_gen.get_prompt_stats(prompt)

        return jsonify({
            'success': True,
            'prompt': prompt,
            'stats': stats,
            'language': language
        })

    except Exception as e:
        logger.error(f"生成 prompt 失敗: {e}")
        return jsonify({'error': str(e)}), 500


@vocabulary_bp.route('/prompt/preview', methods=['POST'])
def preview_prompt():
    """預覽自定義 prompt"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '缺少請求數據'}), 400

        focus_terms = data.get('focus_terms', [])
        additional_context = data.get('additional_context', '')

        prompt_gen = get_prompt_generator()
        if not prompt_gen:
            return jsonify({'error': 'Prompt 生成器不可用'}), 500

        prompt = prompt_gen.generate_custom_prompt(
            focus_terms=focus_terms,
            additional_context=additional_context
        )

        stats = prompt_gen.get_prompt_stats(prompt)

        return jsonify({
            'success': True,
            'prompt': prompt,
            'stats': stats
        })

    except Exception as e:
        logger.error(f"預覽 prompt 失敗: {e}")
        return jsonify({'error': str(e)}), 500


@vocabulary_bp.route('/export', methods=['GET'])
def export_vocabulary():
    """導出詞彙表為 JSON 文件"""
    try:
        vocab_config = get_vocabulary_config()
        if not vocab_config:
            return jsonify({'error': '詞彙配置不可用'}), 500

        terms = vocab_config.get_all_terms()

        # 創建 JSON 字符串
        json_str = json.dumps(terms, ensure_ascii=False, indent=2)

        # 創建內存中的文件對象
        buffer = io.BytesIO()
        buffer.write(json_str.encode('utf-8'))
        buffer.seek(0)

        return send_file(
            buffer,
            mimetype='application/json',
            as_attachment=True,
            download_name='custom_vocabulary.json'
        )

    except Exception as e:
        logger.error(f"導出詞彙表失敗: {e}")
        return jsonify({'error': str(e)}), 500


@vocabulary_bp.route('/import', methods=['POST'])
def import_vocabulary():
    """從 JSON 文件導入詞彙表"""
    try:
        # 檢查是否有文件
        if 'file' not in request.files:
            return jsonify({'error': '缺少文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '未選擇文件'}), 400

        # 檢查文件類型
        if not file.filename.endswith('.json'):
            return jsonify({'error': '僅支持 JSON 文件'}), 400

        merge = request.form.get('merge', 'true').lower() == 'true'

        vocab_config = get_vocabulary_config()
        if not vocab_config:
            return jsonify({'error': '詞彙配置不可用'}), 500

        # 讀取文件內容
        file_content = file.read().decode('utf-8')
        imported_vocab = json.loads(file_content)

        # 驗證格式
        if not isinstance(imported_vocab, dict):
            return jsonify({'error': '無效的詞彙表格式'}), 400

        # 臨時保存到文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp:
            json.dump(imported_vocab, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name

        # 導入
        success = vocab_config.import_vocabulary(tmp_path, merge=merge)

        # 刪除臨時文件
        import os
        try:
            os.unlink(tmp_path)
        except:
            pass

        if success:
            return jsonify({
                'success': True,
                'message': f'詞彙表已導入: {len(imported_vocab)} 個術語',
                'merge': merge,
                'imported_count': len(imported_vocab)
            })
        else:
            return jsonify({'error': '導入詞彙表失敗'}), 500

    except json.JSONDecodeError as e:
        return jsonify({'error': f'JSON 格式錯誤: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"導入詞彙表失敗: {e}")
        return jsonify({'error': str(e)}), 500


@vocabulary_bp.route('/reset', methods=['POST'])
def reset_vocabulary():
    """重置為預設詞彙表"""
    try:
        vocab_config = get_vocabulary_config()
        if not vocab_config:
            return jsonify({'error': '詞彙配置不可用'}), 500

        success = vocab_config.reset_to_default()

        if success:
            return jsonify({
                'success': True,
                'message': '詞彙表已重置為預設值'
            })
        else:
            return jsonify({'error': '重置詞彙表失敗'}), 500

    except Exception as e:
        logger.error(f"重置詞彙表失敗: {e}")
        return jsonify({'error': str(e)}), 500


@vocabulary_bp.route('/stats', methods=['GET'])
def get_vocabulary_stats():
    """獲取詞彙表統計信息"""
    try:
        vocab_config = get_vocabulary_config()
        if not vocab_config:
            return jsonify({'error': '詞彙配置不可用'}), 500

        terms = vocab_config.get_all_terms()

        # 統計
        total_terms = len(terms)
        total_corrections = sum(len(config.get('corrections', [])) for config in terms.values())

        # 按優先級分組
        priority_groups = {}
        for term, config in terms.items():
            priority = config.get('priority', 5)
            if priority not in priority_groups:
                priority_groups[priority] = 0
            priority_groups[priority] += 1

        # 按領域分類 (簡化版)
        categories = {
            'ai_ml': 0,
            'hardware': 0,
            'frameworks': 0,
            'protocols': 0,
            'others': 0
        }

        ai_ml_keywords = {'GPT', 'ChatGPT', 'LLM', 'AI', 'Agent', 'MCP', 'Whisper', 'Ollama', 'vLLM'}
        hardware_keywords = {'NVIDIA', 'CUDA', 'GPU', 'CPU', 'RTX'}
        framework_keywords = {'PyTorch', 'TensorFlow', 'Flask', 'React', 'Python', 'JavaScript'}
        protocol_keywords = {'API', 'REST', 'HTTP', 'JSON'}

        for term in terms.keys():
            if term in ai_ml_keywords:
                categories['ai_ml'] += 1
            elif term in hardware_keywords:
                categories['hardware'] += 1
            elif term in framework_keywords:
                categories['frameworks'] += 1
            elif term in protocol_keywords:
                categories['protocols'] += 1
            else:
                categories['others'] += 1

        return jsonify({
            'success': True,
            'stats': {
                'total_terms': total_terms,
                'total_corrections': total_corrections,
                'priority_distribution': priority_groups,
                'category_distribution': categories
            }
        })

    except Exception as e:
        logger.error(f"獲取統計信息失敗: {e}")
        return jsonify({'error': str(e)}), 500


@vocabulary_bp.route('/health', methods=['GET'])
def health_check():
    """健康檢查"""
    try:
        vocab_config = get_vocabulary_config()
        prompt_gen = get_prompt_generator()

        return jsonify({
            'success': True,
            'status': 'healthy',
            'vocabulary_config': 'available' if vocab_config else 'unavailable',
            'prompt_generator': 'available' if prompt_gen else 'unavailable'
        })

    except Exception as e:
        logger.error(f"健康檢查失敗: {e}")
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        }), 500
