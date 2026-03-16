"""
簡化版 Prompt 生成器
"""

def generate_detailed_prompt(text: str, mode: str = "default", detail_level: str = "normal") -> str:
    """生成摘要 prompt"""

    mode_hints = {
        "meeting": "這是會議內容",
        "lecture": "這是講座內容",
        "interview": "這是訪談內容",
        "default": ""
    }

    detail_hints = {
        "normal": "請完整整理內容重點",
        "detailed": "請深入分析每個論點",
        "comprehensive": "請全面系統整理所有內容",
        "executive": "請提煉核心要點"
    }

    mode_hint = mode_hints.get(mode, "")
    detail_hint = detail_hints.get(detail_level, detail_hints["normal"])

    prompt = f"""請使用台灣繁體中文整理以下內容，嚴禁使用任何簡體字。{mode_hint}

{detail_hint}

使用 Markdown 格式（## 標題、- 列表、**粗體**）。
直接輸出結果，不要說明過程。

---
{text.strip()}
---

請開始整理："""

    return prompt


def generate_chunked_prompt(chunk: str, chunk_index: int, total_chunks: int,
                            detail_level: str = "normal", is_final: bool = False) -> str:
    """分塊處理的 prompt"""

    if is_final:
        return f"""請將以下 {total_chunks} 段內容匯總成完整報告。
使用台灣繁體中文，嚴禁使用任何簡體字，保留重要資訊，消除重複。

---
{chunk.strip()}
---

請開始匯總："""

    detail_hints = {
        "normal": "完整整理",
        "detailed": "深入分析",
        "comprehensive": "全面整理",
        "executive": "提煉要點"
    }

    hint = detail_hints.get(detail_level, "完整整理")

    return f"""這是第 {chunk_index + 1} 段（共 {total_chunks} 段）。
請{hint}此段內容，使用台灣繁體中文（嚴禁簡體字）和 Markdown 格式。

---
{chunk.strip()}
---

請開始整理第 {chunk_index + 1} 段："""


def create_prompt(text: str, mode: str = "default", detail_level: str = "normal",
                 chunk_info: dict = None) -> str:
    """統一的 prompt 創建函數"""
    if chunk_info and chunk_info.get("total", 1) > 1:
        return generate_chunked_prompt(
            text,
            chunk_info.get("index", 0),
            chunk_info.get("total", 1),
            detail_level,
            chunk_info.get("is_final", False)
        )
    else:
        return generate_detailed_prompt(text, mode, detail_level)
