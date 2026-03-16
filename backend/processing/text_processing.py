"""
文字處理模組 - 從 app.py 提取的文字處理邏輯
"""
import logging
import re
import requests
from typing import List
from collections import Counter
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def _check_task_cancelled_text(task_id: str, stage: str = "") -> None:
    """
    檢查任務是否已被取消，如果已取消則拋出異常

    Args:
        task_id: 任務 ID
        stage: 當前處理階段（用於日誌記錄）
    """
    try:
        import app
        qm = app.get_queue_manager()
        if qm and qm.is_task_cancelled(task_id):
            stage_info = f" (階段: {stage})" if stage else ""
            logger.info(f"🚫 任務 {task_id} 已被取消{stage_info}，停止 AI 文字處理")
            from .task_processor import TaskCancelledException
            raise TaskCancelledException(f"任務已被用戶取消{stage_info}")
    except ImportError:
        pass  # 如果無法導入，繼續執行


# 移除重複的 generate_prompt 函數，統一使用 PromptConfig 系統

def organize_text_with_ai(text, mode="default", detail_level="normal", ai_model=None,
                         custom_mode_prompt=None, custom_detail_prompt=None, custom_format_template=None,
                         selected_tags=None, custom_prompt=None, task_id=None):
    """使用統一 AI 引擎整理文字 (支援 Ollama 和 vLLM)

    Args:
        task_id: 任務 ID，用於檢查取消狀態（可選）
    """
    try:
        logger.info(f"🚀 organize_text_with_ai 被調用 (統一 AI 引擎)")
        logger.info(f"📋 參數: mode={mode}, detail_level={detail_level}, ai_model={ai_model}")
        logger.info(f"📝 文本長度: {len(text) if text else 0} 字符")

        # 🔧 修復：AI 處理前檢查取消狀態
        if task_id:
            _check_task_cancelled_text(task_id, "AI 文字處理開始")
        
        from config import config
        from services.ai_engine_service import ai_engine_manager
        
        # 在 AI 處理前清理 Whisper 模型以釋放 GPU 記憶體
        try:
            from whisper_integration import WhisperManager
            logger.info("🧹 清理 Whisper 模型以釋放 GPU 記憶體...")
            # 這裡不需要載入模型，只需要清理現有的
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                logger.info("✅ GPU 記憶體已清理")
        except Exception as e:
            logger.warning(f"⚠️ 清理 GPU 記憶體時出現警告: {e}")
        
        # 檢查當前 AI 引擎狀態
        engine_info = ai_engine_manager.get_engine_info()
        current_model = ai_model or engine_info.get("model")
        logger.info(f"🤖 開始 AI 整理: 引擎={engine_info.get('engine_type')}, 模式={mode}, 詳細度={detail_level}, 模型={current_model}")
        
        if not text or len(text.strip()) < 10:
            logger.warning("⚠️ 文本過短，跳過 AI 整理")
            return text
        
        # 檢查 AI 引擎健康狀態
        if not ai_engine_manager.check_health():
            logger.error("❌ AI 引擎服務不可用")
            return text

        # 🚀 High Quality Mode - 從 config 讀取 context window 設定
        num_ctx = config.OLLAMA_NUM_CTX        # .env: OLLAMA_NUM_CTX (預設 65536)
        num_predict = config.OLLAMA_NUM_PREDICT  # .env: OLLAMA_NUM_PREDICT (預設 16384)

        # 🔧 動態計算最大分段大小，確保 input + output 不超過 num_ctx
        # 公式：可用輸入 tokens = num_ctx - num_predict - prompt 開銷
        # 中文 tokenizer 比例約 1.2 tokens/字元（保守估計，確保不溢出）
        TOKENS_PER_CHAR = 1.2
        PROMPT_OVERHEAD_TOKENS = 2000  # system message + prompt 模板 + 安全緩衝
        if num_predict > 0:
            input_budget_tokens = num_ctx - num_predict - PROMPT_OVERHEAD_TOKENS
        else:
            # num_predict=-1 (無限制)：保留 40% context 給輸出
            input_budget_tokens = int(num_ctx * 0.6) - PROMPT_OVERHEAD_TOKENS
        MAX_CHARS_PER_CHUNK = max(int(input_budget_tokens / TOKENS_PER_CHAR), 5000)

        max_chunk_size = MAX_CHARS_PER_CHUNK
        logger.info(f"📋 High Quality Mode: num_ctx={num_ctx}, num_predict={num_predict}, max_chunk={MAX_CHARS_PER_CHUNK} 字符")

        # 🌟 固定使用詳細模式參數配置 - 無輸出限制
        # 🔧 優化：降低懲罰參數，讓模型能更自然地展開論述
        temperature = 0.3        # 較低溫度，確保輸出穩定性
        top_k = 80               # 🔧 提高：更多詞彙選擇
        top_p = 0.95             # 鼓勵持續生成
        repeat_penalty = 1.05    # 🔧 降低：允許更自然的重複
        mirostat = 0             # 保持預設行為
        presence_penalty = 0.6   # 🔧 降低：允許重複提及重要概念
        frequency_penalty = 0.8  # 🔧 降低：允許詳細闘述

        logger.info(f"⚙️ 高品質配置 - num_predict={num_predict}, 上下文: {num_ctx}, 溫度: {temperature}, top_k: {top_k}, top_p: {top_p}")

        logger.info(f"🔧 使用穩定配置：每段最多 {max_chunk_size} 字符，總文本長度 {len(text)} 字符")
        
        # 智能分段：如果文本超過單段限制，進行分段處理
        if len(text) <= max_chunk_size:
            text_chunks = [text]
            logger.info(f"✅ 文本長度在限制內，不分段處理")
        else:
            text_chunks = split_text_into_chunks(text, max_chunk_size)
            logger.info(f"📋 文本已分段為 {len(text_chunks)} 段，將逐段處理")
        organized_chunks = []
        
        for i, chunk in enumerate(text_chunks):

            # 🎯 選擇 Prompt 生成器：自定義 > 標籤式 > 標準
            try:
                # 🔍 診斷日誌：檢查自定義標籤參數
                logger.info(f"🔍 [診斷] selected_tags: {selected_tags}")
                logger.info(f"🔍 [診斷] custom_prompt 類型: {type(custom_prompt)}, 值: {repr(custom_prompt)}")
                logger.info(f"🔍 [診斷] custom_prompt 是否為真值: {bool(custom_prompt)}")
                logger.info(f"🔍 [診斷] 'custom' in selected_tags: {'custom' in selected_tags if selected_tags else 'N/A'}")

                # 🔥 優先檢查是否使用自定義 Prompt（完全繞過標籤處理）
                if selected_tags and "custom" in selected_tags and custom_prompt:
                    # 自定義 prompt — 直接使用使用者的指令，不加多餘約束
                    prompt = f"""{custom_prompt.strip()}

使用台灣繁體中文，Markdown 格式。嚴禁出現任何簡體字。

---
{chunk.strip()}
---"""

                    logger.info(f"✅ 使用自定義 Prompt（長度: {len(prompt)} 字符）")
                    logger.info(f"📋 自定義 Prompt 預覽: {custom_prompt[:100]}...")

                # ⚠️ 檢測到 custom 標籤但沒有 custom_prompt - 這是錯誤情況
                elif selected_tags and "custom" in selected_tags and not custom_prompt:
                    logger.error(f"❌ 錯誤：選擇了 'custom' 標籤但 custom_prompt 為空！")
                    logger.error(f"❌ selected_tags: {selected_tags}")
                    logger.error(f"❌ custom_prompt: {repr(custom_prompt)}")
                    logger.error(f"❌ 將使用標準標籤系統作為後備方案，但這可能不是用戶期望的結果")

                    # 移除 custom 標籤，使用其他標籤處理
                    filtered_tags = [tag for tag in selected_tags if tag != 'custom']
                    if filtered_tags:
                        from prompt_config.prompt_config import PromptConfig
                        from prompt_config.prompt_config import ProcessingMode, DetailLevel
                        mode_enum = ProcessingMode(mode) if isinstance(mode, str) else mode
                        # 固定使用 DETAILED 模式
                        detail_enum = DetailLevel.DETAILED
                        prompt = PromptConfig.generate_prompt(
                            text=chunk,
                            mode=mode_enum,
                            detail_level=detail_enum,
                            selected_tags=filtered_tags
                        )
                        logger.warning(f"⚠️ 使用過濾後的標籤: {filtered_tags}")
                    else:
                        # 沒有其他標籤，使用標準 prompt
                        from processing.improved_prompts import create_prompt
                        chunk_info = {
                            "index": i,
                            "total": len(text_chunks),
                            "is_final": False
                        } if len(text_chunks) > 1 else None
                        prompt = create_prompt(chunk, mode, detail_level, chunk_info)
                        logger.warning(f"⚠️ 沒有其他標籤，使用標準 Prompt 生成器")

                # 如果有選擇標籤（非自定義），使用 PromptConfig 標籤系統
                elif selected_tags and len(selected_tags) > 0:
                    from prompt_config.prompt_config import PromptConfig

                    logger.info(f"🏷️ 檢測到標籤: {selected_tags}")
                    logger.info(f"🏷️ 標籤數量: {len(selected_tags)}")
                    logger.info(f"🏷️ 處理模式: {mode}, 詳細度: {detail_level}")

                    # 🔧 使用完整的 PromptConfig.generate_prompt()
                    from prompt_config.prompt_config import ProcessingMode, DetailLevel

                    mode_enum = ProcessingMode(mode) if isinstance(mode, str) else mode
                    # 固定使用 DETAILED 模式
                    detail_enum = DetailLevel.DETAILED

                    prompt = PromptConfig.generate_prompt(
                        text=chunk,
                        mode=mode_enum,
                        detail_level=detail_enum,
                        selected_tags=selected_tags
                    )

                    logger.info(f"📋 生成的完整 Prompt 長度: {len(prompt)} 字符")
                    logger.info(f"📋 Prompt 前300字: {prompt[:300]}")
                    logger.info(f"✅ 使用 PromptConfig 標籤系統（標籤數: {len(selected_tags)}）")
                    logger.info(f"📋 選擇的標籤: {', '.join(selected_tags)}")

                else:
                    # 🔄 沒有標籤時使用標準 Prompt 生成器
                    from processing.improved_prompts import create_prompt

                    # 准备分块信息
                    chunk_info = {
                        "index": i,
                        "total": len(text_chunks),
                        "is_final": False
                    } if len(text_chunks) > 1 else None

                    # 生成详细 prompt
                    prompt = create_prompt(chunk, mode, detail_level, chunk_info)
                    logger.info(f"✅ 使用標準 Prompt 生成器（詳細程度: {detail_level}）")

            except ImportError as e:
                logger.warning(f"⚠️ 無法載入 Prompt 生成器: {e}，使用簡化版本")
                prompt = f"""請使用台灣繁體中文整理以下內容，Markdown 格式。嚴禁出現任何簡體字。

---
{chunk.strip()}
---"""

            logger.info(f"🎯 使用引擎: {engine_info.get('engine_type')}, 模型: {current_model}")
            logger.info(f"📝 Prompt 長度: {len(prompt)} 字符, 詳細度: {detail_level}")

            try:
                # 處理選項 - 從 config 讀取 context 和 output 設定
                options = {
                    "temperature": temperature,
                    "num_predict": num_predict,       # 從 .env OLLAMA_NUM_PREDICT 讀取
                    "num_ctx": num_ctx,               # 從 .env OLLAMA_NUM_CTX 讀取
                    "top_p": top_p,
                    "top_k": top_k,
                    "repeat_penalty": repeat_penalty,
                    "mirostat": mirostat,
                    "presence_penalty": presence_penalty,
                    "frequency_penalty": frequency_penalty,
                    "stop": [],
                    # GPU 優化
                    "num_gpu": 99,                   # 全 GPU 加速
                    "num_batch": 512,                # 批處理優化
                }
                logger.info(f"🚀 配置: temp={temperature}, top_k={top_k}, top_p={top_p}, num_predict={num_predict}, ctx={num_ctx}, repeat_penalty={repeat_penalty}")
                
                logger.info(f"🚀 開始調用統一 AI 引擎...")
                logger.info(f"📋 最終 Options: num_predict={num_predict}, num_ctx={num_ctx}, temp={options.get('temperature')}")
                if options.get('stop'):
                    logger.info(f"📋 停止序列 ({len(options['stop'])} 個): {options['stop'][:5]}...")  # 只顯示前5個

                # 使用統一的 AI 引擎處理
                response_text = ai_engine_manager.process_text(prompt, current_model, options)

                logger.info(f"✅ AI 引擎響應成功")

                # 🔧 檢查 AI 回應是否有效（不是 prompt 回顯）
                logger.info(f"🔍 AI 回應檢查: response_text存在={bool(response_text)}, 長度={len(response_text) if response_text else 0}")

                # 🔧 重試機制：如果第一次返回空內容，使用簡化 prompt 重試一次
                if not response_text or len(response_text.strip()) == 0:
                    logger.warning(f"⚠️ AI 第一次返回空內容，使用簡化 prompt 重試...")

                    # 簡化的 prompt，移除所有複雜指令
                    simple_prompt = f"""請用台灣繁體中文整理以下內容的重點。嚴禁出現任何簡體字（如：用「軟體」不用「軟件」，用「資料」不用「數據」，用「網路」不用「網絡」）。

{chunk.strip()}

請直接輸出整理結果（使用 Markdown 格式）："""

                    # 使用更保守的參數重試
                    retry_options = options.copy()
                    retry_options['temperature'] = 0.1  # 降低溫度

                    logger.info(f"🔄 重試參數: temp={retry_options['temperature']}, num_predict={num_predict}")
                    logger.info(f"🔄 簡化 Prompt 長度: {len(simple_prompt)} 字符")

                    try:
                        response_text = ai_engine_manager.process_text(simple_prompt, current_model, retry_options)
                        if response_text and len(response_text.strip()) > 0:
                            logger.info(f"✅ 重試成功！AI 返回內容長度: {len(response_text)} 字符")
                        else:
                            logger.error(f"❌ 重試後仍然返回空內容")
                    except Exception as retry_error:
                        logger.error(f"❌ 重試時發生錯誤: {str(retry_error)}")
                        response_text = ""

                is_valid_response = True
                if response_text:
                    logger.info(f"🔍 回應預覽: {response_text[:200]}...")

                    # 檢查1: 完全相同
                    if response_text == prompt:
                        logger.error("❌ AI 回應與 prompt 完全相同（模型直接回顯）")
                        is_valid_response = False

                    # 檢查2: 回應是否以指令性關鍵字開頭（表示模型在重複指令而非執行）
                    instruction_keywords = [
                        "請整理以下", "【核心要求】", "【必須包含", "【原始內容】",
                        "請開始整理", "請總結以下", "極致詳細：", "多維分析："
                    ]
                    response_start = response_text[:300]
                    if any(keyword in response_start for keyword in instruction_keywords):
                        logger.error(f"❌ AI 回應包含指令關鍵字（模型在重複指令）: {response_start[:100]}...")
                        is_valid_response = False

                    # 檢查3: 回應是否包含超過50%的prompt內容（相似度檢查）
                    prompt_first_500 = prompt[:500]
                    if len(response_text) > 100 and prompt_first_500 in response_text:
                        logger.error(f"❌ AI 回應包含大量 prompt 內容（可能是回顯）")
                        is_valid_response = False

                    # 檢查4: 偵測 thinking 模式洩漏（英文推理或迴圈）
                    if is_valid_response and len(response_text) > 200:
                        # 4a: 中文比例過低（可能是英文推理內容）
                        chinese_count = len(re.findall(r'[\u4e00-\u9fff]', response_text))
                        chinese_ratio = chinese_count / len(response_text)
                        if chinese_ratio < 0.2:
                            logger.error(f"❌ AI 回應中文比例過低 ({chinese_ratio:.1%})，可能是 thinking 模式洩漏")
                            is_valid_response = False

                        # 4b: 偵測嚴重迴圈（同一行佔總行數 30%+ 且重複 20 次以上）
                        lines = [l.strip() for l in response_text.split('\n') if l.strip()]
                        if len(lines) > 20:
                            from collections import Counter
                            line_counts = Counter(lines)
                            top_line, top_count = line_counts.most_common(1)[0]
                            loop_ratio = top_count / len(lines)
                            if top_count >= 20 and loop_ratio > 0.3:
                                logger.error(f"❌ AI 回應包含嚴重迴圈: '{top_line[:50]}...' 重複 {top_count} 次 ({loop_ratio:.0%})")
                                is_valid_response = False

                if response_text and is_valid_response:
                    summary = response_text.strip()
                    logger.info(f"🎯 AI 處理第 {i+1} 段完成，輸出長度: {len(summary)} 字符")

                    # 🔧 調試：檢查 AI 回應內容
                    logger.info(f"🤖 AI 回應預覽: {summary[:300]}...")

                    # 🔧 移除早期檢測機制 - 不再檢查和強制清理重複內容

                    # 🔧 檢查是否是範例回應
                    if "基於先前提供的指令和要求" in summary or "整理後的內容應包括但不限於" in summary:
                        logger.error("❌ AI 輸出了範例回應而不是實際處理結果！")
                        logger.error(f"❌ 問題回應: {summary[:500]}...")
                        logger.error(f"❌ 原始 chunk 內容: {chunk[:200]}...")
                        logger.error(f"❌ 使用的 prompt 前500字: {prompt[:500]}...")
                    
                    # 🔧 修復：只清理開頭的指令性文字，不要刪除內容中的分隔符
                    original_summary = summary

                    # 只在文本開頭處理指令性前綴
                    instruction_prefixes = [
                        "請立即", "根據以下", "直接輸出", "立即開始", "整理結果：",
                        "好的，我", "讓我來", "我將", "我會", "以下是"
                    ]

                    # 只清理開頭100字符內的指令前綴
                    if len(summary) > 100:
                        first_part = summary[:100]
                        for prefix in instruction_prefixes:
                            if prefix in first_part:
                                marker_pos = summary.find(prefix)
                                if marker_pos < 100:  # 只清理開頭部分
                                    # 找到第一個真正的內容（以 ## 或 # 開頭的行）
                                    content_start = summary.find('\n## ', marker_pos)
                                    if content_start < 0:
                                        content_start = summary.find('\n# ', marker_pos)
                                    if content_start > 0 and content_start < 200:
                                        summary = summary[content_start:].strip()
                                        logger.info(f"✅ 清理開頭指令: {prefix}, 新長度: {len(summary)}")
                                        break

                    # 不要移除分隔線！--- 和 === 是有效的 Markdown 語法
                    # 只移除過多的連續空行（re 已在模組頂層 import）
                    summary = re.sub(r'\n{3,}', '\n\n', summary)  # 最多保留兩個換行
                    
                    # 如果清理後內容太短，保留原始回應
                    if len(summary.strip()) < 50 and len(original_summary) > 50:
                        logger.warning("⚠️ 清理後內容過短，保留原始回應")
                        summary = original_summary

                    # ✅ 移除過度清理邏輯，保留AI原始輸出的完整性

                    # 🔧 移除重複內容檢測和清理機制 - 直接使用 AI 原始輸出
                    # cleaned_summary = clean_ai_duplications(summary)
                    cleaned_summary = summary  # 直接使用 AI 輸出，不做去重處理

                    # 🔧 修復：調整結果長度檢查標準，支援詳細模式
                    min_expected_length = 200 if detail_level == "detailed" else 100 if detail_level == "normal" else 50

                    if cleaned_summary and len(cleaned_summary) >= min_expected_length:
                        organized_chunks.append(cleaned_summary)
                        logger.info(f"✅ AI 處理第 {i+1} 段成功: {len(cleaned_summary)} 字符")
                    elif cleaned_summary and len(cleaned_summary) >= 30:  # 至少有基本內容
                        logger.warning(f"⚠️ AI 處理第 {i+1} 段結果較短但可接受: {len(cleaned_summary)} 字符")
                        organized_chunks.append(cleaned_summary)
                    else:
                        logger.error(f"❌ AI 處理第 {i+1} 段結果過短: {len(cleaned_summary)} 字符")
                        # 保留原文而非錯誤訊息，讓用戶看到實際內容
                        organized_chunks.append(chunk)
                else:
                    logger.warning(f"⚠️ AI 處理第 {i+1} 段響應為空或與 prompt 相同")
                    logger.error(f"❌ 模型 {current_model} 無法處理此內容")
                    logger.error(f"❌ 可能原因: 1) 模型未正確加載 2) Prompt 過於複雜 3) 模型資源不足")
                    logger.error(f"❌ 建議: 切換到其他模型或使用簡化的處理模式")
                    # 提供原始轉錄文本，而非錯誤訊息
                    organized_chunks.append(chunk)
                    
            except Exception as chunk_error:
                logger.error(f"❌ AI 處理第 {i+1} 段發生異常: {str(chunk_error)}")
                organized_chunks.append(f"⚠️ **處理異常: {str(chunk_error)}**\\n\\n原始內容：\\n{chunk}")
        
        final_result = "\\n\\n".join(organized_chunks)

        # 🔧 移除最終去重處理 - 保持 AI 原始輸出
        # final_result = clean_ai_duplications(final_result)
        logger.info(f"🎯 最終結果長度: {len(final_result)} 字符")
        
        # AI 處理完成後，重新載入 Whisper 模型以備後續使用
        try:
            logger.info("🔄 AI 處理完成，準備重新載入 Whisper 模型...")
            # 這裡可以觸發 Whisper 模型的重新載入
            # 但為了避免循環依賴，我們只清理記憶體
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                logger.info("✅ AI 處理後 GPU 記憶體已清理")
        except Exception as e:
            logger.warning(f"⚠️ AI 處理後清理 GPU 記憶體時出現警告: {e}")
        
        return final_result
        
    except Exception as e:
        logger.error(f"💥 AI 整理嚴重失敗: {str(e)}")
        return f"⚠️ **系統處理失敗**: {str(e)}\\n\\n**原始內容：**\\n{text}"

# 兼容性包裝器，保持向後兼容
def organize_text_with_ollama(text, mode="default", detail_level="normal", ai_model=None,
                             custom_mode_prompt=None, custom_detail_prompt=None, custom_format_template=None,
                             selected_tags=None, custom_prompt=None, task_id=None):
    """向後兼容包裝器 - 重定向到新的統一 AI 引擎函數"""
    logger.warning("⚠️ 使用了已廢棄的 organize_text_with_ollama 函數，請更新為 organize_text_with_ai")
    return organize_text_with_ai(text, mode, detail_level, ai_model,
                                custom_mode_prompt, custom_detail_prompt, custom_format_template,
                                selected_tags, custom_prompt, task_id)

def split_text_into_chunks(text, max_size):
    """智能文字分段 - 優化版本，基於處理時間限制"""
    logger.info(f"🔪 開始智能分段：文本長度 {len(text)} 字符，每段最大 {max_size} 字符")
    
    if len(text) <= max_size:
        logger.info(f"✅ 文本無需分段")
        return [text]
    
    chunks = []
    current_pos = 0
    chunk_count = 0
    
    while current_pos < len(text):
        chunk_count += 1
        end_pos = min(current_pos + max_size, len(text))
        
        # 如果不是最後一段，尋找適當的分段點
        if end_pos < len(text):
            # 優先尋找段落分隔符（雙換行）
            best_split = end_pos
            for i in range(end_pos, max(current_pos, end_pos - 300), -1):
                if i < len(text) and text[i:i+2] == '\\n\\n':
                    best_split = i + 2
                    break
                # 其次尋找句號
                elif i < len(text) and text[i] in '。！？':
                    best_split = i + 1
                    break
                # 最後尋找句號標點
                elif i < len(text) and text[i] in '，、；：':
                    best_split = i + 1
            
            end_pos = best_split
        
        chunk = text[current_pos:end_pos].strip()
        if chunk:
            chunks.append(chunk)
            estimated_time = len(chunk) * 0.196  # 基於實測處理速度
            logger.info(f"📄 段落 {chunk_count}: {len(chunk)} 字符，預估處理時間 {estimated_time:.1f} 秒")
        
        current_pos = end_pos
    
    logger.info(f"🔪 分段完成：總共 {len(chunks)} 段")
    total_estimated_time = sum(len(chunk) * 0.196 for chunk in chunks)
    logger.info(f"⏱️ 總預估處理時間：{total_estimated_time:.1f} 秒 ({total_estimated_time/60:.1f} 分鐘)")
    
    # 安全檢查：如果預估時間超過25分鐘，發出警告
    if total_estimated_time > 1500:
        logger.warning(f"⚠️ 預估處理時間較長 ({total_estimated_time/60:.1f} 分鐘)，建議考慮使用簡化模式")
    
    return chunks

def clean_ai_duplications(text):
    """清理 AI 輸出中的重複內容 - 強化版本"""
    if not text or not isinstance(text, str):
        return ""

    logger.info(f"🧹 開始清理 AI 重複內容，原始長度: {len(text)} 字符")
    original_text = text

    # 🔧 強化清理：處理各種重複模式

    # 0. 首先清理重複的單詞和短語（最嚴重的問題）
    def remove_word_repetitions(text):
        """移除句子中重複的單詞和短語"""
        # 移除重複的中文詞組（如：先前的...先前的...）
        text = re.sub(r'(\S{2,})[，、。；：\s]*(\1[，、。；：\s]*){2,}', r'\1', text)
        # 移除重複的英文單詞
        text = re.sub(r'\b(\w+)\s+(\1\s+){2,}', r'\1 ', text)
        return text

    text = remove_word_repetitions(text)
    logger.info(f"🧹 移除單詞重複後長度: {len(text)} 字符")

    # 1. 清理重複的標題（嚴重問題）
    def remove_duplicate_headers(text):
        """移除重複的 Markdown 標題"""
        lines = text.split('\n')
        seen_headers = {}
        cleaned_lines = []

        for line in lines:
            # 檢測標題行
            if re.match(r'^#+\s+', line):
                # 標準化標題文字（移除 emoji、符號、空格差異）
                normalized = re.sub(r'[#\s\*\*emoji️⃣0-9０-９①-⑳]', '', line).strip()
                normalized = re.sub(r'[，、。；：]', '', normalized)

                if normalized:
                    # 檢查是否已見過相似標題
                    is_duplicate = False
                    for seen_norm, seen_line in seen_headers.items():
                        # 計算相似度
                        if normalized == seen_norm or normalized in seen_norm or seen_norm in normalized:
                            is_duplicate = True
                            logger.info(f"🗑️ 移除重複標題: {line[:50]}...")
                            break

                    if not is_duplicate:
                        seen_headers[normalized] = line
                        cleaned_lines.append(line)
                else:
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    text = remove_duplicate_headers(text)
    logger.info(f"🧹 移除重複標題後長度: {len(text)} 字符")

    # 2. 先按段落分割（保留雙換行符結構）
    paragraphs = re.split(r'\n\s*\n', text)
    unique_paragraphs = []
    seen_paragraphs = set()
    
    for para in paragraphs:
        para_clean = para.strip()
        if para_clean:
            # 檢查是否完全重複
            if para_clean not in seen_paragraphs:
                seen_paragraphs.add(para_clean)
                unique_paragraphs.append(para)
            else:
                logger.info(f"🗑️ 移除重複段落: {para_clean[:50]}...")
    
    # 2. 重新組合段落，保持雙換行符分隔
    text = '\n\n'.join(unique_paragraphs)
    
    # 3. 只清理明顯的重複句子（在同一段落內）
    def clean_paragraph_duplicates(paragraph):
        sentences = re.split(r'([。！？])', paragraph)
        # 重新組合句子和標點
        combined_sentences = []
        for i in range(0, len(sentences), 2):
            if i < len(sentences):
                sentence = sentences[i].strip()
                punctuation = sentences[i+1] if i+1 < len(sentences) else ''
                if sentence:
                    combined_sentences.append(sentence + punctuation)
        
        # 移除完全相同的句子
        seen_sentences = set()
        filtered_sentences = []
        
        for sentence in combined_sentences:
            sentence_clean = re.sub(r'[，、；：]', '', sentence.strip())
            if sentence_clean not in seen_sentences and len(sentence_clean) > 5:
                seen_sentences.add(sentence_clean)
                filtered_sentences.append(sentence)
            elif len(sentence_clean) <= 5:
                filtered_sentences.append(sentence)  # 保留短句子
        
        return ''.join(filtered_sentences)
    
    # 4. 對每個段落單獨處理
    cleaned_paragraphs = []
    for para in unique_paragraphs:
        if para.strip():
            cleaned_para = clean_paragraph_duplicates(para)
            if cleaned_para.strip():
                cleaned_paragraphs.append(cleaned_para.strip())
    
    # 5. 重新組合，保持段落結構
    final_text = '\n\n'.join(cleaned_paragraphs)
    
    # 6. 只做必要的格式清理，保留markdown格式
    final_text = re.sub(r'\n{3,}', '\n\n', final_text)  # 限制最多2個換行符
    final_text = re.sub(r'[。！？]{2,}', '。', final_text)  # 清理重複標點
    final_text = final_text.strip()
    
    # 7. 安全檢查 - 如果清理太多，保留原文
    if len(final_text) < len(original_text) * 0.3 and len(original_text) > 100:
        logger.warning("⚠️ 清理過度，保留原始內容")
        return original_text
    
    logger.info(f"🧹 完成清理 AI 重複內容，清理後長度: {len(final_text)} 字符")
    logger.info(f"🧹 清理率: {((len(original_text) - len(final_text)) / len(original_text) * 100):.1f}%")
    
    return final_text

def detect_severe_duplication(text):
    """檢測嚴重的重複問題，包括相似內容的重複"""
    if not text or len(text) < 100:
        return False

    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # 檢查 0: 檢測重複的 Markdown 標題（最常見的問題）
    headers = [line for line in lines if re.match(r'^#+\s+', line)]
    if headers:
        normalized_headers = {}
        for header in headers:
            # 標準化：移除 # 符號、emoji、數字、空格
            norm = re.sub(r'[#\s\*\*emoji️⃣0-9０-９①-⑳，、。；：]', '', header).strip()
            if norm:
                normalized_headers[norm] = normalized_headers.get(norm, 0) + 1

        for norm_header, count in normalized_headers.items():
            if count >= 2:  # 同樣的標題出現2次就是問題
                logger.error(f"❌ 檢測到重複標題: '{norm_header[:30]}...' 出現 {count} 次")
                return True

    # 檢查 0.5: 檢測句子中的重複詞組（如：先前的...先前的...）
    # 排除常見的英文功能詞和中文虛詞
    excluded_words = {
        # 英文功能詞
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'can',
        'could', 'should', 'may', 'might', 'must', 'that', 'this', 'these',
        'those', 'it', 'its', 'he', 'she', 'his', 'her', 'we', 'our', 'they',
        'their', 'i', 'my', 'me', 'you', 'your',
        # 中文虛詞
        '的', '了', '是', '在', '有', '和', '與', '或', '但', '也', '都', '就',
        '還', '又', '再', '更', '很', '太', '最', '以', '可以', '可能', '應該'
    }

    for line in lines:
        if len(line) > 20:
            # 檢測重複的2-10個字的詞組
            words = re.findall(r'\S{2,10}', line)
            if words:
                word_counts = {}
                for word in words:
                    # 只統計非功能詞
                    if word.lower() not in excluded_words:
                        word_counts[word] = word_counts.get(word, 0) + 1
                # 如果任何內容詞在同一行出現4次以上（提高閾值）
                for word, count in word_counts.items():
                    if count >= 4 and len(word) >= 2:
                        logger.error(f"❌ 檢測到詞組重複: '{word}' 在同一行出現 {count} 次")
                        return True

    # 檢查 1: 完全相同的行重複超過限制
    line_counts = {}
    for line in lines:
        if len(line) > 20:
            line_counts[line] = line_counts.get(line, 0) + 1

    for line, count in line_counts.items():
        if count > 5:  # 降低閾值：同樣的行出現5次就是問題
            logger.error(f"❌ 檢測到嚴重重複: '{line[:50]}...' 重複了 {count} 次")
            return True
    
    # 檢查 2: 相似度高的句子重複（針對您的例子）
    sentence_groups = {}
    for line in lines:
        if len(line) > 30:
            # 提取關鍵詞組合作為特徵
            key_phrases = []
            if "雲市集計畫" in line:
                key_phrases.append("雲市集")
            if "未來規劃" in line:
                key_phrases.append("未來規劃")
            if "國中" in line and "合作對象" in line:
                key_phrases.append("國中合作")
            if "異業結盟" in line:
                key_phrases.append("異業結盟")
            if "中小型創發署" in line:
                key_phrases.append("創發署")
            
            # 如果有關鍵短語，歸類
            if key_phrases:
                phrase_key = '+'.join(sorted(key_phrases))
                if phrase_key not in sentence_groups:
                    sentence_groups[phrase_key] = []
                sentence_groups[phrase_key].append(line)
    
    # 檢查是否有相似句子組重複超過 3 次
    for phrase_key, sentences in sentence_groups.items():
        if len(sentences) > 3:
            logger.error(f"❌ 檢測到主題重複: '{phrase_key}' 相關內容出現 {len(sentences)} 次")
            logger.error(f"   例如: '{sentences[0][:50]}...'")
            return True
    
    # 檢查 3: 文本長度異常（可能是重複導致）- 進一步放寬閾值
    total_chars = len(text)
    unique_chars = len(set(text.replace(' ', '').replace('\n', '')))
    # 大幅放寬檢測條件：只有極端重複才觸發（文本很長但獨特字符極少）
    if total_chars > 2000 and unique_chars < total_chars * 0.08:  # 從0.15降到0.08，長度閾值從1000提高到2000
        logger.error(f"❌ 檢測到異常重複模式: 文本長度 {total_chars}，但獨特字符只有 {unique_chars}")
        return True
    
    # 檢查 4: 常見開頭重複過多
    prefix_counts = {}
    for line in lines:
        if len(line) > 15:
            prefix = line[:15]
            prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    
    for prefix, count in prefix_counts.items():
        if count > 8:  # 放寬到同樣開頭超過 8 次才觸發
            logger.error(f"❌ 檢測到開頭模式重複: '{prefix}...' 出現 {count} 次")
            return True
    
    return False

def clean_whisper_output(text):
    """清理 Whisper 輸出文本"""
    if not text or not isinstance(text, str):
        return ""

    # 🔧 修復 Whisper 字符損壞：。替換 n 的問題
    # 檢測並修復常見的英文單詞中的字符損壞
    common_patterns = [
        (r'i。', 'in'),      # i。a → in a, i。dustry → industry
        (r'o。', 'on'),      # o。the → on the
        (r'avi。g', 'aving'), # havi。g → having
        (r'fi。', 'fin'),    # fi。cial → financial, fi。d → find
        (r'ca。', 'can'),    # ca。not → cannot
        (r'。ot', 'not'),    # 。ot → not
        (r'。ow', 'now'),    # 。ow → now
        (r'。eed', 'need'),  # 。eed → need
        (r'eve。', 'even'),  # eve。 → even
        (r'the。', 'then'),  # the。 → then
        (r'whe。', 'when'),  # whe。 → when
        (r'bee。', 'been'),  # bee。 → been
        (r'see。', 'seen'),  # see。 → seen
    ]

    for pattern, replacement in common_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 通用模式：修復英文單詞中間的。
    # 如果。前後都是英文字母，很可能是 n 被誤識別
    # 特殊處理：。前後有空格時，替換為 'n '，否則替換為 'n'
    text = re.sub(r'([a-z])。\s+([a-z])', r'\1n \2', text, flags=re.IGNORECASE)  # i。 a → in a
    text = re.sub(r'([a-z])。([a-z])', r'\1n\2', text, flags=re.IGNORECASE)     # i。dustry → industry

    text = re.sub(r'\\[.*?\\]', '', text)
    text = re.sub(r'\\(.*?\\)', '', text)

    # 🔧 Whisper 幻覺短語清理（來自 YouTube 字幕訓練數據）
    hallucination_patterns = [
        r'中文字幕志願者\s*李宗盛',   # 最常見的 Whisper 幻覺
        r'字幕志願者\s*\w{0,4}',      # 字幕志願者 + 任意名字
        r'字幕由\s*\S+\s*提供',
        r'字幕製作\s*\S+',
        r'字幕校對\s*\S+',
        r'感謝觀看',
        r'謝謝觀看',
        r'訂閱頻道',
        r'請訂閱',
        r'按讚訂閱',
        r'Subtitles?\s+by\s+\S+',
        r'Amara\.org',
    ]
    for pattern in hallucination_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # 🔧 清除 Whisper 停頓標記（省略號）
    text = re.sub(r'\.{2,}', '', text)   # 連續兩個以上的半形點
    text = re.sub(r'…+', '', text)        # Unicode 省略號（U+2026）

    text = re.sub(r'\\s+', ' ', text)
    text = text.strip()

    return text

def advanced_text_deduplication(text):
    """強化版文字去重處理"""
    if not text or len(text) < 10:
        return text
    
    char_patterns = [
        (r'(.)\\1{4,}', r'\\1\\1\\1'),
        (r'(..)\\1{3,}', r'\\1\\1'),
        (r'(...)\\1{2,}', r'\\1\\1'),
    ]
    
    for pattern, replacement in char_patterns:
        text = re.sub(pattern, replacement, text)
    
    words = text.split()
    if len(words) < 3:
        return text
    
    processed_words = []
    prev_word = ""
    word_repeat_count = 0
    
    for word in words:
        clean_word = re.sub(r'[^\\w\\u4e00-\\u9fff]', '', word)
        
        if not clean_word:
            processed_words.append(word)
            continue
        
        if clean_word == prev_word:
            word_repeat_count += 1
            if word_repeat_count >= 3:
                continue
        else:
            word_repeat_count = 1
            prev_word = clean_word
        
        processed_words.append(word)
    
    filler_words = ['就是', '然後', '那個', '這個', '嗯', '啊', '呃', '呃呃', '嗯嗯']
    final_words = []
    filler_count = 0
    
    for word in processed_words:
        clean_word = re.sub(r'[^\\w\\u4e00-\\u9fff]', '', word)
        
        if clean_word in filler_words:
            filler_count += 1
            if filler_count >= 3:
                continue
        else:
            filler_count = 0
        
        final_words.append(word)
    
    return ' '.join(final_words)

def remove_repetitive_text(text):
    """移除重複文字 - 增強版"""
    if not text or len(text) < 10:
        return text
    
    sentences = re.split(r'[。！？\\n]', text)
    filtered_sentences = []
    sentence_counts = {}
    
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 3:
            continue
        
        clean_sentence = re.sub(r'[^\\w\\u4e00-\\u9fff]', '', sentence)
        
        is_duplicate = False
        similarity_threshold = 0.8
        
        for prev_sentence in filtered_sentences[-3:]:
            prev_clean = re.sub(r'[^\\w\\u4e00-\\u9fff]', '', prev_sentence)
            
            if clean_sentence == prev_clean:
                is_duplicate = True
                break
            
            if len(clean_sentence) > 5 and len(prev_clean) > 5:
                if clean_sentence in prev_clean or prev_clean in clean_sentence:
                    is_duplicate = True
                    break
            
            if len(clean_sentence) > 10 and len(prev_clean) > 10:
                similarity = SequenceMatcher(None, clean_sentence, prev_clean).ratio()
                if similarity > similarity_threshold:
                    is_duplicate = True
                    break
        
        if clean_sentence in sentence_counts:
            sentence_counts[clean_sentence] += 1
            if sentence_counts[clean_sentence] >= 3:
                is_duplicate = True
        else:
            sentence_counts[clean_sentence] = 1
        
        if not is_duplicate:
            filtered_sentences.append(sentence)
    
    result = '。'.join(filtered_sentences) + ('。' if filtered_sentences else '')
    return result

def enhanced_post_processing_pipeline(text):
    """增強版後處理管道"""
    if not text or not isinstance(text, str):
        return ""
    
    steps = [
        clean_whisper_output,
        advanced_text_deduplication,
        remove_repetitive_text,
        lambda x: re.sub(r'\\n+', '\\n', x),
        lambda x: re.sub(r' +', ' ', x),
        lambda x: x.strip()
    ]
    
    current_text = text
    logger.info(f"🔧 後處理管道開始: 原始文本長度 {len(text)} 字符")
    
    for i, step_func in enumerate(steps):
        try:
            previous_length = len(current_text)
            current_text = step_func(current_text)
            new_length = len(current_text)
            
            logger.info(f"🔧 步驟 {i+1} ({step_func.__name__ if hasattr(step_func, '__name__') else 'lambda'}): {previous_length} → {new_length} 字符")
            
            if len(current_text.strip()) < 10:
                logger.warning(f"⚠️ 步驟 {i+1} 後文本過短，中斷後處理")
                logger.warning(f"⚠️ 當前文本: '{current_text}'")
                break
        except Exception as e:
            logger.error(f"後處理步驟 {i+1} 失敗: {str(e)}")
            continue
    
    logger.info(f"🔧 後處理管道完成: 最終文本長度 {len(current_text)} 字符")
    
    if current_text and current_text[-1] not in '。！？':
        current_text += '。'
    
    return current_text