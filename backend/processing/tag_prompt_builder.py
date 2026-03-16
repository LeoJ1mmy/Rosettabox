"""
標籤式 Prompt 建構器 - 直接將標籤映射到 Prompt 元素
無需額外的 AI 調用，即時響應
"""
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


# 標籤定義 - 每個標籤代表整理風格的提示（不強制內容結構）
TAG_DEFINITIONS = {
    # 內容類型標籤 - 僅作為風格參考，不強制生成不存在的內容
    "executive_summary": {
        "name": "執行摘要風格",
        "style_hint": "如果原文包含決策相關信息，請突出呈現",
        "weight": 10,
        "style_only": True
    },
    "key_points": {
        "name": "關鍵要點風格",
        "style_hint": "將原文的重要信息提煉為要點形式",
        "weight": 9,
        "style_only": True
    },
    "action_items": {
        "name": "行動項目風格",
        "style_hint": "如果原文提到任務或行動，請清楚標示",
        "weight": 8,
        "style_only": True
    },
    "decisions_made": {
        "name": "決議事項風格",
        "style_hint": "如果原文包含決定或結論，請明確呈現",
        "weight": 8,
        "style_only": True
    },
    "discussion_summary": {
        "name": "討論摘要風格",
        "style_hint": "如果是討論內容，請保留不同觀點",
        "weight": 7,
        "style_only": True
    },
    "technical_details": {
        "name": "技術細節風格",
        "style_hint": "如果原文包含技術信息，請保留完整細節",
        "weight": 6,
        "increases_length": True,
        "style_only": True
    },
    "risks_challenges": {
        "name": "風險挑戰風格",
        "style_hint": "如果原文提到風險或挑戰，請特別標示",
        "weight": 5,
        "style_only": True
    },
    "next_steps": {
        "name": "後續步驟風格",
        "style_hint": "如果原文提到未來計劃，請整理呈現",
        "weight": 7,
        "style_only": True
    },
    "participants": {
        "name": "參與者風格",
        "style_hint": "如果原文提到發言者，請標示說話者",
        "weight": 3,
        "style_only": True
    },
    "timeline": {
        "name": "時間軸風格",
        "style_hint": "如果原文包含時間順序，請按時序整理",
        "weight": 4,
        "style_only": True
    },
    "metrics_data": {
        "name": "數據指標風格",
        "style_hint": "如果原文包含數據，請清楚呈現數字信息",
        "weight": 6,
        "style_only": True
    },
    "background_context": {
        "name": "背景脈絡風格",
        "style_hint": "如果原文提到背景，請說明相關脈絡",
        "weight": 4,
        "increases_length": True,
        "style_only": True
    },
    "quotes": {
        "name": "重要引述風格",
        "style_hint": "如果有關鍵語句，請保留原文引述",
        "weight": 5,
        "style_only": True
    },
    "recommendations": {
        "name": "建議事項風格",
        "style_hint": "如果原文包含建議，請整理列出",
        "weight": 7,
        "style_only": True
    },
    "brief_summary": {
        "name": "精簡摘要風格",
        "style_hint": "用精簡方式呈現原文核心內容",
        "weight": 10,
        "reduces_length": True,
        "style_only": True
    },
    "custom": {
        "name": "自定義 Prompt",
        "style_hint": "",
        "weight": 100,
        "bypass_tag_builder": True
    },
}


def build_prompt_from_tags(
    content: str,
    selected_tags: List[str],
    base_mode: str = "meeting",
    detail_level: str = "normal",
    is_large_model: bool = False
) -> str:
    """
    根據選擇的標籤直接構建 prompt

    Args:
        content: 原始內容
        selected_tags: 用戶選擇的標籤 ID 列表
        base_mode: 基礎模式 (meeting, lecture, interview, etc.)
        detail_level: 詳細程度
        is_large_model: 是否為大型模型（30B+）

    Returns:
        完整的 prompt 字符串
    """

    if not selected_tags:
        # 沒有標籤時使用默認 prompt
        from processing.improved_prompts import generate_detailed_prompt
        return generate_detailed_prompt(content, base_mode, detail_level)

    # 驗證標籤並獲取定義
    valid_tags = []
    for tag_id in selected_tags:
        if tag_id in TAG_DEFINITIONS:
            valid_tags.append(tag_id)
        else:
            logger.warning(f"未知標籤: {tag_id}")

    if not valid_tags:
        logger.warning("沒有有效標籤，使用默認 prompt")
        from processing.improved_prompts import generate_detailed_prompt
        return generate_detailed_prompt(content, base_mode, detail_level)

    # 按權重排序標籤（高權重優先）
    sorted_tags = sorted(valid_tags, key=lambda t: TAG_DEFINITIONS[t]["weight"], reverse=True)

    # 🔧 移除死代碼 - tag_requirements 未被使用且會導致 KeyError
    # tag_requirements 變量從未被使用，而且 'prompt_section' 字段不存在
    # 實際的提示是通過 style_hints 構建的（見下方）

    # 基礎模式描述
    mode_descriptions = {
        "meeting": "會議記錄",
        "lecture": "課程內容",
        "interview": "訪談內容",
        "default": "內容"
    }
    mode_desc = mode_descriptions.get(base_mode, "內容")

    # 收集風格提示（不強制內容結構）
    style_hints = []
    for tag_id in sorted_tags:
        tag_def = TAG_DEFINITIONS[tag_id]
        if tag_def.get('style_hint'):
            style_hints.append(f"• {tag_def['style_hint']}")

    style_guidance = '\n'.join(style_hints) if style_hints else "• 根據原文實際內容靈活組織結構"

    # 🚀 大型模型使用極簡 prompt
    if is_large_model:
        tag_names = [TAG_DEFINITIONS[tag]["name"] for tag in sorted_tags]
        tag_list = '、'.join(tag_names)

        prompt = f"""請使用台灣繁體中文整理以下內容。

風格參考（僅供參考，不強制）：{tag_list}

核心原則：
• 必須忠實於原文，不可捏造信息
• 根據原文實際內容組織，不強制套用固定結構
• 可適當調整術語以確保邏輯連貫

---原始內容---
{content.strip()}
---內容結束---

請開始整理："""

        logger.info(f"🚀 大型模型簡化 Prompt: {len(sorted_tags)} 個風格標籤")
        logger.info(f"🚀 Prompt 內容: {prompt[:500]}...")
        return prompt

    # 標準模型使用完整 prompt（內容忠實版）
    prompt = f"""你是專業的內容整理助手。請忠實整理以下{mode_desc}內容，幫助讀者理解原文。

風格提示（僅作參考，根據原文實際情況靈活運用）：
{style_guidance}

核心原則：
• 必須使用台灣繁體中文（台灣用語習慣）
• 嚴格基於原文內容，絕對不可捏造或添加原文沒有的信息
• 忠實呈現原文的邏輯和結構
• 根據原文實際內容組織，不強制套用固定章節
• 如果原文沒有某類信息（如背景、案例、風險等），就不要生成
• 可適當調整專業術語的表達以確保邏輯連貫和易於理解

輸出格式：
• 使用清晰的 Markdown 格式（## 標題、條列、段落）
• 結構應反映原文的實際內容，而非標籤列表

---原始內容---
{content.strip()}
---內容結束---

請開始整理："""

    logger.info(f"✅ 標準風格標籤 Prompt: {len(sorted_tags)} 個標籤")
    logger.info(f"📋 風格提示: {', '.join([TAG_DEFINITIONS[t]['name'] for t in sorted_tags])}")
    logger.info(f"📋 Prompt 前500字: {prompt[:500]}...")

    return prompt


def _calculate_length_adjustment(tags: List[str], base_detail_level: str) -> Dict[str, str]:
    """
    根據標籤計算樣式調整

    Args:
        tags: 標籤列表
        base_detail_level: 基礎詳細程度

    Returns:
        包含 style 的字典
    """

    # 基礎樣式配置
    base_styles = {
        "simple": "簡潔明瞭",
        "normal": "完整詳細",
        "detailed": "詳盡深入",
        "comprehensive": "全面透徹"
    }

    base_style = base_styles.get(base_detail_level, base_styles["normal"])

    # 根據標籤數量調整
    tag_count = len(tags)

    # 檢查特殊標籤
    has_length_reducers = any(TAG_DEFINITIONS[t].get("reduces_length") for t in tags)

    if has_length_reducers:
        # 精簡摘要等標籤
        return {
            "style": "高度精簡，只保留核心資訊"
        }

    return {
        "style": f"{base_style}，涵蓋所有選定的{tag_count}個內容要素"
    }


def get_recommended_tags(mode: str) -> List[str]:
    """
    根據模式推薦標籤

    Args:
        mode: 處理模式

    Returns:
        推薦的標籤 ID 列表
    """

    recommendations = {
        "meeting": [
            "key_points",
            "decisions_made",
            "action_items",
            "next_steps",
            "discussion_summary"
        ],
        "lecture": [
            "key_points",
            "technical_details",
            "background_context",
            "recommendations"
        ],
        "interview": [
            "key_points",
            "quotes",
            "background_context",
            "recommendations"
        ],
        "executive": [
            "executive_summary",
            "key_points",
            "decisions_made",
            "next_steps"
        ]
    }

    return recommendations.get(mode, recommendations["meeting"])


def get_all_tags() -> Dict[str, Dict]:
    """
    獲取所有可用標籤及其定義

    Returns:
        標籤 ID 到定義的映射
    """
    return TAG_DEFINITIONS.copy()


def estimate_output_length(tags: List[str], detail_level: str) -> Dict[str, str]:
    """
    獲取給定標籤組合的輸出樣式描述

    Args:
        tags: 標籤列表
        detail_level: 詳細程度

    Returns:
        包含 style 描述的字典
    """

    adjustment = _calculate_length_adjustment(tags, detail_level)

    return {
        "style": adjustment["style"],
        "description": f"{detail_level} 模式，{adjustment['style']}"
    }


# 便捷函數
def create_tag_based_prompt(content: str, tags: List[str], mode: str = "meeting",
                            detail_level: str = "normal", is_large_model: bool = False) -> str:
    """
    便捷函數：創建基於標籤的 prompt

    這個函數可以直接替代使用 AI 編譯標籤的方法
    - 即時響應（無需 AI 調用）
    - 一致可靠
    - 易於調試
    - 可完全控制

    Args:
        content: 原始內容
        tags: 標籤列表
        mode: 處理模式
        detail_level: 詳細程度
        is_large_model: 是否為大型模型（30B+）- 使用極簡 prompt
    """
    return build_prompt_from_tags(content, tags, mode, detail_level, is_large_model)


if __name__ == "__main__":
    # 測試範例
    test_content = "這是一段測試會議內容..." * 50
    test_tags = ["executive_summary", "action_items", "key_points", "next_steps"]

    prompt = create_tag_based_prompt(test_content, test_tags, "meeting", "normal")

    print("=" * 70)
    print("標籤式 Prompt 建構器測試")
    print("=" * 70)
    print(f"\n選擇的標籤: {test_tags}")
    print(f"\n生成的 Prompt 長度: {len(prompt)} 字符")
    print(f"\n生成的 Prompt 預覽:")
    print(prompt[:800])
    print("...")

    # 估算輸出長度
    estimated = estimate_output_length(test_tags, "normal")
    print(f"\n預估輸出長度: {estimated['description']}")
