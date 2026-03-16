"""
自定義詞彙配置 - 用於修正語音識別中的技術術語錯誤
Custom Vocabulary Configuration for Speech Recognition Error Correction
"""
import json
import os
import logging
from typing import Dict, List, Set, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class VocabularyConfig:
    """詞彙配置管理器"""

    # 預設技術詞彙庫 - 包含常見的技術術語及其可能的錯誤拼寫
    DEFAULT_VOCABULARY = {
        # AI/ML 相關
        "GPT": {
            "corrections": ["G P T", "gpt", "g.p.t.", "gee pee tee", "jpt", "gp t"],
            "context": ["ai", "model", "language", "chat", "openai"],
            "priority": 10,
            "case_sensitive": True
        },
        "ChatGPT": {
            "corrections": ["chat gpt", "chat g p t", "chatgpt", "chat GPT"],
            "context": ["ai", "openai", "conversation"],
            "priority": 10,
            "case_sensitive": False
        },
        "LLM": {
            "corrections": ["L L M", "l.l.m.", "llm", "L.L.M.", "el el em"],
            "context": ["model", "language", "ai", "large"],
            "priority": 9,
            "case_sensitive": True
        },
        "AI": {
            "corrections": ["A I", "a.i.", "A.I.", "ay eye"],
            "context": ["artificial", "intelligence", "machine", "learning"],
            "priority": 8,
            "case_sensitive": True
        },
        "MCP": {
            "corrections": ["M C P", "m.c.p.", "M.C.P.", "em cee pee"],
            "context": ["protocol", "model", "context"],
            "priority": 9,
            "case_sensitive": True
        },
        "Agent": {
            "corrections": ["ajent", "agant", "eigent"],
            "context": ["ai", "autonomous", "intelligent"],
            "priority": 7,
            "case_sensitive": False
        },

        # 硬體/平台相關
        "NVIDIA": {
            "corrections": ["in video", "nvidia", "n video", "N video", "en video"],
            "context": ["gpu", "cuda", "graphics", "rtx"],
            "priority": 10,
            "case_sensitive": True
        },
        "CUDA": {
            "corrections": ["cuda", "C U D A", "c.u.d.a.", "cooda"],
            "context": ["nvidia", "gpu", "parallel", "computing"],
            "priority": 9,
            "case_sensitive": True
        },
        "GPU": {
            "corrections": ["G P U", "g.p.u.", "gee pee you", "gpus"],
            "context": ["graphics", "nvidia", "cuda", "processing"],
            "priority": 9,
            "case_sensitive": True
        },
        "CPU": {
            "corrections": ["C P U", "c.p.u.", "see pee you", "cpus"],
            "context": ["processor", "intel", "amd", "computing"],
            "priority": 8,
            "case_sensitive": True
        },
        "RTX": {
            "corrections": ["R T X", "r.t.x.", "R.T.X.", "artex"],
            "context": ["nvidia", "gpu", "graphics", "5070"],
            "priority": 8,
            "case_sensitive": True
        },

        # 框架/工具相關
        "PyTorch": {
            "corrections": ["py torch", "pytorch", "pie torch", "pi torch"],
            "context": ["deep", "learning", "neural", "network"],
            "priority": 9,
            "case_sensitive": False
        },
        "TensorFlow": {
            "corrections": ["tensor flow", "tensorflow", "tenser flow"],
            "context": ["google", "machine", "learning", "neural"],
            "priority": 9,
            "case_sensitive": False
        },
        "Whisper": {
            "corrections": ["whisper", "wisper", "whisperer"],
            "context": ["openai", "speech", "transcription", "audio"],
            "priority": 10,
            "case_sensitive": False
        },
        "Ollama": {
            "corrections": ["ollama", "olama", "o lama", "oh lama"],
            "context": ["llm", "model", "local", "inference"],
            "priority": 9,
            "case_sensitive": False
        },
        "vLLM": {
            "corrections": ["v llm", "V LLM", "v L L M", "vllm"],
            "context": ["inference", "server", "model", "fast"],
            "priority": 9,
            "case_sensitive": False
        },
        "Flask": {
            "corrections": ["flask", "flasks", "flasque"],
            "context": ["python", "web", "framework", "api"],
            "priority": 7,
            "case_sensitive": False
        },
        "React": {
            "corrections": ["react", "re-act", "reakt"],
            "context": ["javascript", "frontend", "component", "ui"],
            "priority": 7,
            "case_sensitive": False
        },

        # 協議/標準相關
        "API": {
            "corrections": ["A P I", "a.p.i.", "A.P.I.", "ay pee eye"],
            "context": ["interface", "rest", "endpoint", "http"],
            "priority": 8,
            "case_sensitive": True
        },
        "REST": {
            "corrections": ["R E S T", "rest", "r.e.s.t."],
            "context": ["api", "http", "web", "service"],
            "priority": 7,
            "case_sensitive": True
        },
        "HTTP": {
            "corrections": ["H T T P", "h.t.t.p.", "aitch tee tee pee"],
            "context": ["protocol", "web", "request", "api"],
            "priority": 8,
            "case_sensitive": True
        },
        "JSON": {
            "corrections": ["J S O N", "j.s.o.n.", "jason", "jay son"],
            "context": ["data", "format", "api", "javascript"],
            "priority": 8,
            "case_sensitive": True
        },

        # 語言/技術相關
        "Python": {
            "corrections": ["python", "pyton", "pithon"],
            "context": ["programming", "language", "code", "script"],
            "priority": 7,
            "case_sensitive": False
        },
        "JavaScript": {
            "corrections": ["java script", "javascript", "jscript"],
            "context": ["programming", "web", "frontend", "node"],
            "priority": 7,
            "case_sensitive": False
        },
        "TypeScript": {
            "corrections": ["type script", "typescript", "ts"],
            "context": ["javascript", "typed", "programming", "microsoft"],
            "priority": 7,
            "case_sensitive": False
        },

        # 公司/組織相關
        "OpenAI": {
            "corrections": ["open ai", "open A I", "openai", "open a.i."],
            "context": ["gpt", "chatgpt", "whisper", "ai"],
            "priority": 9,
            "case_sensitive": False
        },
        "Google": {
            "corrections": ["google", "gogle", "googel"],
            "context": ["search", "cloud", "tensorflow", "ai"],
            "priority": 6,
            "case_sensitive": False
        },
        "Microsoft": {
            "corrections": ["microsoft", "micro soft", "MS"],
            "context": ["windows", "azure", "copilot", "office"],
            "priority": 6,
            "case_sensitive": False
        },

        # 資料庫/儲存相關
        "PostgreSQL": {
            "corrections": ["postgres", "post gres", "postgresql", "postgre sql"],
            "context": ["database", "sql", "relational", "data"],
            "priority": 7,
            "case_sensitive": False
        },
        "MongoDB": {
            "corrections": ["mongo db", "mongo", "mongodb"],
            "context": ["database", "nosql", "document", "json"],
            "priority": 7,
            "case_sensitive": False
        },
        "Redis": {
            "corrections": ["redis", "reedis", "read is"],
            "context": ["cache", "database", "memory", "key"],
            "priority": 7,
            "case_sensitive": False
        },
    }

    def __init__(self, config_dir: str = "./config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "custom_vocabulary.json"

        # 載入或初始化詞彙表
        self.vocabulary = self._load_vocabulary()

        # 建立快速查找索引
        self._build_lookup_index()

        logger.info(f"✅ 詞彙配置已載入: {len(self.vocabulary)} 個術語")

    def _load_vocabulary(self) -> Dict:
        """載入詞彙配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    custom_vocab = json.load(f)
                    # 合併預設詞彙和自定義詞彙
                    merged = self.DEFAULT_VOCABULARY.copy()
                    merged.update(custom_vocab)
                    logger.info(f"📚 載入自定義詞彙: {len(custom_vocab)} 個")
                    return merged
            except Exception as e:
                logger.error(f"❌ 載入自定義詞彙失敗: {e}")
                return self.DEFAULT_VOCABULARY.copy()
        else:
            # 首次運行，保存預設詞彙
            self._save_vocabulary(self.DEFAULT_VOCABULARY)
            return self.DEFAULT_VOCABULARY.copy()

    def _save_vocabulary(self, vocab: Dict):
        """保存詞彙配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(vocab, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 詞彙配置已保存: {len(vocab)} 個術語")
        except Exception as e:
            logger.error(f"❌ 保存詞彙配置失敗: {e}")

    def _build_lookup_index(self):
        """建立快速查找索引"""
        self.correction_map = {}  # 錯誤拼寫 -> 正確術語
        self.context_map = {}     # 術語 -> 上下文關鍵詞
        self.priority_map = {}    # 術語 -> 優先級

        for correct_term, config in self.vocabulary.items():
            # 建立修正映射
            for incorrect in config.get("corrections", []):
                # 儲存多個可能的正確術語（以優先級排序）
                if incorrect.lower() not in self.correction_map:
                    self.correction_map[incorrect.lower()] = []
                self.correction_map[incorrect.lower()].append({
                    "term": correct_term,
                    "priority": config.get("priority", 5),
                    "case_sensitive": config.get("case_sensitive", False)
                })

            # 建立上下文映射
            self.context_map[correct_term.lower()] = [
                ctx.lower() for ctx in config.get("context", [])
            ]

            # 建立優先級映射
            self.priority_map[correct_term.lower()] = config.get("priority", 5)

        # 按優先級排序修正映射
        for key in self.correction_map:
            self.correction_map[key].sort(key=lambda x: x["priority"], reverse=True)

    def add_term(self, term: str, corrections: List[str],
                 context: List[str] = None, priority: int = 5,
                 case_sensitive: bool = False) -> bool:
        """添加新術語"""
        try:
            self.vocabulary[term] = {
                "corrections": corrections,
                "context": context or [],
                "priority": priority,
                "case_sensitive": case_sensitive
            }
            self._save_vocabulary(self.vocabulary)
            self._build_lookup_index()
            logger.info(f"✅ 已添加術語: {term}")
            return True
        except Exception as e:
            logger.error(f"❌ 添加術語失敗: {e}")
            return False

    def remove_term(self, term: str) -> bool:
        """移除術語"""
        try:
            if term in self.vocabulary:
                del self.vocabulary[term]
                self._save_vocabulary(self.vocabulary)
                self._build_lookup_index()
                logger.info(f"🗑️ 已移除術語: {term}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ 移除術語失敗: {e}")
            return False

    def update_term(self, term: str, **kwargs) -> bool:
        """更新術語配置"""
        try:
            if term not in self.vocabulary:
                return False

            self.vocabulary[term].update(kwargs)
            self._save_vocabulary(self.vocabulary)
            self._build_lookup_index()
            logger.info(f"✏️ 已更新術語: {term}")
            return True
        except Exception as e:
            logger.error(f"❌ 更新術語失敗: {e}")
            return False

    def get_all_terms(self) -> Dict:
        """獲取所有術語"""
        return self.vocabulary.copy()

    def get_term(self, term: str) -> Optional[Dict]:
        """獲取特定術語配置"""
        return self.vocabulary.get(term)

    def export_vocabulary(self, file_path: str) -> bool:
        """導出詞彙表"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.vocabulary, f, ensure_ascii=False, indent=2)
            logger.info(f"📤 詞彙表已導出: {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ 導出詞彙表失敗: {e}")
            return False

    def import_vocabulary(self, file_path: str, merge: bool = True) -> bool:
        """導入詞彙表"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_vocab = json.load(f)

            if merge:
                self.vocabulary.update(imported_vocab)
            else:
                self.vocabulary = imported_vocab

            self._save_vocabulary(self.vocabulary)
            self._build_lookup_index()
            logger.info(f"📥 詞彙表已導入: {len(imported_vocab)} 個術語")
            return True
        except Exception as e:
            logger.error(f"❌ 導入詞彙表失敗: {e}")
            return False

    def reset_to_default(self) -> bool:
        """重置為預設詞彙表"""
        try:
            self.vocabulary = self.DEFAULT_VOCABULARY.copy()
            self._save_vocabulary(self.vocabulary)
            self._build_lookup_index()
            logger.info("🔄 詞彙表已重置為預設值")
            return True
        except Exception as e:
            logger.error(f"❌ 重置詞彙表失敗: {e}")
            return False


# 全局實例
vocabulary_config = VocabularyConfig()
