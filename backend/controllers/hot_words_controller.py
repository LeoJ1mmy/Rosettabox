"""
Hot Words Admin API Controller
提供密碼保護的熱詞 CRUD 操作
"""
from flask import Blueprint, request
from functools import wraps
import logging
import secrets  # 🔒 安全導入：用於恆定時間比較

from utils.api_response import APIResponse
from utils.hot_words_manager import get_hot_words_manager

logger = logging.getLogger(__name__)

hot_words_bp = Blueprint('hot_words', __name__, url_prefix='/api/admin/hot-words')


# ============== Authentication ==============

def require_admin_auth(f):
    """Admin password authentication decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check X-Admin-Password header
        auth_header = request.headers.get('X-Admin-Password')

        if not auth_header:
            return APIResponse.unauthorized("缺少管理員密碼")

        # Get password from config
        from config import config
        admin_password = config.ADMIN_PASSWORD

        if not admin_password:
            return APIResponse.error(
                "管理員密碼未配置",
                code=503,
                error_code="ADMIN_NOT_CONFIGURED"
            )

        # 🔒 使用恆定時間比較防止時序攻擊
        if not secrets.compare_digest(auth_header, admin_password):
            return APIResponse.forbidden("管理員密碼錯誤")

        return f(*args, **kwargs)

    return decorated_function


# ============== Password Verification ==============

@hot_words_bp.route('/verify', methods=['POST'])
def verify_admin_password():
    """Verify admin password without exposing it"""
    try:
        data = request.get_json() or {}
        password = data.get('password', '')

        from config import config
        admin_password = config.ADMIN_PASSWORD

        if not admin_password:
            return APIResponse.error(
                "管理員功能未啟用",
                code=503,
                error_code="ADMIN_NOT_CONFIGURED"
            )

        # 🔒 使用恆定時間比較防止時序攻擊
        if secrets.compare_digest(password, admin_password):
            return APIResponse.success(
                data={'verified': True},
                message="密碼驗證成功"
            )
        else:
            return APIResponse.forbidden("密碼錯誤")

    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return APIResponse.error("驗證失敗", code=500)


# ============== Categories ==============

@hot_words_bp.route('/categories', methods=['GET'])
@require_admin_auth
def get_categories():
    """Get all categories with their enabled status"""
    try:
        manager = get_hot_words_manager()
        categories = manager.config.get('categories', {})

        result = []
        for name, data in categories.items():
            # Count terms from config (not just loaded ones)
            terms = data.get('terms', data.get('words', []))
            result.append({
                'name': name,
                'enabled': data.get('enabled', False),
                'priority': data.get('priority', 'medium'),
                'description': data.get('description', ''),
                'term_count': len(terms)
            })

        return APIResponse.success(
            data={'categories': result},
            message="類別列表獲取成功"
        )
    except Exception as e:
        logger.error(f"Get categories failed: {e}")
        return APIResponse.error(f"獲取類別失敗: {str(e)}", code=500)


@hot_words_bp.route('/categories/<category>/toggle', methods=['POST'])
@require_admin_auth
def toggle_category(category: str):
    """Enable or disable a category"""
    try:
        manager = get_hot_words_manager()
        categories = manager.config.get('categories', {})

        if category not in categories:
            return APIResponse.not_found(f"類別 '{category}'")

        current_status = categories[category].get('enabled', False)

        if current_status:
            manager.disable_category(category)
        else:
            manager.enable_category(category)

        manager.save_config()

        return APIResponse.success(
            data={
                'category': category,
                'enabled': not current_status
            },
            message=f"類別 '{category}' 已{'停用' if current_status else '啟用'}"
        )
    except Exception as e:
        logger.error(f"Toggle category failed: {e}")
        return APIResponse.error(f"切換類別失敗: {str(e)}", code=500)


# ============== Entries CRUD ==============

@hot_words_bp.route('/entries', methods=['GET'])
@require_admin_auth
def get_all_entries():
    """Get all hot word entries from all categories"""
    try:
        manager = get_hot_words_manager()

        # Get entries from config (including disabled categories)
        categories = manager.config.get('categories', {})
        all_entries = []

        for cat_name, cat_data in categories.items():
            terms = cat_data.get('terms', cat_data.get('words', []))
            for term in terms:
                if isinstance(term, dict):
                    all_entries.append({
                        'word': term.get('word', ''),
                        'annotation': term.get('annotation', ''),
                        'aliases': term.get('aliases', []),
                        'category': cat_name,
                        'priority': cat_data.get('priority', 'medium'),
                        'category_enabled': cat_data.get('enabled', False)
                    })
                else:
                    # Legacy string format
                    all_entries.append({
                        'word': term,
                        'annotation': '',
                        'aliases': [],
                        'category': cat_name,
                        'priority': cat_data.get('priority', 'medium'),
                        'category_enabled': cat_data.get('enabled', False)
                    })

        return APIResponse.success(
            data={
                'entries': all_entries,
                'total_count': len(all_entries)
            },
            message="熱詞列表獲取成功"
        )
    except Exception as e:
        logger.error(f"Get entries failed: {e}")
        return APIResponse.error(f"獲取熱詞失敗: {str(e)}", code=500)


@hot_words_bp.route('/entries', methods=['POST'])
@require_admin_auth
def add_entry():
    """Add a new hot word entry"""
    try:
        data = request.get_json() or {}

        word = data.get('word', '').strip()
        category = data.get('category', 'custom')
        annotation = data.get('annotation', '')
        aliases = data.get('aliases', [])

        if not word:
            return APIResponse.validation_error("詞彙不能為空")

        manager = get_hot_words_manager()

        # Check if category exists, if not and it's not custom, return error
        categories = manager.config.get('categories', {})
        if category not in categories:
            return APIResponse.not_found(f"類別 '{category}'")

        # Check if word already exists in the config
        for cat_name, cat_data in categories.items():
            terms = cat_data.get('terms', cat_data.get('words', []))
            for term in terms:
                term_word = term.get('word', '') if isinstance(term, dict) else term
                if term_word == word:
                    return APIResponse.error(
                        f"詞彙 '{word}' 已存在於類別 '{cat_name}'",
                        code=409,
                        error_code="DUPLICATE_ENTRY"
                    )

        # Add to config directly
        if 'terms' not in categories[category]:
            categories[category]['terms'] = categories[category].get('words', [])

        categories[category]['terms'].append({
            'word': word,
            'annotation': annotation,
            'aliases': aliases if isinstance(aliases, list) else []
        })

        # If category is enabled, also add to manager's runtime data
        if categories[category].get('enabled', False):
            manager.add_hot_word(word, category, annotation, aliases)

        manager.save_config()

        return APIResponse.success(
            data={'word': word, 'category': category},
            message=f"熱詞 '{word}' 已添加",
            code=201
        )
    except Exception as e:
        logger.error(f"Add entry failed: {e}")
        return APIResponse.error(f"添加熱詞失敗: {str(e)}", code=500)


@hot_words_bp.route('/entries/<path:word>', methods=['PUT'])
@require_admin_auth
def update_entry(word: str):
    """Update a hot word entry"""
    try:
        data = request.get_json() or {}

        manager = get_hot_words_manager()
        categories = manager.config.get('categories', {})

        # Find the entry in config
        found = False
        target_category = None

        for cat_name, cat_data in categories.items():
            terms = cat_data.get('terms', cat_data.get('words', []))
            for i, term in enumerate(terms):
                term_word = term.get('word', '') if isinstance(term, dict) else term
                if term_word == word:
                    found = True
                    target_category = cat_name

                    # Update the term
                    if isinstance(term, dict):
                        if 'annotation' in data:
                            terms[i]['annotation'] = data['annotation']
                        if 'aliases' in data:
                            terms[i]['aliases'] = data['aliases'] if isinstance(data['aliases'], list) else []
                    else:
                        # Convert to dict format
                        terms[i] = {
                            'word': word,
                            'annotation': data.get('annotation', ''),
                            'aliases': data.get('aliases', [])
                        }
                    break
            if found:
                break

        if not found:
            return APIResponse.not_found(f"詞彙 '{word}'")

        # If category is enabled, also update in manager's runtime data
        if categories[target_category].get('enabled', False):
            if 'annotation' in data:
                manager.update_annotation(word, data['annotation'])
            if 'aliases' in data:
                manager.update_aliases(word, data['aliases'])

        manager.save_config()

        return APIResponse.success(
            data={'word': word},
            message=f"熱詞 '{word}' 已更新"
        )
    except Exception as e:
        logger.error(f"Update entry failed: {e}")
        return APIResponse.error(f"更新熱詞失敗: {str(e)}", code=500)


@hot_words_bp.route('/entries/<path:word>', methods=['DELETE'])
@require_admin_auth
def delete_entry(word: str):
    """Delete a hot word entry"""
    try:
        manager = get_hot_words_manager()
        categories = manager.config.get('categories', {})

        # Find and remove from config
        found = False
        target_category = None

        for cat_name, cat_data in categories.items():
            terms = cat_data.get('terms', cat_data.get('words', []))
            for i, term in enumerate(terms):
                term_word = term.get('word', '') if isinstance(term, dict) else term
                if term_word == word:
                    found = True
                    target_category = cat_name
                    terms.pop(i)
                    break
            if found:
                break

        if not found:
            return APIResponse.not_found(f"詞彙 '{word}'")

        # Also remove from manager's runtime data
        manager.remove_hot_word(word)
        manager.save_config()

        return APIResponse.success(
            data={'word': word},
            message=f"熱詞 '{word}' 已刪除"
        )
    except Exception as e:
        logger.error(f"Delete entry failed: {e}")
        return APIResponse.error(f"刪除熱詞失敗: {str(e)}", code=500)


# ============== Search & Statistics ==============

@hot_words_bp.route('/search', methods=['GET'])
@require_admin_auth
def search_entries():
    """Search hot words"""
    try:
        query = request.args.get('q', '')

        if not query:
            return APIResponse.validation_error("搜尋關鍵字不能為空")

        manager = get_hot_words_manager()

        # Search in config (all categories, not just enabled)
        categories = manager.config.get('categories', {})
        results = []
        query_lower = query.lower()

        for cat_name, cat_data in categories.items():
            terms = cat_data.get('terms', cat_data.get('words', []))
            for term in terms:
                if isinstance(term, dict):
                    word = term.get('word', '')
                    annotation = term.get('annotation', '')
                    aliases = term.get('aliases', [])
                else:
                    word = term
                    annotation = ''
                    aliases = []

                # Match word, annotation, or aliases
                if (query_lower in word.lower() or
                    query_lower in annotation.lower() or
                    any(query_lower in a.lower() for a in aliases)):
                    results.append({
                        'word': word,
                        'annotation': annotation,
                        'aliases': aliases,
                        'category': cat_name,
                        'priority': cat_data.get('priority', 'medium'),
                        'category_enabled': cat_data.get('enabled', False)
                    })

        return APIResponse.success(
            data={
                'query': query,
                'results': results,
                'count': len(results)
            },
            message=f"找到 {len(results)} 個結果"
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return APIResponse.error(f"搜尋失敗: {str(e)}", code=500)


@hot_words_bp.route('/statistics', methods=['GET'])
@require_admin_auth
def get_statistics():
    """Get hot words statistics"""
    try:
        manager = get_hot_words_manager()
        stats = manager.get_statistics()

        return APIResponse.success(
            data=stats,
            message="統計信息獲取成功"
        )
    except Exception as e:
        logger.error(f"Get statistics failed: {e}")
        return APIResponse.error(f"獲取統計失敗: {str(e)}", code=500)
