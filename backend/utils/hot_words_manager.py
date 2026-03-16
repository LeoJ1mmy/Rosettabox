"""
Hot Words Manager - 管理 Whisper ASR 的熱詞/自訂詞彙
提高特定領域術語、人名、品牌名稱的識別準確度

Version 2.0 - 支援帶註解的熱詞結構
"""

import json
import os
import logging
from typing import List, Dict, Set, Optional, Tuple, Any, Union
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class HotWordEntry:
    """熱詞條目 - 包含詞彙、註解和別名"""
    word: str
    annotation: str = ""
    aliases: List[str] = field(default_factory=list)
    category: str = ""
    priority: str = "medium"

    def to_dict(self) -> Dict:
        """轉換為字典格式"""
        return {
            "word": self.word,
            "annotation": self.annotation,
            "aliases": self.aliases
        }

    @classmethod
    def from_dict(cls, data: Union[Dict, str], category: str = "", priority: str = "medium") -> "HotWordEntry":
        """從字典或字串創建條目（向下相容）"""
        if isinstance(data, str):
            # 向下相容：舊版本的簡單字串格式
            return cls(word=data, category=category, priority=priority)
        return cls(
            word=data.get("word", ""),
            annotation=data.get("annotation", ""),
            aliases=data.get("aliases", []),
            category=category,
            priority=priority
        )


class HotWordsManager:
    """熱詞管理器 - 支援帶註解的熱詞結構，內建 RAM 緩存"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化熱詞管理器

        Args:
            config_path: hot_words.json 的路徑，如果為 None 則使用默認路徑
        """
        if config_path is None:
            # 默認路徑：backend/config/hot_words.json
            backend_dir = Path(__file__).parent.parent
            config_path = backend_dir / "config" / "hot_words.json"

        self.config_path = Path(config_path)
        self.config: Dict = {}
        self.hot_words: Set[str] = set()
        self.hot_word_entries: Dict[str, HotWordEntry] = {}  # word -> HotWordEntry
        self.category_entries: Dict[str, List[HotWordEntry]] = {}  # category -> [entries]

        # 🚀 RAM 緩存：預計算優先級索引，避免重複遍歷
        self._priority_cache: Dict[str, List[str]] = {}  # priority -> [words]
        self._priority_entries_cache: Dict[str, List[HotWordEntry]] = {}  # priority -> [entries]
        self._whisper_prompt_cache: Optional[str] = None  # 緩存 Whisper prompt
        self._annotated_context_cache: Dict[str, str] = {}  # cache key -> context string

        self._load_config()

    def _load_config(self):
        """從 JSON 文件加載配置"""
        try:
            if not self.config_path.exists():
                logger.warning(f"Hot words config not found at {self.config_path}")
                return

            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)

            schema_version = self.config.get('schema_version', '1.0')
            logger.info(f"✅ Loaded hot words config from {self.config_path}")
            logger.info(f"📋 Config version: {self.config.get('version', 'unknown')}, Schema: {schema_version}")

            # 加載所有啟用的類別
            if self.config.get('global_settings', {}).get('auto_load_enabled_categories', True):
                self._load_enabled_categories()

        except Exception as e:
            logger.error(f"❌ Failed to load hot words config: {e}")

    def _load_enabled_categories(self):
        """加載所有啟用的類別的熱詞，並建立優先級緩存"""
        categories = self.config.get('categories', {})
        schema_version = self.config.get('schema_version', '1.0')

        # 🚀 初始化優先級緩存（包含 highest 優先級）
        self._priority_cache = {"highest": [], "high": [], "medium": [], "low": []}
        self._priority_entries_cache = {"highest": [], "high": [], "medium": [], "low": []}

        for category_name, category_data in categories.items():
            if category_data.get('enabled', False):
                priority = category_data.get('priority', 'medium')

                # 支援新版 terms 和舊版 words 兩種格式
                terms_data = category_data.get('terms', category_data.get('words', []))
                entries = []

                for term_data in terms_data:
                    entry = HotWordEntry.from_dict(term_data, category=category_name, priority=priority)
                    entries.append(entry)
                    self.hot_words.add(entry.word)
                    self.hot_word_entries[entry.word] = entry

                    # 🚀 同時更新優先級緩存
                    if priority in self._priority_cache:
                        self._priority_cache[priority].append(entry.word)
                        self._priority_entries_cache[priority].append(entry)

                    # 也將別名加入熱詞集合（用於 Whisper 識別）
                    if self.config.get('global_settings', {}).get('include_aliases_in_prompt', True):
                        for alias in entry.aliases:
                            self.hot_words.add(alias)

                self.category_entries[category_name] = entries
                logger.info(f"✅ Loaded {len(entries)} hot word entries from category '{category_name}' (priority: {priority})")

        # 🚀 清除其他緩存，因為數據已更新
        self._whisper_prompt_cache = None
        self._annotated_context_cache = {}

        logger.info(f"📊 Total hot words loaded: {len(self.hot_words)} (including aliases)")
        logger.info(f"📊 Total unique terms: {len(self.hot_word_entries)}")
        logger.info(f"📊 Priority cache: high={len(self._priority_cache.get('high', []))}, "
                   f"medium={len(self._priority_cache.get('medium', []))}, "
                   f"low={len(self._priority_cache.get('low', []))}")

    # ============================================================
    # 基本存取方法
    # ============================================================

    def get_all_hot_words(self) -> List[str]:
        """
        獲取所有熱詞列表（僅詞彙，不含註解）

        Returns:
            熱詞列表
        """
        return sorted(list(self.hot_words))

    def get_all_entries(self) -> List[HotWordEntry]:
        """
        獲取所有熱詞條目（含註解和別名）

        Returns:
            熱詞條目列表
        """
        return list(self.hot_word_entries.values())

    def get_entry(self, word: str) -> Optional[HotWordEntry]:
        """
        獲取指定詞彙的完整條目

        Args:
            word: 詞彙

        Returns:
            HotWordEntry 或 None
        """
        return self.hot_word_entries.get(word)

    def get_annotation(self, word: str) -> str:
        """
        獲取指定詞彙的註解

        Args:
            word: 詞彙

        Returns:
            註解字串，如果找不到則返回空字串
        """
        entry = self.hot_word_entries.get(word)
        return entry.annotation if entry else ""

    def get_aliases(self, word: str) -> List[str]:
        """
        獲取指定詞彙的別名列表

        Args:
            word: 詞彙

        Returns:
            別名列表
        """
        entry = self.hot_word_entries.get(word)
        return entry.aliases if entry else []

    # ============================================================
    # 類別相關方法
    # ============================================================

    def get_hot_words_by_category(self, category: str) -> List[str]:
        """
        獲取指定類別的熱詞（僅詞彙）

        Args:
            category: 類別名稱（technology, business, people 等）

        Returns:
            該類別的熱詞列表
        """
        entries = self.category_entries.get(category, [])
        return [e.word for e in entries]

    def get_entries_by_category(self, category: str) -> List[HotWordEntry]:
        """
        獲取指定類別的熱詞條目（含註解）

        Args:
            category: 類別名稱

        Returns:
            該類別的熱詞條目列表
        """
        return self.category_entries.get(category, [])

    def get_hot_words_by_priority(self, priority: str = "high") -> List[str]:
        """
        獲取指定優先級的熱詞（🚀 使用 RAM 緩存，O(1) 查找）

        Args:
            priority: 優先級（high, medium, low）

        Returns:
            指定優先級的熱詞列表
        """
        # 🚀 直接從緩存返回，避免遍歷所有類別
        return self._priority_cache.get(priority, [])

    def get_entries_by_priority(self, priority: str = "high") -> List[HotWordEntry]:
        """
        獲取指定優先級的熱詞條目（🚀 使用 RAM 緩存，O(1) 查找）

        Args:
            priority: 優先級（high, medium, low）

        Returns:
            指定優先級的熱詞條目列表
        """
        # 🚀 直接從緩存返回，避免遍歷所有類別
        return self._priority_entries_cache.get(priority, [])

    # ============================================================
    # 修改方法
    # ============================================================

    def add_hot_word(self, word: str, category: str = "custom",
                     annotation: str = "", aliases: List[str] = None):
        """
        動態添加熱詞

        Args:
            word: 要添加的熱詞
            category: 要添加到的類別（默認為 custom）
            annotation: 詞彙註解
            aliases: 別名列表
        """
        if aliases is None:
            aliases = []

        priority = self.config.get('categories', {}).get(category, {}).get('priority', 'high')
        entry = HotWordEntry(
            word=word,
            annotation=annotation,
            aliases=aliases,
            category=category,
            priority=priority
        )

        self.hot_words.add(word)
        self.hot_word_entries[word] = entry

        if category not in self.category_entries:
            self.category_entries[category] = []

        # 檢查是否已存在
        existing = [e for e in self.category_entries[category] if e.word == word]
        if not existing:
            self.category_entries[category].append(entry)

            # 🚀 更新優先級緩存
            if priority in self._priority_cache and word not in self._priority_cache[priority]:
                self._priority_cache[priority].append(word)
                self._priority_entries_cache[priority].append(entry)

            logger.info(f"✅ Added hot word '{word}' to category '{category}'")
        else:
            # 更新現有條目
            for e in self.category_entries[category]:
                if e.word == word:
                    e.annotation = annotation
                    e.aliases = aliases
            logger.info(f"✅ Updated hot word '{word}' in category '{category}'")

        # 🚀 清除相關緩存
        self._whisper_prompt_cache = None
        self._annotated_context_cache = {}

    def add_hot_words(self, words: List[Union[str, Dict]], category: str = "custom"):
        """
        批量添加熱詞

        Args:
            words: 要添加的熱詞列表（可以是字串或字典格式）
            category: 要添加到的類別（默認為 custom）
        """
        for word_data in words:
            if isinstance(word_data, str):
                self.add_hot_word(word_data, category)
            elif isinstance(word_data, dict):
                self.add_hot_word(
                    word=word_data.get('word', ''),
                    category=category,
                    annotation=word_data.get('annotation', ''),
                    aliases=word_data.get('aliases', [])
                )

        logger.info(f"✅ Added {len(words)} hot words to category '{category}'")

    def remove_hot_word(self, word: str):
        """
        移除熱詞

        Args:
            word: 要移除的熱詞
        """
        self.hot_words.discard(word)

        if word in self.hot_word_entries:
            del self.hot_word_entries[word]

        # 從所有類別中移除
        for category_name in self.category_entries:
            self.category_entries[category_name] = [
                e for e in self.category_entries[category_name] if e.word != word
            ]

        # 🚀 從優先級緩存中移除
        for priority in self._priority_cache:
            if word in self._priority_cache[priority]:
                self._priority_cache[priority].remove(word)
            self._priority_entries_cache[priority] = [
                e for e in self._priority_entries_cache[priority] if e.word != word
            ]

        # 🚀 清除相關緩存
        self._whisper_prompt_cache = None
        self._annotated_context_cache = {}

        logger.info(f"✅ Removed hot word '{word}'")

    def update_annotation(self, word: str, annotation: str):
        """
        更新詞彙的註解

        Args:
            word: 詞彙
            annotation: 新的註解
        """
        if word in self.hot_word_entries:
            self.hot_word_entries[word].annotation = annotation
            logger.info(f"✅ Updated annotation for '{word}'")
        else:
            logger.warning(f"⚠️ Word '{word}' not found")

    def update_aliases(self, word: str, aliases: List[str]):
        """
        更新詞彙的別名

        Args:
            word: 詞彙
            aliases: 新的別名列表
        """
        if word in self.hot_word_entries:
            old_aliases = self.hot_word_entries[word].aliases
            # 從熱詞集合中移除舊別名
            for alias in old_aliases:
                self.hot_words.discard(alias)
            # 添加新別名
            self.hot_word_entries[word].aliases = aliases
            for alias in aliases:
                self.hot_words.add(alias)
            logger.info(f"✅ Updated aliases for '{word}'")
        else:
            logger.warning(f"⚠️ Word '{word}' not found")

    # ============================================================
    # 類別啟用/禁用
    # ============================================================

    def enable_category(self, category: str):
        """
        啟用指定類別

        Args:
            category: 類別名稱
        """
        categories = self.config.get('categories', {})

        if category in categories:
            categories[category]['enabled'] = True

            priority = categories[category].get('priority', 'medium')
            terms_data = categories[category].get('terms', categories[category].get('words', []))
            entries = []

            for term_data in terms_data:
                entry = HotWordEntry.from_dict(term_data, category=category, priority=priority)
                entries.append(entry)
                self.hot_words.add(entry.word)
                self.hot_word_entries[entry.word] = entry

                # 🚀 更新優先級緩存
                if priority in self._priority_cache and entry.word not in self._priority_cache[priority]:
                    self._priority_cache[priority].append(entry.word)
                    self._priority_entries_cache[priority].append(entry)

                for alias in entry.aliases:
                    self.hot_words.add(alias)

            self.category_entries[category] = entries

            # 🚀 清除相關緩存
            self._whisper_prompt_cache = None
            self._annotated_context_cache = {}

            logger.info(f"✅ Enabled category '{category}' ({len(entries)} entries)")
        else:
            logger.warning(f"⚠️ Category '{category}' not found in config")

    def disable_category(self, category: str):
        """
        禁用指定類別

        Args:
            category: 類別名稱
        """
        categories = self.config.get('categories', {})

        if category in categories:
            categories[category]['enabled'] = False
            entries = self.category_entries.get(category, [])

            # 從熱詞集合中移除該類別的詞
            for entry in entries:
                self.hot_words.discard(entry.word)
                if entry.word in self.hot_word_entries:
                    del self.hot_word_entries[entry.word]

                # 🚀 從優先級緩存中移除
                priority = entry.priority
                if priority in self._priority_cache and entry.word in self._priority_cache[priority]:
                    self._priority_cache[priority].remove(entry.word)
                if priority in self._priority_entries_cache:
                    self._priority_entries_cache[priority] = [
                        e for e in self._priority_entries_cache[priority] if e.word != entry.word
                    ]

                for alias in entry.aliases:
                    self.hot_words.discard(alias)

            if category in self.category_entries:
                del self.category_entries[category]

            # 🚀 清除相關緩存
            self._whisper_prompt_cache = None
            self._annotated_context_cache = {}

            logger.info(f"✅ Disabled category '{category}'")
        else:
            logger.warning(f"⚠️ Category '{category}' not found in config")

    # ============================================================
    # 保存配置
    # ============================================================

    def save_config(self):
        """保存配置到 JSON 文件"""
        try:
            # 更新配置中的類別數據
            for category_name, entries in self.category_entries.items():
                if category_name in self.config.get('categories', {}):
                    self.config['categories'][category_name]['terms'] = [
                        e.to_dict() for e in entries
                    ]

            # 更新最後修改時間和版本
            from datetime import datetime
            self.config['last_updated'] = datetime.now().strftime('%Y-%m-%d')
            self.config['schema_version'] = '2.0'

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ Saved hot words config to {self.config_path}")

        except Exception as e:
            logger.error(f"❌ Failed to save hot words config: {e}")

    # ============================================================
    # Whisper 整合
    # ============================================================

    def get_whisper_initial_prompt(self, max_words: Optional[int] = None) -> str:
        """
        生成 Whisper 的 initial_prompt 參數（🚀 使用 RAM 緩存）

        Whisper 支持通過 initial_prompt 提供上下文詞彙來提高識別準確度

        Args:
            max_words: 最多包含多少個熱詞（None 表示使用配置中的限制）

        Returns:
            包含熱詞的 prompt 字符串
        """
        if max_words is None:
            max_words = self.config.get('global_settings', {}).get('max_words_per_request', 200)

        # 🚀 檢查緩存（僅當使用默認 max_words 時）
        if self._whisper_prompt_cache is not None and max_words == self.config.get('global_settings', {}).get('max_words_per_request', 200):
            return self._whisper_prompt_cache

        # 🔧 修復：優先使用所有優先級的熱詞（包含 highest）（🚀 O(1) 查找）
        highest_priority_words = self.get_hot_words_by_priority("highest")
        high_priority_words = self.get_hot_words_by_priority("high")
        medium_priority_words = self.get_hot_words_by_priority("medium")

        # 組合熱詞，優先級高的在前
        combined_words = highest_priority_words + high_priority_words + medium_priority_words

        # 限制數量
        selected_words = combined_words[:max_words]

        # 生成 prompt（用逗號分隔）
        prompt = ", ".join(selected_words)

        # 🚀 緩存結果（僅當使用默認 max_words 時）
        if max_words == self.config.get('global_settings', {}).get('max_words_per_request', 200):
            self._whisper_prompt_cache = prompt

        logger.info(f"📋 Generated Whisper initial_prompt with {len(selected_words)} hot words")

        return prompt

    # ============================================================
    # LLM 上下文生成（新增）
    # ============================================================

    def get_annotated_context(self, max_entries: int = 100,
                               include_aliases: bool = True,
                               format_type: str = "list") -> str:
        """
        生成帶註解的上下文字串，供 LLM 使用（🚀 使用 RAM 緩存）

        Args:
            max_entries: 最多包含多少個條目
            include_aliases: 是否包含別名
            format_type: 格式類型 ("list", "table", "json")

        Returns:
            格式化的上下文字串
        """
        # 🚀 建立緩存鍵
        cache_key = f"{max_entries}_{include_aliases}_{format_type}"
        if cache_key in self._annotated_context_cache:
            return self._annotated_context_cache[cache_key]

        # 🔧 修復：優先使用所有優先級（包含 highest）（🚀 O(1) 查找）
        highest_priority = self.get_entries_by_priority("highest")
        high_priority = self.get_entries_by_priority("high")
        medium_priority = self.get_entries_by_priority("medium")
        all_entries = highest_priority + high_priority + medium_priority
        selected = all_entries[:max_entries]

        if format_type == "json":
            result = self._format_as_json(selected, include_aliases)
        elif format_type == "table":
            result = self._format_as_table(selected, include_aliases)
        else:  # list
            result = self._format_as_list(selected, include_aliases)

        # 🚀 緩存結果
        self._annotated_context_cache[cache_key] = result
        return result

    def _format_as_list(self, entries: List[HotWordEntry], include_aliases: bool) -> str:
        """格式化為列表"""
        lines = ["術語參考列表："]
        for entry in entries:
            line = f"- {entry.word}"
            if entry.annotation:
                line += f": {entry.annotation}"
            if include_aliases and entry.aliases:
                line += f" (別名: {', '.join(entry.aliases)})"
            lines.append(line)
        return "\n".join(lines)

    def _format_as_table(self, entries: List[HotWordEntry], include_aliases: bool) -> str:
        """格式化為表格"""
        lines = ["| 術語 | 說明 |" + (" 別名 |" if include_aliases else "")]
        lines.append("|------|------|" + ("------|" if include_aliases else ""))
        for entry in entries:
            alias_col = f" {', '.join(entry.aliases)} |" if include_aliases else ""
            lines.append(f"| {entry.word} | {entry.annotation} |{alias_col}")
        return "\n".join(lines)

    def _format_as_json(self, entries: List[HotWordEntry], include_aliases: bool) -> str:
        """格式化為 JSON"""
        data = []
        for entry in entries:
            item = {"term": entry.word, "description": entry.annotation}
            if include_aliases and entry.aliases:
                item["aliases"] = entry.aliases
            data.append(item)
        return json.dumps(data, ensure_ascii=False, indent=2)

    def get_terms_with_annotations(self, category: Optional[str] = None) -> List[Tuple[str, str]]:
        """
        獲取詞彙與註解的配對列表

        Args:
            category: 可選的類別過濾

        Returns:
            [(word, annotation), ...] 列表
        """
        if category:
            entries = self.category_entries.get(category, [])
        else:
            entries = list(self.hot_word_entries.values())

        return [(e.word, e.annotation) for e in entries]

    # ============================================================
    # 搜尋功能
    # ============================================================

    def search(self, query: str, include_aliases: bool = True) -> List[HotWordEntry]:
        """
        搜尋熱詞（支援詞彙、註解、別名搜尋）

        Args:
            query: 搜尋關鍵字
            include_aliases: 是否搜尋別名

        Returns:
            符合的熱詞條目列表
        """
        query_lower = query.lower()
        results = []

        for entry in self.hot_word_entries.values():
            # 搜尋詞彙
            if query_lower in entry.word.lower():
                results.append(entry)
                continue

            # 搜尋註解
            if query_lower in entry.annotation.lower():
                results.append(entry)
                continue

            # 搜尋別名
            if include_aliases:
                for alias in entry.aliases:
                    if query_lower in alias.lower():
                        results.append(entry)
                        break

        return results

    # ============================================================
    # 統計信息
    # ============================================================

    def get_statistics(self) -> Dict:
        """
        獲取熱詞統計信息

        Returns:
            統計信息字典
        """
        import sys

        categories = self.config.get('categories', {})

        # 計算有註解的詞彙數量
        annotated_count = sum(1 for e in self.hot_word_entries.values() if e.annotation)
        total_aliases = sum(len(e.aliases) for e in self.hot_word_entries.values())

        # 🚀 計算 RAM 緩存使用量
        cache_stats = self._get_cache_stats()

        stats = {
            "total_words": len(self.hot_words),
            "total_unique_terms": len(self.hot_word_entries),
            "total_aliases": total_aliases,
            "annotated_terms": annotated_count,
            "unannotated_terms": len(self.hot_word_entries) - annotated_count,
            "total_categories": len(categories),
            "enabled_categories": sum(1 for c in categories.values() if c.get('enabled', False)),
            "disabled_categories": sum(1 for c in categories.values() if not c.get('enabled', False)),
            "highest_priority_words": len(self.get_hot_words_by_priority("highest")),
            "high_priority_words": len(self.get_hot_words_by_priority("high")),
            "medium_priority_words": len(self.get_hot_words_by_priority("medium")),
            "low_priority_words": len(self.get_hot_words_by_priority("low")),
            "schema_version": self.config.get('schema_version', '1.0'),
            "ram_cache": cache_stats,
            "category_breakdown": {
                name: {
                    "enabled": data.get('enabled', False),
                    "priority": data.get('priority', 'medium'),
                    "term_count": len(self.category_entries.get(name, [])),
                    "annotated": sum(1 for e in self.category_entries.get(name, []) if e.annotation)
                }
                for name, data in categories.items()
            }
        }

        return stats

    def _get_cache_stats(self) -> Dict:
        """🚀 獲取 RAM 緩存統計信息"""
        import sys

        # 估算各緩存的記憶體使用
        priority_cache_size = sum(sys.getsizeof(v) for v in self._priority_cache.values())
        priority_entries_size = sum(sys.getsizeof(v) for v in self._priority_entries_cache.values())
        whisper_cache_size = sys.getsizeof(self._whisper_prompt_cache) if self._whisper_prompt_cache else 0
        context_cache_size = sum(sys.getsizeof(v) for v in self._annotated_context_cache.values())

        total_cache_bytes = priority_cache_size + priority_entries_size + whisper_cache_size + context_cache_size

        return {
            "priority_cache_entries": sum(len(v) for v in self._priority_cache.values()),
            "priority_entries_cache_entries": sum(len(v) for v in self._priority_entries_cache.values()),
            "whisper_prompt_cached": self._whisper_prompt_cache is not None,
            "annotated_context_cached_keys": len(self._annotated_context_cache),
            "estimated_memory_bytes": total_cache_bytes,
            "estimated_memory_kb": round(total_cache_bytes / 1024, 2)
        }

    def print_statistics(self):
        """打印熱詞統計信息"""
        stats = self.get_statistics()

        print(f"\n{'='*60}")
        print(f"Hot Words Statistics (Schema v{stats['schema_version']})")
        print(f"{'='*60}")
        print(f"Total Words (incl. aliases): {stats['total_words']}")
        print(f"Unique Terms: {stats['total_unique_terms']}")
        print(f"Total Aliases: {stats['total_aliases']}")
        print(f"Annotated Terms: {stats['annotated_terms']}")
        print(f"Unannotated Terms: {stats['unannotated_terms']}")
        print(f"\nCategories: {stats['total_categories']}")
        print(f"  - Enabled: {stats['enabled_categories']}")
        print(f"  - Disabled: {stats['disabled_categories']}")
        print(f"\nBy Priority:")
        print(f"  - Highest: {stats['highest_priority_words']} words")
        print(f"  - High: {stats['high_priority_words']} words")
        print(f"  - Medium: {stats['medium_priority_words']} words")
        print(f"  - Low: {stats['low_priority_words']} words")

        # 🚀 顯示 RAM 緩存信息
        cache = stats.get('ram_cache', {})
        print(f"\n🚀 RAM Cache:")
        print(f"  - Priority cache entries: {cache.get('priority_cache_entries', 0)}")
        print(f"  - Whisper prompt cached: {cache.get('whisper_prompt_cached', False)}")
        print(f"  - Context cache keys: {cache.get('annotated_context_cached_keys', 0)}")
        print(f"  - Estimated memory: {cache.get('estimated_memory_kb', 0)} KB")

        print(f"\nCategory Breakdown:")

        for category, info in stats['category_breakdown'].items():
            status = "✅" if info['enabled'] else "❌"
            print(f"  {status} {category}: {info['term_count']} terms "
                  f"({info['annotated']} annotated, priority: {info['priority']})")

        print(f"{'='*60}\n")


# ============================================================
# 全局單例實例
# ============================================================

_hot_words_manager_instance: Optional[HotWordsManager] = None


def get_hot_words_manager() -> HotWordsManager:
    """
    獲取熱詞管理器的全局單例

    Returns:
        HotWordsManager 實例
    """
    global _hot_words_manager_instance

    if _hot_words_manager_instance is None:
        _hot_words_manager_instance = HotWordsManager()

    return _hot_words_manager_instance


def reset_hot_words_manager():
    """重置熱詞管理器單例（用於測試或重新加載配置）"""
    global _hot_words_manager_instance
    _hot_words_manager_instance = None


# ============================================================
# 便捷函數
# ============================================================

def get_hot_words() -> List[str]:
    """獲取所有熱詞"""
    return get_hot_words_manager().get_all_hot_words()


def get_whisper_prompt() -> str:
    """獲取 Whisper initial_prompt"""
    return get_hot_words_manager().get_whisper_initial_prompt()


def get_annotated_context(max_entries: int = 100, format_type: str = "list") -> str:
    """獲取帶註解的上下文"""
    return get_hot_words_manager().get_annotated_context(max_entries, format_type=format_type)


def add_hot_words(words: List[Union[str, Dict]], category: str = "custom"):
    """添加熱詞"""
    get_hot_words_manager().add_hot_words(words, category)


def get_annotation(word: str) -> str:
    """獲取詞彙的註解"""
    return get_hot_words_manager().get_annotation(word)


def search_hot_words(query: str) -> List[HotWordEntry]:
    """搜尋熱詞"""
    return get_hot_words_manager().search(query)


# ============================================================
# CLI 測試
# ============================================================

if __name__ == "__main__":
    # 測試熱詞管理器
    manager = HotWordsManager()

    # 打印統計信息
    manager.print_statistics()

    # 測試獲取熱詞
    print(f"All hot words ({len(manager.get_all_hot_words())}):")
    print(f"  {', '.join(manager.get_all_hot_words()[:20])}...")

    # 測試生成 Whisper prompt
    print(f"\nWhisper initial_prompt:")
    prompt = manager.get_whisper_initial_prompt(max_words=50)
    print(f"  {prompt[:200]}...")

    # 測試獲取註解
    print(f"\nTest get_annotation:")
    for word in ["LLM", "GPT", "Docker"]:
        annotation = manager.get_annotation(word)
        print(f"  {word}: {annotation}")

    # 測試帶註解的上下文
    print(f"\nAnnotated context (list format):")
    context = manager.get_annotated_context(max_entries=5, format_type="list")
    print(context)

    # 測試搜尋
    print(f"\nSearch test (query='AI'):")
    results = manager.search("AI")
    for entry in results[:5]:
        print(f"  - {entry.word}: {entry.annotation[:50]}...")
