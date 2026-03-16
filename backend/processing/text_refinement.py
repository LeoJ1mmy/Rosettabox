"""
Text Refinement Agent - 文字精煉代理
在 Whisper 轉錄後、AI 摘要前進行文字清理和術語校正

功能：
1. 移除中英文語氣詞（嗯、啊、呃、um、uh 等）
2. 清理異常重複字符（我我我我→我）
3. 程式化模糊匹配術語校正（無需 LLM，毫秒級完成）
4. 追蹤並報告哪些詞彙被替換（v2.0）

v3.0 重大變更：
- 移除 LLM 術語校正（gemma3:27b 處理 15000 字符需要 4 分鐘）
- 改用 difflib 模糊匹配 + 滑動窗口搜尋
- 速度：從 4 分鐘 → < 1 秒（提升 240x）
"""

import logging
import re
import difflib
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ReplacementRecord:
    """記錄單個替換操作"""
    original: str
    replacement: str
    hot_word_matched: str = ""
    hot_word_annotation: str = ""  # 熱詞的註解說明
    position: int = -1
    context: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "replacement": self.replacement,
            "hot_word_matched": self.hot_word_matched,
            "hot_word_annotation": self.hot_word_annotation,
            "position": self.position,
            "context": self.context
        }


@dataclass
class RefinementResult:
    """精煉結果，包含替換追蹤"""
    refined_text: str
    original_text: str
    replacements: List[ReplacementRecord] = field(default_factory=list)
    filler_words_removed: int = 0
    stage1_applied: bool = False
    stage2_applied: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "refined_text": self.refined_text,
            "original_text": self.original_text,
            "replacements": [r.to_dict() for r in self.replacements],
            "replacement_count": len(self.replacements),
            "filler_words_removed": self.filler_words_removed,
            "stage1_applied": self.stage1_applied,
            "stage2_applied": self.stage2_applied
        }

# ============================================================================
# Filler Word Patterns
# ============================================================================

# 中文語氣詞模式（含台灣口語 / 台式中文常見語氣詞）
CHINESE_FILLERS = [
    # --- 基本語氣詞 ---
    r'嗯+[,，、\s]*',           # 嗯、嗯嗯、嗯嗯嗯
    r'啊+[,，、\s]*',           # 啊、啊啊
    r'呃+[,，、\s]*',           # 呃、呃呃
    r'哦+[,，、\s]*',           # 哦、哦哦
    r'噢+[,，、\s]*',           # 噢、噢噢
    r'欸+[,，、\s]*',           # 欸、欸欸
    # --- 台灣口語特有語氣詞 ---
    r'齁+[,，、\s]*',           # 齁（台灣常見強調 / 確認語氣）
    r'蛤+[,，、\s]*',           # 蛤（疑問 / 驚訝）
    r'吼+[,，、\s]*',           # 吼（台語強調語氣）
    r'喔+[,，、\s]*',           # 喔（知道了 / 應答）
    r'厚+[,，、\s]*',           # 厚（台語「齁」的另一寫法）
    r'嘿+[,，、\s]*',           # 嘿（台灣口語應答）
    r'(?<![^\s,，。！？])\s*對+啦?[,，、\s]*',  # 對、對對、對啦
    r'(?<![^\s,，。！？])\s*好+啦?[,，、\s]*',  # 好、好好、好啦
    r'(?<![^\s,，。！？])\s*是啊[,，、\s]*',    # 是啊（附和）
    # --- 口語連接詞 / 填充詞 ---
    r'(?<![^\s,，。！？])\s*那個[,，、\s]*',   # 那個（作為語氣詞）
    r'(?<![^\s,，。！？])\s*就是說?[,，、\s]*', # 就是、就是說
    r'(?<![^\s,，。！？])\s*然後呢?[,，、\s]*', # 然後、然後呢
    r'(?<![^\s,，。！？])\s*對啊[,，、\s]*',   # 對啊
    r'(?<![^\s,，。！？])\s*這樣子[,，、\s]*', # 這樣子（作為語氣詞）
    r'(?<![^\s,，。！？])\s*怎麼說[,，、\s]*', # 怎麼說
    r'(?<![^\s,，。！？])\s*其實[,，、\s]*',   # 其實（作為語氣詞開頭）
    r'(?<![^\s,，。！？])\s*所以說?[,，、\s]*', # 所以、所以說
    r'(?<![^\s,，。！？])\s*反正就是[,，、\s]*', # 反正就是（台灣口語）
    r'(?<![^\s,，。！？])\s*也就是說[,，、\s]*', # 也就是說
    r'(?<![^\s,，。！？])\s*不是嘛[,，、\s]*',  # 不是嘛
    r'(?<![^\s,，。！？])\s*對不對[,，、\s]*',  # 對不對（台灣口語反問）
    r'(?<![^\s,，。！？])\s*有沒有[,，、\s]*',  # 有沒有（台灣口語反問）
]

# 英文語氣詞模式
ENGLISH_FILLERS = [
    r'\b[Uu]m+\b[,\s]*',              # um, umm
    r'\b[Uu]h+\b[,\s]*',              # uh, uhh
    r'\b[Ee]r+\b[,\s]*',              # er, err
    r'\b[Aa]h+\b[,\s]*',              # ah, ahh
    r'\b[Ll]ike\b[,\s]+(?=[a-zA-Z])', # like (as filler, before word)
    r'\b[Yy]ou know\b[,\s]*',         # you know
    r'\b[Ww]ell\b[,\s]+(?=[a-zA-Z])', # well (as filler at start)
    r'\b[Ss]o\b[,\s]+(?=[a-zA-Z])',   # so (as filler at start)
    r'\b[Bb]asically\b[,\s]*',        # basically
    r'\b[Aa]ctually\b[,\s]+(?=[a-zA-Z])', # actually (as filler)
    r'\b[Ll]iterally\b[,\s]*',        # literally
    r'\b[Rr]ight\b[,\s]*(?=[,\s])',   # right (as filler)
    r'\b[Oo]kay so\b[,\s]*',          # okay so
]

# ============================================================================
# LLM Diff 模式配置 (v3.1 - 快速 + 精確)
# ============================================================================

REFINEMENT_LLM_OPTIONS = {
    "temperature": 0.01,     # 極低溫度，幾乎確定性
    "num_predict": 1024,     # Diff 模式只需修正列表
    "num_ctx": 32768,        # 模板~500 + 熱詞~4000 + 原文3000 ≈ 11000 tokens，留足餘量
    "top_p": 0.3,            # 嚴格取樣
    "top_k": 5,              # 只取前 5 候選
    "num_gpu": 99,
    "num_batch": 4096,
    "stop": ["【", "---", "```"],  # 只保留安全的 stop tokens（不能用常見中文詞）
}

REFINEMENT_PROMPT_TEMPLATE = """你是台灣語音轉錄校正器。原文來自台灣人的口語錄音，請找出「發音相近但拼寫錯誤」的術語。

嚴格規則：
1. 只修正「發音相似」的拼寫錯誤
2. 原文的詞和術語必須「讀起來像」，發音不相近就不要修正
3. 注意台灣口音特徵：捲舌音（zh/ch/sh）與平舌音（z/c/s）常混淆、前後鼻音（n/ng）不分、ㄈ/ㄏ混淆
4. 原文已經是正確的詞就不要改（例：「衛福部」是正確的詞，不要改）
5. 修正目標只寫術語本身，不寫括號內說明
6. 不改數字，不確定就不修正
7. 所有輸出必須使用台灣繁體中文，嚴禁出現任何簡體字（如：用「軟體」不用「軟件」，用「資料」不用「數據」）

錯誤示範（不要這樣做）：
衛福部→國眾電腦（發音完全不同，禁止）
人工智慧→AI（原文正確，禁止）

術語列表：
{hot_words_context}

原文：
{text}

每行「錯誤→正確」，沒有則輸出「無」："""

# 驗證閾值
MAX_LENGTH_RATIO = 1.15  # Diff 模式下長度變化應很小
MIN_LENGTH_RATIO = 0.85

# ============================================================================
# Core Functions
# ============================================================================

def remove_filler_words(text: str) -> str:
    """
    Stage 1: 使用正則表達式移除中英文語氣詞

    這是預處理步驟，在 LLM 處理之前執行，減少 LLM 處理負擔

    Args:
        text: 原始文本

    Returns:
        移除語氣詞後的文本
    """
    if not text:
        return text

    result = text

    # 移除 Whisper 停頓標記（省略號）
    result = re.sub(r'\.{2,}', '', result)   # 連續兩個以上的半形點
    result = re.sub(r'…+', '', result)        # Unicode 省略號（U+2026）

    # 移除中文語氣詞
    for pattern in CHINESE_FILLERS:
        try:
            result = re.sub(pattern, '', result)
        except re.error as e:
            logger.warning(f"正則表達式錯誤 (中文): {pattern} - {e}")

    # 移除英文語氣詞
    for pattern in ENGLISH_FILLERS:
        try:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        except re.error as e:
            logger.warning(f"正則表達式錯誤 (英文): {pattern} - {e}")

    # 清理多餘空格和標點
    result = re.sub(r'[,，、]{2,}', '，', result)  # 連續逗號合併
    result = re.sub(r'\s{2,}', ' ', result)        # 連續空格合併
    result = re.sub(r'^\s*[,，、]\s*', '', result) # 移除開頭標點
    result = re.sub(r'\s*[,，、]\s*$', '', result) # 移除結尾多餘標點
    result = re.sub(r'([。！？])\s*[,，、]\s*', r'\1', result)  # 句號後的逗號

    return result.strip()


def remove_repeated_chars(text: str) -> str:
    """
    Stage 1.5: 使用正則表達式清理異常重複字符

    例如：「我我我我」→「我」、「對對對對對」→「對」、「好好好好」→「好」

    只清理連續重複 3 次以上的中文字符（保留正常疊字如「謝謝」「慢慢」）

    Args:
        text: 已移除語氣詞的文本

    Returns:
        清理重複後的文本
    """
    if not text:
        return text

    # 中文字符連續重複 3+ 次 → 保留 1 個
    # 使用 backreference: (一個中文字)\1{2,} 表示同一字重複 3 次以上
    result = re.sub(r'([\u4e00-\u9fff])\1{2,}', r'\1', text)

    # 中文雙字詞組連續重複 2+ 次 → 保留 1 次
    # 例如：「所以所以所以」→「所以」、「然後然後然後」→「然後」
    result = re.sub(r'([\u4e00-\u9fff]{2,4})\1{2,}', r'\1', result)

    removed = len(text) - len(result)
    if removed > 0:
        logger.info(f"   清理重複字符: 移除 {removed} 字符")

    return result


def _parse_corrections(
    llm_output: str,
    hot_words_list: List[str] = None
) -> List[Tuple[str, str]]:
    """
    解析 LLM 輸出的修正列表（帶嚴格驗證）

    驗證規則：
    1. 原文最少 2 字符（防止 '4'→'GPT' 這種災難）
    2. 替換目標必須是熱詞或包含熱詞（防止 LLM 幻覺修正）
    3. 不允許純數字修正（防止 '806'→'800'）

    Args:
        llm_output: LLM 的原始輸出
        hot_words_list: 熱詞列表（用於驗證修正合法性）

    Returns:
        List of (original, replacement) tuples
    """
    corrections = []

    if not llm_output or "無需修正" in llm_output or "無" == llm_output.strip():
        return corrections

    # 建立熱詞查找集合（小寫）
    hw_set_lower = set()
    if hot_words_list:
        hw_set_lower = {hw.lower() for hw in hot_words_list}

    for line in llm_output.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        # 移除列表標記
        line = re.sub(r'^[\d]+[.、)\]]\s*', '', line)
        line = re.sub(r'^[-*·•]\s*', '', line)
        line = line.strip()

        # 解析 "A→B" 格式
        match = re.match(r'^(.+?)\s*[→\->=]{1,2}>\s*(.+)$', line)
        if not match:
            match = re.match(r'^(.+?)\s*→\s*(.+)$', line)

        if not match:
            continue

        original = match.group(1).strip().strip('"\'「」『』')
        replacement = match.group(2).strip().strip('"\'「」『』')

        # === 嚴格驗證 ===

        # 1. 跳過空白或相同
        if not original or not replacement or original == replacement:
            continue

        # 2. 最小長度：原文至少 2 字符
        if len(original) < 2:
            logger.debug(f"   丟棄（太短）: '{original}' → '{replacement}'")
            continue

        # 3. 不允許純數字修正
        if re.match(r'^[\d\s.]+$', original):
            logger.debug(f"   丟棄（純數字）: '{original}' → '{replacement}'")
            continue

        # 4. 驗證替換目標必須精確匹配熱詞（核心防線）
        if hw_set_lower:
            repl_lower = replacement.lower()
            if repl_lower not in hw_set_lower:
                logger.debug(f"   丟棄（非熱詞精確匹配）: '{original}' → '{replacement}'")
                continue

        # 5. 相似度防線：原文和替換至少有部分字符重疊
        #    防止「衛福部→國眾電腦」這種發音完全不同的亂配
        orig_lower = original.lower()
        repl_lower = replacement.lower()
        similarity = difflib.SequenceMatcher(None, orig_lower, repl_lower).ratio()

        # 中文：至少 0.2 相似度（允許同音異字，如 羅塞塔 vs RosettaBox = 0）
        # 英文：至少 0.3 相似度（允許拼寫偏差，如 JAMLINE vs Gemini）
        is_chinese_orig = bool(re.search(r'[\u4e00-\u9fff]', original))
        is_chinese_repl = bool(re.search(r'[\u4e00-\u9fff]', replacement))

        if is_chinese_orig and is_chinese_repl:
            # 中文→中文：要求至少共用一個字
            shared_chars = set(original) & set(replacement)
            if not shared_chars:
                logger.info(f"   丟棄（中文零重疊）: '{original}' → '{replacement}'")
                continue
        elif not is_chinese_orig and not is_chinese_repl:
            # 英文→英文：相似度至少 0.25
            if similarity < 0.25:
                logger.info(f"   丟棄（英文相似度 {similarity:.2f}<0.25）: '{original}' → '{replacement}'")
                continue
        # 中英混合（如 羅塞塔→RosettaBox）：跳過相似度檢查，信任 LLM 判斷

        corrections.append((original, replacement))

    return corrections


def _build_boundary_pattern(original: str) -> re.Pattern:
    """
    為修正詞構建正則表達式。

    策略：
    - 中文詞（如 國眾）：直接匹配，不加邊界限制。
      中文字本身就是語義單位，且修正已通過熱詞驗證 + 相似度檢查，
      假陽性風險極低。加邊界反而會導致所有修正都失敗（中文字流無 word boundary）。
    - 純英文詞（如 BUS）：用 \\b word boundary，避免匹配 BUSINESS 中的 BUS。
    - 混合詞（如 RosettaBox）：前後不能是字母數字（允許中文字相鄰）。
    """
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', original))
    has_ascii = bool(re.search(r'[a-zA-Z0-9]', original))

    escaped = re.escape(original)

    if has_chinese:
        # 含中文：直接匹配，不加邊界（中文連續字流中無法用 boundary）
        return re.compile(escaped)
    elif has_ascii:
        # 純英文/數字：前後不能是 ASCII 字母數字（防止 BUS 匹配 BUSINESS）
        # 不用 \b 因為 Python 3 把中文也當 word char，導致中文旁的英文詞匹配失敗
        return re.compile(f'(?<![a-zA-Z0-9]){escaped}(?![a-zA-Z0-9])')
    else:
        # 其他（符號等）：直接匹配
        return re.compile(escaped)


def _apply_corrections(text: str, corrections: List[Tuple[str, str]]) -> str:
    """
    將修正列表應用到原文（防止鏈式覆蓋 + 邊界安全）

    策略：
    1. 長詞優先替換（避免短詞先匹配到長詞的子串）
    2. 佔位符隔離已替換區段（防止鏈式覆蓋）
    3. 邊界檢查（BUS→BU 不會命中 BUSINESS）

    Args:
        text: 原始文本
        corrections: (original, replacement) tuples

    Returns:
        應用修正後的文本
    """
    if not corrections:
        return text

    # 去重 + 按原文長度降序
    seen = set()
    unique_corrections = []
    for orig, repl in corrections:
        if orig not in seen and orig != repl:
            seen.add(orig)
            unique_corrections.append((orig, repl))
    unique_corrections.sort(key=lambda x: len(x[0]), reverse=True)

    result = text
    placeholders = {}
    applied_count = 0

    for i, (original, replacement) in enumerate(unique_corrections):
        placeholder = f"\x00REPL{i:04d}\x00"
        pattern = _build_boundary_pattern(original)
        matches = pattern.findall(result)
        if matches:
            count = len(matches)
            result = pattern.sub(placeholder, result)
            placeholders[placeholder] = replacement
            applied_count += count
            logger.info(f"   修正: '{original}' → '{replacement}' ({count} 處)")

    # 還原佔位符
    for placeholder, replacement in placeholders.items():
        result = result.replace(placeholder, replacement)

    logger.info(f"   共應用 {applied_count} 處修正")
    return result


def build_hot_words_context() -> Tuple[List[str], str, Dict[str, str]]:
    """
    從 HotWordsManager 獲取熱詞並構建 LLM 上下文（帶註解版本）

    Returns:
        Tuple[List[str], str, Dict[str, str]]:
            (熱詞列表, 格式化的上下文字符串, 熱詞到註解的映射字典)
    """
    try:
        from utils.hot_words_manager import get_hot_words_manager
        manager = get_hot_words_manager()

        # 🔧 修復：獲取所有優先級的熱詞條目（包含 highest）
        highest_priority_entries = manager.get_entries_by_priority("highest")
        high_priority_entries = manager.get_entries_by_priority("high")
        medium_priority_entries = manager.get_entries_by_priority("medium")

        # 合併並限制數量（避免 prompt 過長）
        all_entries = highest_priority_entries + high_priority_entries + medium_priority_entries
        selected_entries = all_entries[:100]  # 最多 100 個熱詞

        if not selected_entries:
            return [], "", {}

        # 檢查是否包含別名
        include_aliases = manager.config.get('global_settings', {}).get('include_aliases_in_prompt', True)

        # 提取詞彙列表（用於後續匹配）— 包含別名作為合法替換目標
        selected_words = [e.word for e in selected_entries]
        alias_count = 0
        if include_aliases:
            for e in selected_entries:
                for alias in e.aliases:
                    if alias and alias not in selected_words:
                        selected_words.append(alias)
                        alias_count += 1

        # 建立熱詞到註解的映射字典
        annotations_dict = {e.word: e.annotation for e in selected_entries if e.annotation}

        # 構建術語列表（帶註解 + 別名，幫助 LLM 理解語境）
        context_lines = []
        for entry in selected_entries:
            line = f"- {entry.word}"
            if entry.annotation:
                line += f"（{entry.annotation}）"
            if include_aliases and entry.aliases:
                line += f"　別名：{', '.join(entry.aliases)}"
            context_lines.append(line)
        context = "\n".join(context_lines)

        # 統計有註解的數量
        annotated_count = len(annotations_dict)
        logger.info(f"✨ 熱詞上下文已構建：{len(selected_entries)} 個術語（{annotated_count} 個有註解，{alias_count} 個別名）")

        return selected_words, context, annotations_dict

    except Exception as e:
        logger.warning(f"⚠️ 構建熱詞上下文失敗: {e}")
        return [], "", {}


def correct_terms_with_llm(
    text: str,
    hot_words_context: str,
    ai_model: str,
    task_id: str,
    progress_callback=None,
    hot_words_list: List[str] = None
) -> str:
    """
    Stage 2: 使用 LLM 進行術語校正（Diff 模式 v3.1）

    優化：
    - 段落縮小到 3000 字符（prefill 快 5x）
    - 預過濾跳過無需校正的段落
    - num_ctx 縮小到 8192（匹配段落大小）

    Args:
        text: 預處理後的文本
        hot_words_context: 熱詞上下文字符串
        ai_model: AI 模型名稱
        task_id: 任務 ID
        progress_callback: 進度回調
        hot_words_list: 熱詞列表（用於預過濾）

    Returns:
        校正後的文本
    """
    from services.ai_engine_service import refinement_engine_manager
    from .task_processor import check_task_cancelled, TaskCancelledException
    import re

    check_task_cancelled(task_id, "LLM 校正前")

    if not refinement_engine_manager.check_health():
        logger.warning("⚠️ Refinement 引擎不可用，跳過 LLM 校正")
        return text

    model = ai_model or refinement_engine_manager.get_current_model()
    from config import config as _cfg
    logger.info(f"🔧 Refinement 引擎: {_cfg.REFINEMENT_ENGINE}, 模型: {model}")

    # v3.1: 縮小段落到 3000 字符，prefill 從 ~4 分鐘降到 ~48 秒
    MAX_CHUNK_SIZE = 3000

    if len(text) > MAX_CHUNK_SIZE:
        logger.info(f"📦 文本 {len(text)} 字符，分段處理（每段 {MAX_CHUNK_SIZE}）...")
        return _process_text_in_chunks(
            text, hot_words_context, model, task_id,
            MAX_CHUNK_SIZE, refinement_engine_manager, check_task_cancelled, TaskCancelledException,
            progress_callback, hot_words_list
        )

    # 短文本：直接處理
    if progress_callback:
        progress_callback(1, 1, "處理中")
    return _process_single_chunk(
        text, hot_words_context, model, task_id,
        refinement_engine_manager, check_task_cancelled, TaskCancelledException,
        hot_words_list
    )


def _process_single_chunk(
    text: str,
    hot_words_context: str,
    model: str,
    task_id: str,
    ai_engine_manager,
    check_task_cancelled,
    TaskCancelledException,
    hot_words_list: List[str] = None
) -> str:
    """
    處理單個文本段落（Diff 模式 v3.1）

    優化：
    1. 預過濾：無潛在匹配 → 跳過 LLM（0 秒）
    2. 段落縮小到 3000 字符（prefill 快 5x）
    3. 修正列表 + 佔位符替換（防止鏈式覆蓋）
    """
    import time

    # 構建 prompt
    prompt = REFINEMENT_PROMPT_TEMPLATE.format(
        hot_words_context=hot_words_context,
        text=text
    )

    options = REFINEMENT_LLM_OPTIONS.copy()

    logger.info(f"   🔧 LLM Diff: {len(text)} 字符, model={model}")

    try:
        t0 = time.time()
        response = ai_engine_manager.process_text(prompt, model, options)
        elapsed = time.time() - t0

        check_task_cancelled(task_id, "LLM 術語校正後")

        if not response or len(response.strip()) == 0:
            logger.info(f"   LLM 無回應 ({elapsed:.1f}s)")
            return text

        response = response.strip()
        logger.info(f"   LLM 回應: {len(response)} 字符 ({elapsed:.1f}s)")

        corrections = _parse_corrections(response, hot_words_list)

        if not corrections:
            logger.info(f"   無有效修正 | 回應: {response[:200]}")
            return text

        logger.info(f"   驗證通過 {len(corrections)} 個修正")
        corrected = _apply_corrections(text, corrections)
        return corrected

    except TaskCancelledException:
        raise
    except Exception as e:
        logger.warning(f"⚠️ LLM 校正失敗: {e}")
        return text


def _process_text_in_chunks(
    text: str,
    hot_words_context: str,
    model: str,
    task_id: str,
    max_chunk_size: int,
    ai_engine_manager,
    check_task_cancelled,
    TaskCancelledException,
    progress_callback=None,
    hot_words_list: List[str] = None
) -> str:
    """
    分段處理長文本（v3.1 快速版）

    策略：
    1. 按 max_chunk_size 分段
    2. 預過濾跳過無需校正的段落
    3. 每段 3000 字符，prefill 時間 ~48 秒
    """
    import time

    t_start = time.time()

    # 按固定大小分段
    chunks = []
    for i in range(0, len(text), max_chunk_size):
        chunks.append(text[i:i + max_chunk_size])

    total_chunks = len(chunks)
    logger.info(f"   📦 分成 {total_chunks} 段（每段 ≤{max_chunk_size} 字符）")

    refined_chunks = []
    skipped = 0

    for i, chunk in enumerate(chunks):
        check_task_cancelled(task_id, f"分段處理 {i+1}/{total_chunks}")

        if progress_callback:
            progress_callback(i + 1, total_chunks, f"校正 {i+1}/{total_chunks}")

        refined = _process_single_chunk(
            chunk, hot_words_context, model, task_id,
            ai_engine_manager, check_task_cancelled, TaskCancelledException,
            hot_words_list
        )
        if refined is chunk:  # 跳過（同一物件，未修改）
            skipped += 1
        refined_chunks.append(refined)

    result = "\n".join(refined_chunks)
    elapsed = time.time() - t_start
    logger.info(f"   ✅ 完成: {total_chunks} 段 ({skipped} 跳過), {elapsed:.1f}s, {len(result)} 字符")
    return result


def is_valid_refinement(original: str, refined: str) -> bool:
    """
    驗證 LLM 精煉結果的有效性

    檢查：
    1. 輸出不為空
    2. 長度變化在合理範圍內（0.50x ~ 1.25x）
       - 下限放寬到 0.50 以允許刪除大量重複字詞
    3. 不是 prompt 回顯
    4. 沒有異常重複模式（模型循環生成的跡象）

    Args:
        original: 原始文本
        refined: 精煉後文本

    Returns:
        bool: 是否有效
    """
    if not refined or len(refined.strip()) < 10:
        logger.warning("⚠️ 驗證失敗：輸出為空或過短")
        return False

    # 🔧 長度變化檢查
    # 允許較大幅度縮減（刪除重複字詞），但不允許大幅增加
    len_ratio = len(refined) / max(len(original), 1)
    logger.info(f"📊 長度變化比例: {len_ratio:.2f} (原始: {len(original)}, 精煉後: {len(refined)})")

    if len_ratio > MAX_LENGTH_RATIO:
        logger.warning(f"⚠️ 驗證失敗：輸出過長 (比例 {len_ratio:.2f} > {MAX_LENGTH_RATIO})")
        logger.warning(f"   這通常表示模型在生成額外內容而非修正術語")
        return False

    if len_ratio < MIN_LENGTH_RATIO:
        logger.warning(f"⚠️ 驗證失敗：輸出過短 (比例 {len_ratio:.2f} < {MIN_LENGTH_RATIO})")
        logger.warning(f"   這通常表示模型進行了過度刪減或摘要")
        return False

    # 🔧 異常重複模式檢測（通用算法，非窮舉）
    # 檢測任何字符連續重複超過閾值的情況
    repetition_score = detect_repetition_score(refined)
    if repetition_score > 0.1:  # 超過 10% 的內容是異常重複
        logger.warning(f"⚠️ 驗證失敗：檢測到異常重複模式 (分數: {repetition_score:.2%})")
        logger.warning(f"   這通常表示模型進入了循環生成狀態")
        return False

    # Prompt 回顯檢查（匹配當前 REFINEMENT_PROMPT_TEMPLATE 中的標記）
    prompt_markers = [
        "語音轉錄校正器",
        "嚴格規則：",
        "錯誤示範（不要這樣做）",
        "術語列表：",
        "每行「錯誤→正確」",
    ]
    for marker in prompt_markers:
        if marker in refined:
            logger.warning(f"⚠️ 驗證失敗：檢測到 prompt 回顯 ({marker})")
            return False

    return True


def detect_repetition_score(text: str) -> float:
    """
    通用重複檢測算法 - 計算文本中異常重複的比例

    算法：
    1. 掃描文本，找出連續重複的字符序列
    2. 如果同一字符（或短語）連續出現超過 N 次，標記為異常
    3. 返回異常重複字符佔總長度的比例

    Args:
        text: 待檢測文本

    Returns:
        異常重複分數 (0.0 ~ 1.0)
    """
    if not text or len(text) < 10:
        return 0.0

    total_len = len(text)
    abnormal_chars = 0

    # 閾值：連續重複超過 5 次視為異常
    REPEAT_THRESHOLD = 5

    i = 0
    while i < len(text):
        char = text[i]
        repeat_count = 1

        # 計算連續相同字符數量
        while i + repeat_count < len(text) and text[i + repeat_count] == char:
            repeat_count += 1

        # 如果超過閾值（且不是空格/換行），標記為異常
        if repeat_count > REPEAT_THRESHOLD and char not in ' \n\t':
            # 只計算超出正常範圍的部分
            abnormal_chars += (repeat_count - 1)

        i += repeat_count

    return abnormal_chars / total_len


def detect_replacements(
    original: str,
    refined: str,
    hot_words: List[str],
    hot_word_annotations: Optional[Dict[str, str]] = None
) -> List[ReplacementRecord]:
    """
    檢測原文與精煉後文本之間的替換

    使用 difflib 進行差異分析，並匹配 hot words 來識別術語校正

    Args:
        original: 原始文本
        refined: 精煉後文本
        hot_words: 熱詞列表
        hot_word_annotations: 熱詞到註解的映射字典 {word: annotation}

    Returns:
        替換記錄列表
    """
    replacements = []
    annotations = hot_word_annotations or {}

    # 使用 SequenceMatcher 來找出差異
    matcher = difflib.SequenceMatcher(None, original, refined)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            original_segment = original[i1:i2]
            refined_segment = refined[j1:j2]

            # 跳過純空白差異
            if original_segment.strip() == refined_segment.strip():
                continue

            # 嘗試匹配 hot word 並獲取註解
            matched_hot_word = ""
            matched_annotation = ""
            for hw in hot_words:
                hw_lower = hw.lower()
                if hw_lower in refined_segment.lower() or hw in refined_segment:
                    matched_hot_word = hw
                    matched_annotation = annotations.get(hw, "")
                    break

            # 獲取上下文（前後各 20 字符）
            context_start = max(0, j1 - 20)
            context_end = min(len(refined), j2 + 20)
            context = refined[context_start:context_end]

            record = ReplacementRecord(
                original=original_segment.strip(),
                replacement=refined_segment.strip(),
                hot_word_matched=matched_hot_word,
                hot_word_annotation=matched_annotation,
                position=i1,
                context=f"...{context}..."
            )
            replacements.append(record)

            # 日誌輸出包含註解
            log_msg = f"🔄 檢測到替換: '{original_segment.strip()}' → '{refined_segment.strip()}'"
            if matched_hot_word:
                log_msg += f" (熱詞: {matched_hot_word}"
                if matched_annotation:
                    log_msg += f" - {matched_annotation}"
                log_msg += ")"
            logger.info(log_msg)

    return replacements


def refine_transcription_with_tracking(
    raw_text: str,
    task_id: str,
    ai_model: str = None
) -> RefinementResult:
    """
    精煉 Whisper 轉錄結果，並追蹤所有替換（帶替換追蹤的版本）

    兩階段處理：
    1. Stage 1: Regex 移除語氣詞（快速、確定性）
    2. Stage 2: LLM 術語校正（上下文感知）

    Args:
        raw_text: Whisper 原始轉錄文本
        task_id: 任務 ID（用於取消檢查和進度更新）
        ai_model: AI 模型名稱（可選，使用配置默認值）

    Returns:
        RefinementResult: 包含精煉文本和替換追蹤的完整結果

    Raises:
        TaskCancelledException: 如果任務被取消
    """
    from .task_processor import check_task_cancelled, TaskCancelledException

    result = RefinementResult(
        refined_text=raw_text,
        original_text=raw_text
    )

    # 空文本檢查
    if not raw_text or len(raw_text.strip()) < 10:
        logger.warning("⚠️ 文本過短，跳過精煉處理")
        return result

    logger.info(f"✨ 開始文字精煉處理（帶替換追蹤）")
    logger.info(f"   原始文本長度: {len(raw_text)} 字符")

    try:
        # 取消檢查
        check_task_cancelled(task_id, "文字精煉開始")

        # ================================================================
        # Stage 1: Regex 移除語氣詞（總是執行）
        # ================================================================
        preprocessed_text = remove_filler_words(raw_text)
        removed_chars = len(raw_text) - len(preprocessed_text)
        result.filler_words_removed = removed_chars
        result.stage1_applied = True

        logger.info(f"✨ Stage 1 完成: 移除語氣詞")
        logger.info(f"   移除字符數: {removed_chars}")
        logger.info(f"   處理後長度: {len(preprocessed_text)} 字符")

        # Stage 1.5: 清理異常重複字符（正則，無需 LLM）
        preprocessed_text = remove_repeated_chars(preprocessed_text)

        # 取消檢查
        check_task_cancelled(task_id, "Stage 1 後")

        # ================================================================
        # Stage 2: LLM 術語校正（Diff 模式）
        # ================================================================
        try:
            # 檢查是否啟用 refinement agent
            from utils.hot_words_manager import get_hot_words_manager
            manager = get_hot_words_manager()
            use_in_refinement = manager.config.get('global_settings', {}).get('use_in_refinement_agent', True)

            if not use_in_refinement:
                logger.info("ℹ️ 熱詞配置：use_in_refinement_agent=false，跳過 LLM 校正")
                result.refined_text = preprocessed_text
                return result

            # 獲取熱詞上下文（包含註解）
            hot_words_list, hot_words_context, hot_words_annotations = build_hot_words_context()

            if not hot_words_list:
                logger.info("ℹ️ 無熱詞配置，跳過 LLM 校正")
                result.refined_text = preprocessed_text
                return result

            # LLM 術語校正（Diff 模式：只返回修正列表）
            refined_text = correct_terms_with_llm(
                text=preprocessed_text,
                hot_words_context=hot_words_context,
                ai_model=ai_model,
                task_id=task_id,
                hot_words_list=hot_words_list
            )

            # Diff 模式下，校正已在 _process_single_chunk 中套用
            # 直接驗證結果合理性
            if is_valid_refinement(preprocessed_text, refined_text):
                result.stage2_applied = True
                result.refined_text = refined_text

                # 檢測替換（傳入註解字典）
                result.replacements = detect_replacements(
                    preprocessed_text, refined_text, hot_words_list, hot_words_annotations
                )

                logger.info(f"✅ Stage 2 完成: LLM 術語校正（Diff 模式）")
                logger.info(f"   最終長度: {len(refined_text)} 字符")
                logger.info(f"   檢測到 {len(result.replacements)} 個替換")

                # 輸出替換摘要（包含註解）
                if result.replacements:
                    logger.info("📋 替換摘要:")
                    for i, r in enumerate(result.replacements[:10], 1):  # 最多顯示 10 個
                        log_line = f"   {i}. '{r.original}' → '{r.replacement}'"
                        if r.hot_word_matched:
                            log_line += f" [{r.hot_word_matched}]"
                            if r.hot_word_annotation:
                                log_line += f" ({r.hot_word_annotation})"
                        logger.info(log_line)
                    if len(result.replacements) > 10:
                        logger.info(f"   ... 還有 {len(result.replacements) - 10} 個替換")
            else:
                logger.warning("⚠️ LLM 輸出驗證失敗，使用 Stage 1 結果")
                result.refined_text = preprocessed_text

        except TaskCancelledException:
            raise
        except Exception as e:
            logger.warning(f"⚠️ LLM 校正失敗: {str(e)}，使用 Stage 1 結果")
            result.refined_text = preprocessed_text

    except TaskCancelledException:
        raise
    except Exception as e:
        logger.error(f"❌ 文字精煉完全失敗: {str(e)}，返回原始文本")

    return result


def refine_transcription(
    raw_text: str,
    task_id: str,
    ai_model: str = None,
    progress_callback=None
) -> str:
    """
    精煉 Whisper 轉錄結果的主入口函數

    兩階段處理：
    1. Stage 1: Regex 移除語氣詞（快速、確定性）
    2. Stage 2: LLM 術語校正（上下文感知）

    錯誤回退策略：
    - LLM 失敗 → 使用 Stage 1 結果
    - Stage 1 失敗 → 使用原始文本

    Args:
        raw_text: Whisper 原始轉錄文本
        task_id: 任務 ID（用於取消檢查和進度更新）
        ai_model: AI 模型名稱（可選，使用配置默認值）
        progress_callback: 可選的進度回調函數 callback(current, total, message)

    Returns:
        精煉後的文本（保留原始結構，僅修正術語和移除語氣詞）

    Raises:
        TaskCancelledException: 如果任務被取消
    """
    from .task_processor import check_task_cancelled, TaskCancelledException

    # 空文本檢查
    if not raw_text or len(raw_text.strip()) < 10:
        logger.warning("⚠️ 文本過短，跳過精煉處理")
        return raw_text

    logger.info(f"✨ 開始文字精煉處理")
    logger.info(f"   原始文本長度: {len(raw_text)} 字符")

    try:
        # 取消檢查
        check_task_cancelled(task_id, "文字精煉開始")

        # ================================================================
        # Stage 1: Regex 移除語氣詞（總是執行）
        # ================================================================
        preprocessed_text = remove_filler_words(raw_text)
        removed_chars = len(raw_text) - len(preprocessed_text)
        logger.info(f"✨ Stage 1 完成: 移除語氣詞")
        logger.info(f"   移除字符數: {removed_chars}")
        logger.info(f"   處理後長度: {len(preprocessed_text)} 字符")

        # Stage 1.5: 清理異常重複字符（正則，無需 LLM）
        preprocessed_text = remove_repeated_chars(preprocessed_text)

        # 取消檢查
        check_task_cancelled(task_id, "Stage 1 後")

        # ================================================================
        # Stage 2: LLM 術語校正（Diff 模式）
        # ================================================================
        try:
            # 獲取熱詞上下文（包含註解）
            hot_words_list, hot_words_context, _ = build_hot_words_context()

            if not hot_words_list:
                logger.info("ℹ️ 無熱詞配置，跳過 LLM 校正")
                return preprocessed_text

            # LLM 術語校正（Diff 模式）
            refined_text = correct_terms_with_llm(
                text=preprocessed_text,
                hot_words_context=hot_words_context,
                ai_model=ai_model,
                task_id=task_id,
                progress_callback=progress_callback,
                hot_words_list=hot_words_list
            )

            # Diff 模式下，校正已在 _process_single_chunk 中套用
            if is_valid_refinement(preprocessed_text, refined_text):
                logger.info(f"✅ Stage 2 完成: LLM 術語校正（Diff 模式）")
                logger.info(f"   最終長度: {len(refined_text)} 字符")
                return refined_text
            else:
                logger.warning("⚠️ LLM 輸出驗證失敗，使用 Stage 1 結果")
                return preprocessed_text

        except TaskCancelledException:
            raise  # 重新拋出取消異常
        except Exception as e:
            logger.warning(f"⚠️ LLM 校正失敗: {str(e)}，使用 Stage 1 結果")
            return preprocessed_text

    except TaskCancelledException:
        raise  # 重新拋出取消異常
    except Exception as e:
        logger.error(f"❌ 文字精煉完全失敗: {str(e)}，返回原始文本")
        return raw_text


def clean_filler_words(text: str) -> str:
    """僅執行口語贅字清理（Stage 1），不進行 LLM 術語校正。
    用於文字處理模式，對使用者貼上的逐字稿進行基本清理。"""
    cleaned = remove_filler_words(text)
    cleaned = remove_repeated_chars(cleaned)
    return cleaned
