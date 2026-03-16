"""
統一 Prompt 配置文件 - 優化簡化版本
集中管理所有 AI 模型的提示詞設定
"""

from typing import Dict, Any, Optional, Union, List
from enum import Enum
import logging
from functools import lru_cache
import re

class ProcessingMode(Enum):
    """處理模式枚舉"""
    DEFAULT = "default"
    MEETING = "meeting"
    LECTURE = "lecture"
    INTERVIEW = "interview"
    SPEAKER_ALIGNMENT = "speaker_alignment"
    CUSTOM = "custom"

class DetailLevel(Enum):
    """詳細程度枚舉 - 系統固定使用 DETAILED，但保留原值以維持向後兼容"""
    DETAILED = "detailed"
    NORMAL = "normal"           # 保留原值，但系統會強制使用 DETAILED
    SIMPLE = "simple"           # 保留原值，但系統會強制使用 DETAILED
    COMPREHENSIVE = "comprehensive"  # 保留原值，但系統會強制使用 DETAILED
    EXECUTIVE = "executive"     # 保留原值，但系統會強制使用 DETAILED
    CUSTOM = "custom"           # 保留原值，但系統會強制使用 DETAILED

class SummaryTag(Enum):
    """摘要標籤枚舉 - 簡化版（5 個實用標籤）"""
    BULLETED_LIST = "bulleted_list"       # 條列式整理
    SUMMARY = "summary"                   # 摘要整理
    MEETING_NOTES = "meeting_notes"       # 會議記錄（含待辦、決策）
    DETAILED_ANALYSIS = "detailed_analysis"  # 詳細分析
    CUSTOM = "custom"                     # 自定義

class PromptConfig:
    """
    Prompt 配置類別
    提供統一的 prompt 管理功能，支援多種處理模式和詳細程度設定
    """

    _logger = logging.getLogger(__name__)

    # 統一基礎要求
    BASE_REQUIREMENTS = """使用台灣繁體中文，Markdown 格式，基於原文整理，直接輸出。不可捏造原文沒有的資訊。嚴禁出現任何簡體字（如：用「軟體」不用「軟件」，用「資料」不用「數據」，用「網路」不用「網絡」）。"""

    # 標籤配置
    TAG_CONFIG = {
        SummaryTag.BULLETED_LIST: {
            "display_name": "條列式",
            "description": "將重點整理成清晰的項目列表",
            "prompt_instruction": "用項目符號列表整理所有重點。",
            "icon": "📋"
        },
        SummaryTag.SUMMARY: {
            "display_name": "摘要整理",
            "description": "整理成連貫的摘要文章",
            "prompt_instruction": "整理成連貫的摘要文章，用標題分段。",
            "icon": "📝"
        },
        SummaryTag.MEETING_NOTES: {
            "display_name": "會議記錄",
            "description": "會議格式，包含討論、決策、待辦事項",
            "prompt_instruction": "整理成會議記錄，包含會議摘要、討論議題、決策事項、待辦事項。",
            "icon": "📅"
        },
        SummaryTag.DETAILED_ANALYSIS: {
            "display_name": "詳細分析",
            "description": "深入分析每個論點和細節",
            "prompt_instruction": "深入分析每個論點，詳細展開所有細節。",
            "icon": "🔍"
        },
        SummaryTag.CUSTOM: {
            "display_name": "自定義",
            "description": "使用自定義指令處理",
            "prompt_instruction": "",
            "icon": "✨"
        }
    }

    # 模式特定的基礎提示
    MODE_BASE_PROMPTS = {
        ProcessingMode.DEFAULT: "整理語音內容",
        ProcessingMode.MEETING: "會議紀錄",
        ProcessingMode.LECTURE: "重點摘要",
        ProcessingMode.INTERVIEW: "訪談整理",
        ProcessingMode.SPEAKER_ALIGNMENT: "多人對話整理",
        ProcessingMode.CUSTOM: ""
    }

    # 詳細程度指令
    DETAIL_LEVEL_INSTRUCTIONS = {
        DetailLevel.DETAILED: "完整涵蓋所有重要細節，不要省略。",
    }

    # 格式模板
    MODE_FORMAT_TEMPLATES = {
        ProcessingMode.MEETING: "",
        ProcessingMode.LECTURE: "",
        ProcessingMode.INTERVIEW: "",
        ProcessingMode.DEFAULT: "",
        ProcessingMode.SPEAKER_ALIGNMENT: "",
        ProcessingMode.CUSTOM: ""
    }

    @classmethod
    def get_mode_specific_requirements(cls, mode: ProcessingMode) -> str:
        """獲取模式特定要求（已簡化，大多數模式不需要額外要求）"""
        return ""

    @classmethod
    def get_available_tags(cls) -> List[Dict[str, Any]]:
        """獲取所有可用的標籤（簡化版）"""
        tags = []
        for tag_enum, config in cls.TAG_CONFIG.items():
            tags.append({
                "id": tag_enum.value,
                "name": config["display_name"],
                "description": config["description"],
                "icon": config.get("icon", "")
            })
        return tags

    @classmethod
    def generate_intelligent_prompt_from_tags(cls, selected_tags: List[str], text: str, mode: str) -> str:
        """根據選擇的標籤生成處理指令（簡化版）"""
        if not selected_tags:
            return ""

        instructions = []
        for tag_id in selected_tags:
            try:
                tag_enum = SummaryTag(tag_id)
                if tag_enum in cls.TAG_CONFIG:
                    instruction = cls.TAG_CONFIG[tag_enum]["prompt_instruction"]
                    if instruction:
                        instructions.append(instruction)
            except ValueError:
                continue

        if not instructions:
            return ""

        return " ".join(instructions)

    @classmethod
    def generate_tag_instructions(cls, selected_tags: List[str]) -> str:
        """標籤指令生成（簡化版）"""
        return cls.generate_intelligent_prompt_from_tags(selected_tags, "", "")

    @classmethod
    def validate_tag_combination(cls, selected_tags: List[str]) -> tuple[bool, str]:
        """驗證標籤組合（簡化版 - 只檢查標籤是否有效）"""
        if not selected_tags:
            return True, ""  # 允許不選標籤

        for tag_id in selected_tags:
            try:
                tag_enum = SummaryTag(tag_id)
                if tag_enum not in cls.TAG_CONFIG:
                    return False, f"無效的標籤: {tag_id}"
            except ValueError:
                return False, f"無效的標籤: {tag_id}"

        return True, ""

    @classmethod
    def get_tag_suggestions(cls, mode: ProcessingMode) -> List[str]:
        """根據處理模式推薦標籤（簡化版）"""
        suggestions = {
            ProcessingMode.MEETING: [SummaryTag.MEETING_NOTES.value],
            ProcessingMode.LECTURE: [SummaryTag.SUMMARY.value],
            ProcessingMode.INTERVIEW: [SummaryTag.DETAILED_ANALYSIS.value],
            ProcessingMode.DEFAULT: [SummaryTag.BULLETED_LIST.value]
        }
        return suggestions.get(mode, [SummaryTag.BULLETED_LIST.value])

    @classmethod
    def generate_prompt(cls, text: str, mode: ProcessingMode = ProcessingMode.DEFAULT,
                       detail_level: DetailLevel = DetailLevel.DETAILED,
                       custom_mode_prompt: Optional[str] = None,
                       custom_detail_prompt: Optional[str] = None,
                       custom_format_template: Optional[str] = None,
                       selected_tags: Optional[List[str]] = None) -> str:
        """
        生成完整的 prompt

        Args:
            text: 需要處理的文字內容
            mode: 處理模式
            detail_level: 詳細程度
            custom_mode_prompt: 自定義模式的基礎提示
            custom_detail_prompt: 自定義詳細程度指令
            custom_format_template: 自定義格式模板
            selected_tags: 選擇的標籤 ID 列表

        Returns:
            str: 完整的 prompt 字符串
        """

        # 處理自定義模式驗證
        if mode == ProcessingMode.CUSTOM and not custom_mode_prompt:
            raise ValueError("自定義模式需要提供 custom_mode_prompt 參數")

        if detail_level == DetailLevel.CUSTOM and not custom_detail_prompt:
            raise ValueError("自定義詳細程度需要提供 custom_detail_prompt 參數")

        # 驗證標籤組合
        if selected_tags:
            is_valid, error_msg = cls.validate_tag_combination(selected_tags)
            if not is_valid:
                raise ValueError(f"標籤組合無效: {error_msg}")

        # 獲取基礎提示
        if mode == ProcessingMode.CUSTOM:
            base_prompt = custom_mode_prompt
        else:
            base_prompt = cls.MODE_BASE_PROMPTS.get(mode, cls.MODE_BASE_PROMPTS[ProcessingMode.DEFAULT])

        # 獲取詳細程度指令 - 固定使用詳細模式
        if detail_level == DetailLevel.CUSTOM:
            detail_instruction = custom_detail_prompt
        else:
            detail_instruction = cls.DETAIL_LEVEL_INSTRUCTIONS.get(DetailLevel.DETAILED, "深入分析每個論點，多層次展開，完整涵蓋所有重要細節。")

        # 獲取模式特定要求
        mode_requirements = cls.get_mode_specific_requirements(mode)

        # 獲取格式模板
        if mode == ProcessingMode.CUSTOM and custom_format_template:
            format_template = custom_format_template
        else:
            format_template = cls.MODE_FORMAT_TEMPLATES.get(mode, cls.MODE_FORMAT_TEMPLATES[ProcessingMode.DEFAULT])

        # 驗證輸入
        if not text or not text.strip():
            raise ValueError("文字內容不能為空")

        # 使用智能標籤系統
        smart_tag_instruction = ""
        if selected_tags:
            smart_tag_instruction = cls.generate_intelligent_prompt_from_tags(selected_tags, text, mode.value)
            if smart_tag_instruction:
                detail_instruction = smart_tag_instruction

        # 組合 prompt
        prompt_parts = [
            base_prompt,
            cls.BASE_REQUIREMENTS,
            detail_instruction,
            mode_requirements,
            format_template,
            f"\n---\n{text.strip()}\n---",
        ]

        return "\n\n".join(filter(None, prompt_parts))

    @classmethod
    def get_simple_prompt(cls, text: str, mode: str = "default", detail_level: str = "detailed",
                         custom_mode_prompt: Optional[str] = None,
                         custom_detail_prompt: Optional[str] = None,
                         custom_format_template: Optional[str] = None,
                         selected_tags: Optional[List[str]] = None) -> str:
        """簡化版本的 prompt 生成（向後兼容）- 固定使用詳細模式"""
        try:
            mode_enum = ProcessingMode(mode)
            # 固定使用 DETAILED 模式
            detail_enum = DetailLevel.DETAILED
            return cls.generate_prompt(text, mode_enum, detail_enum,
                                     custom_mode_prompt, custom_detail_prompt, custom_format_template, selected_tags)
        except ValueError as e:
            cls._logger.warning(f"無效的模式設定: {e}，使用預設值")
            return cls.generate_prompt(text, ProcessingMode.DEFAULT, DetailLevel.DETAILED, selected_tags=selected_tags)
        except Exception as e:
            cls._logger.error(f"Prompt 生成失敗: {e}")
            raise

    @classmethod
    def get_whisper_context_prompt(cls, mode: str = "default", previous_text: Optional[str] = None) -> str:
        """生成 Whisper 上下文 prompt"""
        base_prompts = {
            'meeting': "這是一段會議錄音的轉錄，請準確轉錄發言內容：",
            'lecture': "這是一段講座或教學內容的轉錄，請準確轉錄講解內容：",
            'default': "請準確轉錄以下中文語音內容："
        }

        base_prompt = base_prompts.get(mode, base_prompts['default'])

        if previous_text:
            context_info = f"\n\n前文內容：\n{previous_text}\n\n請繼續轉錄："
            return base_prompt + context_info

        return base_prompt

    @classmethod
    @lru_cache(maxsize=128)
    def get_cached_prompt_template(cls, mode: str, detail_level: str = "detailed") -> str:
        """獲取緩存的 prompt 模板（不包含具體文字內容）- 固定使用詳細模式"""
        try:
            mode_enum = ProcessingMode(mode)
            # 固定使用 DETAILED 模式
            base_prompt = cls.MODE_BASE_PROMPTS.get(mode_enum, cls.MODE_BASE_PROMPTS[ProcessingMode.DEFAULT])
            detail_instruction = cls.DETAIL_LEVEL_INSTRUCTIONS.get(DetailLevel.DETAILED, "深入分析每個論點，多層次展開，完整涵蓋所有重要細節。")
            mode_requirements = cls.get_mode_specific_requirements(mode_enum)
            format_template = cls.MODE_FORMAT_TEMPLATES.get(mode_enum, cls.MODE_FORMAT_TEMPLATES[ProcessingMode.DEFAULT])

            template_parts = [
                base_prompt,
                cls.BASE_REQUIREMENTS,
                detail_instruction,
                mode_requirements,
                format_template
            ]

            return "\n\n".join(filter(None, template_parts))
        except Exception as e:
            cls._logger.error(f"獲取緩存模板失敗: {e}")
            return cls.get_cached_prompt_template("default", "detailed")

    @classmethod
    def validate_mode_and_detail(cls, mode: str, detail_level: str) -> tuple[bool, str]:
        """驗證模式和詳細程度設定"""
        try:
            ProcessingMode(mode)
            DetailLevel(detail_level)
            return True, ""
        except ValueError as e:
            error_msg = f"無效的設定 - mode: {mode}, detail_level: {detail_level}"
            return False, error_msg

    @classmethod
    def get_available_modes(cls) -> list[str]:
        """獲取所有可用的處理模式"""
        return [mode.value for mode in ProcessingMode]

    @classmethod
    def get_available_detail_levels(cls) -> list[str]:
        """獲取所有可用的詳細程度等級 - 固定只有詳細模式"""
        return ["detailed"]

    @classmethod
    def get_mode_description(cls, mode: str) -> str:
        """獲取模式描述"""
        descriptions = {
            "default": "通用文字整理模式",
            "meeting": "會議記錄整理模式",
            "lecture": "講座/課程內容整理模式",
            "interview": "訪談內容整理模式",
            "custom": "自定義處理模式"
        }
        return descriptions.get(mode, "未知模式")

    @classmethod
    def get_text_organization_prompt(cls, text: str, mode: str = "default", detail_level: str = "detailed") -> str:
        """統一使用主要的 prompt 生成系統 - 固定使用詳細模式"""
        return cls.get_simple_prompt(text, mode, "detailed")

# 向後兼容的簡化函數
def generate_prompt(chunk: str, mode: str, detail_level: str) -> str:
    return PromptConfig.get_simple_prompt(chunk, mode, detail_level)
