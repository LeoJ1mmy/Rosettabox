"""
詞彙表 Initial Prompt 生成器
將技術詞彙表轉換為 Whisper 的 initial_prompt，提高識別準確度
"""
import logging
from typing import List, Dict, Set, Optional
import random

logger = logging.getLogger(__name__)


class VocabularyPromptGenerator:
    """生成 Whisper initial_prompt 的智能生成器"""

    # 預設的句子模板 - 用於將詞彙包裝成自然句子
    SENTENCE_TEMPLATES = [
        # AI/ML 領域
        "In this conversation, we will discuss {terms} and related AI technologies.",
        "The speakers might mention {terms} when talking about machine learning.",
        "This recording includes technical terms like {terms}.",
        "We are going to talk about {terms} in the context of artificial intelligence.",

        # 技術討論
        "The discussion involves {terms} and software development.",
        "Topics covered include {terms} and their applications.",
        "Key technologies mentioned: {terms}.",

        # 通用技術
        "Technical terms in this audio: {terms}.",
        "This session covers {terms} and related concepts.",
    ]

    # 按領域分類的連接詞
    CATEGORY_CONNECTORS = {
        "ai_ml": ["AI models like", "frameworks such as", "using", "with"],
        "hardware": ["on", "with", "using", "powered by"],
        "tools": ["using", "with", "through", "via"],
        "companies": ["from", "by", "including"],
        "protocols": ["via", "using", "through", "with"]
    }

    def __init__(self, vocabulary_config=None):
        """
        初始化 prompt 生成器

        Args:
            vocabulary_config: VocabularyConfig 實例
        """
        if vocabulary_config is None:
            from vocabulary.vocabulary_config import vocabulary_config as vc
            vocabulary_config = vc

        self.vocabulary_config = vocabulary_config
        logger.info("✅ Vocabulary Prompt Generator 已初始化")

    def generate_prompt(self,
                       terms: List[str] = None,
                       max_terms: int = 15,
                       context_aware: bool = True,
                       template: str = None,
                       language: str = "english") -> str:
        """
        生成 Whisper initial_prompt

        Args:
            terms: 指定要包含的術語列表（如果為 None，則使用所有高優先級術語）
            max_terms: 最多包含的術語數量
            context_aware: 是否根據上下文智能分組術語
            template: 自定義模板（如果為 None，則隨機選擇）
            language: 語言（'english' 或 'chinese'）

        Returns:
            生成的 initial_prompt 字符串
        """
        try:
            # 1. 選擇術語
            if terms is None:
                selected_terms = self._select_high_priority_terms(max_terms)
            else:
                # 驗證提供的術語是否在詞彙表中
                valid_terms = []
                for term in terms:
                    if term in self.vocabulary_config.vocabulary:
                        valid_terms.append(term)
                    else:
                        logger.warning(f"術語不在詞彙表中: {term}")
                selected_terms = valid_terms[:max_terms]

            if not selected_terms:
                logger.warning("沒有可用的術語，返回空 prompt")
                return ""

            # 2. 生成 prompt
            if language == "chinese":
                prompt = self._generate_chinese_prompt(selected_terms, template)
            else:
                prompt = self._generate_english_prompt(selected_terms, context_aware, template)

            logger.info(f"✅ 生成 prompt ({len(selected_terms)} 個術語, {len(prompt)} 字符)")
            logger.debug(f"Prompt: {prompt}")

            return prompt

        except Exception as e:
            logger.error(f"❌ 生成 prompt 失敗: {e}")
            return ""

    def _select_high_priority_terms(self, max_terms: int = 15) -> List[str]:
        """選擇高優先級的術語"""
        # 按優先級排序所有術語
        terms_with_priority = []
        for term, config in self.vocabulary_config.vocabulary.items():
            priority = config.get("priority", 5)
            terms_with_priority.append((term, priority))

        # 按優先級降序排序
        terms_with_priority.sort(key=lambda x: x[1], reverse=True)

        # 選擇前 N 個
        selected = [term for term, _ in terms_with_priority[:max_terms]]

        logger.info(f"選擇了 {len(selected)} 個高優先級術語")
        return selected

    def _generate_english_prompt(self,
                                 terms: List[str],
                                 context_aware: bool = True,
                                 template: str = None) -> str:
        """生成英文 prompt"""
        if context_aware:
            # 根據上下文將術語分組
            grouped_terms = self._group_terms_by_context(terms)
            # 構建更自然的句子
            prompt = self._build_contextual_sentence(grouped_terms)
        else:
            # 簡單地用逗號連接
            terms_str = ", ".join(terms)

            # 選擇模板
            if template is None:
                template = random.choice(self.SENTENCE_TEMPLATES)

            prompt = template.format(terms=terms_str)

        return prompt

    def _generate_chinese_prompt(self, terms: List[str], template: str = None) -> str:
        """生成中文 prompt - 針對中英混合語音優化"""
        terms_str = "、".join(terms)

        # 中英混合優化模板 - 明確標注英文技術術語
        chinese_templates = [
            f"這段中文對話包含以下英文技術術語：{terms_str}。請正確識別這些英文單詞。",
            f"本段錄音為中英混合語音，涉及 {terms_str} 等英文專業術語。",
            f"對話內容為中文，但包含 {terms_str} 等英文技術名詞，請準確轉錄。",
            f"這是一段技術討論，會提到 {terms_str} 等英文術語。",
        ]

        if template is None:
            template = random.choice(chinese_templates)
            return template
        else:
            return template.format(terms=terms_str)

    def _group_terms_by_context(self, terms: List[str]) -> Dict[str, List[str]]:
        """根據上下文將術語分組"""
        groups = {
            "ai_ml": [],
            "hardware": [],
            "frameworks": [],
            "companies": [],
            "protocols": [],
            "others": []
        }

        # 定義分類規則
        ai_ml_keywords = {"GPT", "ChatGPT", "LLM", "AI", "Agent", "MCP", "Whisper", "Ollama", "vLLM"}
        hardware_keywords = {"NVIDIA", "CUDA", "GPU", "CPU", "RTX"}
        framework_keywords = {"PyTorch", "TensorFlow", "Flask", "React", "TypeScript", "JavaScript", "Python"}
        company_keywords = {"OpenAI", "Google", "Microsoft"}
        protocol_keywords = {"API", "REST", "HTTP", "JSON"}

        for term in terms:
            if term in ai_ml_keywords:
                groups["ai_ml"].append(term)
            elif term in hardware_keywords:
                groups["hardware"].append(term)
            elif term in framework_keywords:
                groups["frameworks"].append(term)
            elif term in company_keywords:
                groups["companies"].append(term)
            elif term in protocol_keywords:
                groups["protocols"].append(term)
            else:
                groups["others"].append(term)

        # 移除空組
        groups = {k: v for k, v in groups.items() if v}

        return groups

    def _build_contextual_sentence(self, grouped_terms: Dict[str, List[str]]) -> str:
        """構建上下文感知的句子"""
        sentences = []

        # AI/ML 組
        if "ai_ml" in grouped_terms and grouped_terms["ai_ml"]:
            terms_str = ", ".join(grouped_terms["ai_ml"])
            sentences.append(f"We will discuss AI technologies including {terms_str}")

        # 硬體組
        if "hardware" in grouped_terms and grouped_terms["hardware"]:
            terms_str = ", ".join(grouped_terms["hardware"])
            sentences.append(f"running on {terms_str} hardware")

        # 框架組
        if "frameworks" in grouped_terms and grouped_terms["frameworks"]:
            terms_str = ", ".join(grouped_terms["frameworks"])
            sentences.append(f"using frameworks like {terms_str}")

        # 公司組
        if "companies" in grouped_terms and grouped_terms["companies"]:
            terms_str = ", ".join(grouped_terms["companies"])
            sentences.append(f"from companies such as {terms_str}")

        # 協議組
        if "protocols" in grouped_terms and grouped_terms["protocols"]:
            terms_str = ", ".join(grouped_terms["protocols"])
            sentences.append(f"through {terms_str} protocols")

        # 其他
        if "others" in grouped_terms and grouped_terms["others"]:
            terms_str = ", ".join(grouped_terms["others"])
            sentences.append(f"and {terms_str}")

        # 組合句子
        if not sentences:
            return ""

        # 第一句首字母大寫，最後加句號
        prompt = ". ".join(sentences).strip()
        if prompt and not prompt.endswith("."):
            prompt += "."

        # 確保首字母大寫
        if prompt:
            prompt = prompt[0].upper() + prompt[1:]

        return prompt

    def generate_custom_prompt(self,
                              focus_terms: List[str],
                              additional_context: str = "") -> str:
        """
        生成自定義 prompt，針對特定術語

        Args:
            focus_terms: 重點關注的術語列表
            additional_context: 額外的上下文描述

        Returns:
            自定義 prompt
        """
        if not focus_terms:
            logger.warning("沒有提供 focus_terms")
            return additional_context

        terms_str = ", ".join(focus_terms)

        if additional_context:
            prompt = f"{additional_context} Key terms include: {terms_str}."
        else:
            prompt = f"This discussion focuses on {terms_str}."

        return prompt

    def get_prompt_stats(self, prompt: str) -> Dict:
        """
        獲取 prompt 統計信息

        Args:
            prompt: 要分析的 prompt

        Returns:
            統計信息字典
        """
        return {
            "length": len(prompt),
            "word_count": len(prompt.split()),
            "term_count": sum(1 for term in self.vocabulary_config.vocabulary.keys()
                            if term in prompt),
            "recommended": 50 <= len(prompt) <= 200  # 推薦的 prompt 長度範圍
        }


# 全局實例
prompt_generator = VocabularyPromptGenerator()


# 便捷函數
def generate_whisper_prompt(terms: List[str] = None,
                           max_terms: int = 15,
                           language: str = "english") -> str:
    """
    便捷函數：生成 Whisper initial_prompt

    Args:
        terms: 指定術語列表（None 表示自動選擇）
        max_terms: 最大術語數量
        language: 語言（'english' 或 'chinese'）

    Returns:
        生成的 prompt 字符串
    """
    return prompt_generator.generate_prompt(
        terms=terms,
        max_terms=max_terms,
        language=language
    )
