"""
AI 引擎服務 - 統一的 Ollama 和 vLLM 介面
"""
import logging
import os
import requests
import aiohttp
import json
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from config import config

logger = logging.getLogger(__name__)

class AIEngineInterface(ABC):
    """AI 引擎介面定義"""
    
    @abstractmethod
    def process_text(self, text: str, model: str, options: Dict[str, Any]) -> str:
        """同步處理文字"""
        pass
    
    @abstractmethod
    async def process_text_async(self, text: str, model: str, options: Dict[str, Any]) -> str:
        """異步處理文字"""
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        """獲取可用模型列表"""
        pass
    
    @abstractmethod
    def check_health(self) -> bool:
        """檢查服務健康狀態"""
        pass

class OllamaEngine(AIEngineInterface):
    """Ollama 引擎實現"""

    def __init__(self, url: str, timeout: int):
        self.url = url
        self.timeout = timeout
        self._available_models = []

        # 🔧 優化：使用連接池提高性能
        self._session = requests.Session()
        # 配置連接池大小
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,  # 連接池大小
            pool_maxsize=20,      # 最大連接數
            max_retries=3,        # 重試次數
            pool_block=False      # 非阻塞模式
        )
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)
        logger.info("🔧 Ollama 引擎已啟用連接池（pool_size=20）")

    def _detect_loop_in_text(self, text: str) -> bool:
        """偵測文字中是否有嚴重的無限迴圈模式（同一行佔 30%+ 且重複 20 次以上）"""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if len(lines) < 20:
            return False
        from collections import Counter
        line_counts = Counter(lines)
        for line, count in line_counts.most_common(3):
            loop_ratio = count / len(lines)
            if count >= 20 and loop_ratio > 0.3 and len(line) > 5:
                logger.warning(f"⚠️ 偵測到嚴重迴圈: '{line[:50]}...' 重複 {count} 次 ({loop_ratio:.0%})")
                return True
        return False

    def _extract_chinese_content_from_thinking(self, thinking: str) -> str:
        """
        從 thinking 欄位中提取中文內容
        如果 thinking 內容是英文推理或迴圈垃圾，返回空字串讓上層重試
        """
        import re

        # 前置檢查：偵測迴圈模式 → 直接拒絕
        if self._detect_loop_in_text(thinking):
            logger.error("❌ thinking 包含無限迴圈，拒絕使用")
            return ""

        # 前置檢查：整體中文比例太低 → 拒絕（純英文推理）
        total_chars = len(thinking)
        chinese_chars_total = len(re.findall(r'[\u4e00-\u9fff]', thinking))
        if total_chars > 500 and chinese_chars_total / total_chars < 0.15:
            logger.error(f"❌ thinking 中文比例過低 ({chinese_chars_total}/{total_chars} = {chinese_chars_total/total_chars:.1%})，拒絕使用")
            return ""

        # 策略 1: 尋找第一個 Markdown 標題
        markdown_header_match = re.search(r'\n(#{1,6}\s+.+)', thinking)
        if markdown_header_match:
            start_pos = markdown_header_match.start() + 1
            content = thinking[start_pos:].strip()
            # 提取後再次檢查迴圈
            if not self._detect_loop_in_text(content):
                logger.info(f"🎯 在 thinking 中找到 Markdown 標題，從位置 {start_pos} 開始提取")
                return content

        # 策略 2: 尋找 Markdown 格式標記
        markdown_format_match = re.search(r'\n(\*\*[^*]+\*\*|##\s+)', thinking)
        if markdown_format_match:
            start_pos = markdown_format_match.start() + 1
            content = thinking[start_pos:].strip()
            if not self._detect_loop_in_text(content):
                logger.info(f"🎯 在 thinking 中找到 Markdown 格式，從位置 {start_pos} 開始提取")
                return content

        # 策略 3: 尋找大段中文文本
        paragraphs = thinking.split('\n\n')
        for i, para in enumerate(paragraphs):
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', para))
            if chinese_chars > 100:
                start_pos = thinking.find(para)
                content = thinking[start_pos:].strip()
                if not self._detect_loop_in_text(content):
                    logger.info(f"🎯 在 thinking 中找到大段中文內容 (第{i+1}段)")
                    return content

        # 所有策略都失敗 → 返回空字串，讓上層使用重試或原文
        logger.warning(f"⚠️ 無法從 thinking 中提取有效中文內容，返回空字串")
        return ""
    
    def process_text(self, text: str, model: str, options: Dict[str, Any]) -> str:
        """同步處理文字 - Ollama Chat 格式，支持 128k 上下文降級策略"""
        try:
            # 🚀 使用 chat format讓 TAIDE 更好理解任務
            original_options = options.copy()

            logger.info(f"📤 準備發送請求到 Ollama: model={model}, prompt_length={len(text)}")

            system_msg = "你是專業的台灣繁體中文內容整理助手。使用 Markdown 格式輸出，直接開始整理。所有輸出必須使用台灣繁體中文，嚴禁出現任何簡體字（如：用「軟體」不用「軟件」，用「資料」不用「數據」，用「網路」不用「網絡」）。"
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": text}
            ]

            # 🔍 記錄實際發送的消息結構
            logger.debug(f"📨 發送消息數量: {len(messages)}")
            for idx, msg in enumerate(messages):
                role = msg.get('role', 'unknown')
                content_preview = msg.get('content', '')[:200]
                logger.debug(f"   消息[{idx}] role={role}, content_length={len(msg.get('content', ''))}, preview={content_preview}...")

            # 第一次嘗試：使用原始參數
            # 🔧 優化：使用連接池 session 而非 requests.post
            # 🔧 關鍵修復：對推理模型使用 think: false 來禁用 thinking 輸出
            # 這樣模型仍會進行推理，但回應直接放在 content 中而非 thinking 中

            # 🔧 分離頂層參數和 options 參數
            # stop 序列需要在頂層，不在 options 裡
            stop_sequences = options.pop("stop", None) if options else None

            request_payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": options
            }

            # 添加 stop 序列（如果有）
            if stop_sequences:
                request_payload["stop"] = stop_sequences
                logger.info(f"🛑 設定 stop 序列: {stop_sequences}")

            # Thinking 模式（由配置控制，非模型偵測）
            try:
                from config import config
                think_mode = config.OLLAMA_THINK_MODE
                if think_mode and think_mode.lower() != 'off':
                    request_payload["think"] = think_mode
                    logger.info(f"🧠 Thinking 模式: {think_mode}")
            except Exception:
                pass

            response = self._session.post(
                f"{self.url}/api/chat",
                json=request_payload,
                timeout=self.timeout
            )

            logger.debug(f"📥 收到 Ollama 響應: status_code={response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    logger.debug(f"🔍 Ollama JSON 解析成功, keys={list(result.keys())}, done={result.get('done', 'N/A')}")

                    # 🔧 檢測是否因為 stop sequence 過早停止
                    eval_count = result.get('eval_count', 0)
                    done_reason = result.get('done_reason', '')

                    # 🔍 診斷：記錄所有情況下的生成統計
                    logger.info(f"📊 生成統計: eval_count={eval_count}, done_reason={done_reason}")
                    logger.info(f"📊 prompt_eval_count={result.get('prompt_eval_count', 'N/A')}")

                    # 🔧 早停檢測（僅記錄，不自動重試）
                    # 為了保持輸出完整性，不再自動重試
                    num_predict_requested = options.get('num_predict', 2048)
                    if eval_count > 0 and eval_count < num_predict_requested * 0.2:
                        percentage = (eval_count / num_predict_requested * 100) if num_predict_requested > 0 else 0
                        logger.warning(f"ℹ️ 模型生成了 {eval_count} 個 tokens ({percentage:.1f}% of {num_predict_requested})")
                        logger.warning(f"ℹ️ done_reason={done_reason}，模型認為內容已完整")
                        # 🔧 禁用自動重試：保持輸出完整性，尊重模型的停止決定
                        # 如果模型認為內容已完整（done_reason=stop），強制重試可能導致重複或不連貫的輸出

                    # 檢查響應結構
                    if 'message' not in result:
                        logger.error(f"❌ 響應中沒有 'message' 欄位! 完整響應: {result}")
                        return text

                    message = result.get('message', {})
                    logger.debug(f"📨 message keys={list(message.keys())}")

                    content = message.get('content', '')
                    logger.debug(f"🎯 提取的 content: 長度={len(content)}, 預覽={content[:200] if content else '(空)'}")

                    # 🔧 診斷：記錄完整的 message 結構以便調試
                    if not content or len(content.strip()) == 0:
                        logger.warning(f"⚠️ Content 為空，檢查完整 message 結構")
                        logger.warning(f"📋 完整 message keys: {list(message.keys())}")
                        for key, value in message.items():
                            if isinstance(value, str):
                                logger.warning(f"   {key}: {value[:100] if len(value) > 100 else value}")
                            else:
                                logger.warning(f"   {key}: {value}")

                    # 🔧 修復推理模型問題：如果 content 為空，使用 thinking 欄位
                    # 推理模型（如 gpt-oss:20b）會將實際回應放在 thinking 中
                    if not content or len(content.strip()) == 0:
                        thinking = message.get('thinking', '')
                        if thinking and len(thinking.strip()) > 0:
                            logger.info(f"✅ 推理模型檢測：使用 thinking 欄位作為回應")
                            logger.info(f"📋 thinking 原始長度: {len(thinking)}")
                            logger.info(f"📋 thinking 前500字: {thinking[:500]}")

                            # 檢查 thinking 中是否包含中文內容
                            import re
                            chinese_char_count = len(re.findall(r'[\u4e00-\u9fff]', thinking))
                            chinese_percentage = (chinese_char_count / len(thinking) * 100) if len(thinking) > 0 else 0

                            logger.info(f"📊 thinking 中文字符: {chinese_char_count} ({chinese_percentage:.1f}%)")

                            # 如果 thinking 基本沒有中文（<10%），說明模型只在推理沒有生成內容
                            if chinese_percentage < 10:
                                logger.error(f"❌ thinking 欄位幾乎沒有中文內容 ({chinese_percentage:.1f}%)，可能是模型只在推理未生成結果")
                                logger.error(f"💡 建議：這可能是推理模型配置問題，考慮切換到標準模型")
                                content = ""  # 返回空，讓上層使用原始文本
                            else:
                                # 🎯 清理 thinking 中的英文推理過程，提取中文內容
                                # thinking 格式通常是：[English reasoning...]\n\n[Chinese formatted content]
                                cleaned_thinking = self._extract_chinese_content_from_thinking(thinking)

                                logger.info(f"📋 提取後長度: {len(cleaned_thinking) if cleaned_thinking else 0}")

                                if cleaned_thinking and len(cleaned_thinking.strip()) > 100:
                                    logger.info(f"✅ 從 thinking 提取中文內容: {len(cleaned_thinking)} 字符")
                                    logger.info(f"📋 提取內容預覽: {cleaned_thinking[:200]}")
                                    content = cleaned_thinking
                                else:
                                    logger.warning(f"⚠️ thinking 清理後內容過短({len(cleaned_thinking) if cleaned_thinking else 0}字符)，直接使用原始 thinking")
                                    logger.warning(f"⚠️ 原始 thinking 將被使用，可能包含英文推理")
                                    content = thinking
                        else:
                            logger.warning(f"⚠️ content 和 thinking 都為空")
                            # 記錄完整的響應結構以便調試
                            logger.error(f"❌ 完整 Ollama 響應: {json.dumps(result, ensure_ascii=False, indent=2)}")

                    # 確保返回非空字符串
                    if not content or len(content.strip()) == 0:
                        logger.error("❌ AI 返回空內容，這不應該發生（content 和 thinking 都已處理）")
                        logger.error(f"❌ 模型: {model}")
                        logger.error(f"❌ Prompt 長度: {len(text)} 字符")
                        logger.error(f"❌ Options: {options}")
                        # 這種情況理論上不會發生，因為上面已經處理了 thinking
                        return ""  # 返回空字符串讓上層使用原始轉錄文本

                    logger.info(f"✅ 最終使用內容長度: {len(content)} 字符")

                    # 🔍 診斷：如果輸出過短，僅記錄資訊（不自動重試）
                    if len(content) < 3000:
                        logger.info(f"ℹ️ 輸出長度: {len(content)} 字符")
                        logger.info(f"   - eval_count: {eval_count} (實際生成的tokens)")
                        logger.info(f"   - done_reason: {done_reason}")
                        logger.info(f"   - num_predict設定: {options.get('num_predict', 'N/A')}")
                        if eval_count < options.get('num_predict', 0) * 0.5:
                            logger.info(f"ℹ️ 模型在 num_predict 限制前完成生成（正常行為）")

                    return content

                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON 解析失敗: {e}")
                    logger.error(f"   響應文本: {response.text[:500]}")
                    return ""  # JSON 解析失敗，返回空字符串
                except Exception as e:
                    logger.error(f"❌ 處理響應時異常: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return ""  # 異常情況，返回空字符串
            else:
                error_detail = response.text if hasattr(response, 'text') else "無詳細錯誤信息"
                logger.error(f"Ollama API 錯誤: {response.status_code}")
                logger.error(f"錯誤詳情: {error_detail}")
                logger.error(f"請求參數: model={model}, num_ctx={options.get('num_ctx')}, num_predict={options.get('num_predict')}")
                
                # 嘗試獲取錯誤響應的 JSON
                try:
                    error_json = response.json()
                    logger.error(f"錯誤 JSON: {error_json}")
                except:
                    pass
                return text
                
        except Exception as e:
            logger.error(f"Ollama 處理失敗: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return text
    
    async def process_text_async(self, text: str, model: str, options: Dict[str, Any]) -> str:
        """異步處理文字 - Ollama 格式"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.url}/api/generate",
                    json={
                        "model": model,
                        "prompt": text,
                        "stream": False,
                        "options": options
                    },
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('response', text)
                    else:
                        logger.error(f"Ollama API 錯誤: {response.status}")
                        return text
            except Exception as e:
                logger.error(f"Ollama 異步處理失敗: {str(e)}")
                return text
    
    def get_available_models(self) -> List[str]:
        """獲取 Ollama 可用模型 - 🔧 優化：使用連接池"""
        try:
            response = self._session.get(f"{self.url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                self._available_models = [m['name'] for m in models]
                return self._available_models
        except Exception as e:
            logger.error(f"獲取 Ollama 模型失敗: {str(e)}")
        return []

    def check_health(self) -> bool:
        """檢查 Ollama 服務健康狀態 - 🔧 優化：使用連接池"""
        try:
            response = self._session.get(f"{self.url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama 健康檢查失敗: {str(e)}")
            return False

class VLLMEngine(AIEngineInterface):
    """vLLM 引擎實現"""

    def __init__(self, url: str, timeout: int):
        self.url = url
        self.timeout = timeout
        self._available_models = []

        # 🔧 優化：使用連接池提高性能
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=3,
            pool_block=False
        )
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)
        logger.info("🔧 vLLM 引擎已啟用連接池（pool_size=20）")
    
    def _estimate_token_count(self, text: str) -> int:
        """估算文字的 token 數量 (粗略估算: 中文字符*1.5 + 英文單詞*1)"""
        import re
        # 簡單的 token 估算
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        other_chars = len(text) - chinese_chars - english_words
        
        # 粗略估算: 中文字符約1.5個token，英文單詞約1個token，其他字符約0.5個token
        estimated_tokens = int(chinese_chars * 1.5 + english_words * 1 + other_chars * 0.5)
        return max(estimated_tokens, 100)  # 最少100個token
    
    def _convert_options_to_vllm(self, options: Dict[str, Any], input_text: str = "") -> Dict[str, Any]:
        """將 Ollama 格式選項轉換為 vLLM 格式，動態調整 max_tokens"""
        vllm_options = {}

        # 參數映射
        if 'temperature' in options:
            vllm_options['temperature'] = options['temperature']
        if 'top_p' in options:
            vllm_options['top_p'] = options['top_p']
        if 'top_k' in options:
            vllm_options['top_k'] = options['top_k']

        # 動態查詢 vLLM 實際的 max_model_len
        max_context_length = self._get_max_model_len()
        input_tokens = self._estimate_token_count(input_text)
        safety_buffer = 100  # 小緩衝區即可

        # 計算可用的輸出 token 數量
        available_tokens = max_context_length - input_tokens - safety_buffer

        # 處理 num_predict 或使用預設值
        if 'num_predict' in options:
            requested_tokens = options['num_predict']
            vllm_options['max_tokens'] = min(requested_tokens, available_tokens)
        else:
            default_tokens = 3000
            vllm_options['max_tokens'] = min(default_tokens, available_tokens)

        # 確保至少有一些輸出空間
        vllm_options['max_tokens'] = max(vllm_options['max_tokens'], 200)

        # 設定其他預設值
        vllm_options.setdefault('temperature', 0.08)
        vllm_options.setdefault('top_p', 0.7)

        # 記錄調試信息
        logger.info(f"vLLM token 計算: context={max_context_length}, 輸入≈{input_tokens}, 可用={available_tokens}, 設定={vllm_options['max_tokens']}")

        return vllm_options

    def _get_max_model_len(self) -> int:
        """查詢 vLLM 伺服器的實際 max_model_len"""
        if not hasattr(self, '_cached_max_model_len') or self._cached_max_model_len is None:
            try:
                response = self._session.get(f"{self.url}/v1/models", timeout=5)
                if response.status_code == 200:
                    models = response.json().get('data', [])
                    if models:
                        self._cached_max_model_len = models[0].get('max_model_len', 8192)
                        logger.info(f"🔧 vLLM max_model_len: {self._cached_max_model_len}")
                        return self._cached_max_model_len
            except Exception as e:
                logger.warning(f"⚠️ 無法查詢 vLLM max_model_len: {e}")
            # 回退值
            self._cached_max_model_len = int(os.getenv('VLLM_MAX_MODEL_LEN', '8192'))
        return self._cached_max_model_len
    
    def _format_prompt_for_vllm(self, text: str) -> List[Dict[str, str]]:
        """將純文字 prompt 轉換為 vLLM 對話格式"""
        return [
            {
                "role": "user",
                "content": text
            }
        ]
    
    def process_text(self, text: str, model: str, options: Dict[str, Any]) -> str:
        """同步處理文字 - vLLM 格式 - 🔧 優化：使用連接池"""
        try:
            vllm_options = self._convert_options_to_vllm(options, text)
            messages = self._format_prompt_for_vllm(text)

            # 🔧 優化：使用連接池 session
            response = self._session.post(
                f"{self.url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    **vllm_options
                },
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                # 🔧 修復：安全提取 API 回應內容，避免 KeyError/IndexError 崩潰
                try:
                    choices = result.get('choices', [])
                    if choices and len(choices) > 0:
                        content = choices[0].get('message', {}).get('content')
                        if content:
                            return content
                    logger.warning(f"vLLM API 回應格式異常: {result}")
                    return text
                except (KeyError, IndexError, TypeError) as e:
                    logger.error(f"vLLM API 回應解析失敗: {e}, 回應: {result}")
                    return text
            else:
                logger.error(f"vLLM API 錯誤: {response.status_code} - {response.text}")
                return text
                
        except Exception as e:
            logger.error(f"vLLM 處理失敗: {str(e)}")
            return text
    
    async def process_text_async(self, text: str, model: str, options: Dict[str, Any]) -> str:
        """異步處理文字 - vLLM 格式"""
        async with aiohttp.ClientSession() as session:
            try:
                vllm_options = self._convert_options_to_vllm(options, text)
                messages = self._format_prompt_for_vllm(text)
                
                async with session.post(
                    f"{self.url}/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": messages,
                        **vllm_options
                    },
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        # 🔧 修復：安全提取 API 回應內容，避免 KeyError/IndexError 崩潰
                        try:
                            choices = result.get('choices', [])
                            if choices and len(choices) > 0:
                                content = choices[0].get('message', {}).get('content')
                                if content:
                                    return content
                            logger.warning(f"vLLM API 異步回應格式異常: {result}")
                            return text
                        except (KeyError, IndexError, TypeError) as e:
                            logger.error(f"vLLM API 異步回應解析失敗: {e}, 回應: {result}")
                            return text
                    else:
                        error_text = await response.text()
                        logger.error(f"vLLM API 錯誤: {response.status} - {error_text}")
                        return text
            except Exception as e:
                logger.error(f"vLLM 異步處理失敗: {str(e)}")
                return text
    
    def get_available_models(self) -> List[str]:
        """獲取 vLLM 可用模型 - 🔧 優化：使用連接池"""
        try:
            response = self._session.get(f"{self.url}/v1/models", timeout=5)
            if response.status_code == 200:
                models_data = response.json()
                self._available_models = [m['id'] for m in models_data.get('data', [])]
                return self._available_models
        except Exception as e:
            logger.error(f"獲取 vLLM 模型失敗: {str(e)}")
        return []

    def check_health(self) -> bool:
        """檢查 vLLM 服務健康狀態 - 🔧 優化：使用連接池"""
        try:
            response = self._session.get(f"{self.url}/v1/models", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"vLLM 健康檢查失敗: {str(e)}")
            return False

class AIEngineManager:
    """AI 引擎管理器 - 統一介面"""
    
    def __init__(self):
        self.current_engine = None
        self._initialize_engine()
    
    def _initialize_engine(self):
        """根據配置初始化引擎"""
        if config.AI_ENGINE == "vllm":
            self.current_engine = VLLMEngine(
                url=config.VLLM_URL,
                timeout=config.VLLM_TIMEOUT
            )
            logger.info(f"✅ 初始化 vLLM 引擎: {config.VLLM_URL}")
        else:  # ollama
            self.current_engine = OllamaEngine(
                url=config.OLLAMA_URL,
                timeout=config.OLLAMA_TIMEOUT
            )
            logger.info(f"✅ 初始化 Ollama 引擎: {config.OLLAMA_URL}")
    
    def switch_engine(self, engine_type: str):
        """切換引擎類型"""
        if engine_type not in ["ollama", "vllm"]:
            raise ValueError(f"不支援的引擎類型: {engine_type}")
        
        config.AI_ENGINE = engine_type
        self._initialize_engine()
        logger.info(f"🔄 已切換至 {engine_type} 引擎")
    
    def get_current_model(self) -> str:
        """獲取當前配置的模型"""
        return config.get_current_ai_model()
    
    def process_text(self, text: str, model: str = None, options: Dict[str, Any] = None) -> str:
        """統一的同步文字處理介面"""
        if not self.current_engine:
            self._initialize_engine()
        
        model = model or self.get_current_model()
        options = options or {}
        
        return self.current_engine.process_text(text, model, options)
    
    async def process_text_async(self, text: str, model: str = None, options: Dict[str, Any] = None) -> str:
        """統一的異步文字處理介面"""
        if not self.current_engine:
            self._initialize_engine()
        
        model = model or self.get_current_model()
        options = options or {}
        
        return await self.current_engine.process_text_async(text, model, options)
    
    def get_available_models(self) -> List[str]:
        """獲取可用模型列表"""
        if not self.current_engine:
            self._initialize_engine()
        
        return self.current_engine.get_available_models()
    
    def check_health(self) -> bool:
        """檢查當前引擎健康狀態"""
        if not self.current_engine:
            self._initialize_engine()
        
        return self.current_engine.check_health()
    
    def get_engine_info(self) -> Dict[str, Any]:
        """獲取當前引擎資訊"""
        return {
            "engine_type": config.AI_ENGINE,
            "url": config.get_current_ai_url(),
            "model": self.get_current_model(),
            "timeout": config.get_current_ai_timeout(),
            "health": self.check_health(),
            "available_models": self.get_available_models()
        }

class RefinementEngineManager:
    """Refinement 專用引擎管理器

    支持混合引擎架構：摘要用 Ollama，refinement 用 vLLM。
    如果 REFINEMENT_ENGINE 與 AI_ENGINE 相同，則共用同一引擎。
    """

    def __init__(self):
        self._engine = None

    def _get_engine(self) -> AIEngineInterface:
        """獲取或創建 Refinement 引擎"""
        if self._engine is not None:
            return self._engine

        if config.REFINEMENT_ENGINE == config.AI_ENGINE:
            # 共用主引擎
            self._engine = ai_engine_manager.current_engine
            logger.info(f"🔗 Refinement 引擎共用主引擎: {config.REFINEMENT_ENGINE}")
        elif config.REFINEMENT_ENGINE == "vllm":
            self._engine = VLLMEngine(
                url=config.VLLM_URL,
                timeout=config.VLLM_TIMEOUT
            )
            logger.info(f"✅ Refinement 專用 vLLM 引擎: {config.VLLM_URL}")
        else:
            self._engine = OllamaEngine(
                url=config.OLLAMA_URL,
                timeout=config.OLLAMA_TIMEOUT
            )
            logger.info(f"✅ Refinement 專用 Ollama 引擎: {config.OLLAMA_URL}")

        return self._engine

    def process_text(self, text: str, model: str = None, options: Dict[str, Any] = None) -> str:
        """Refinement 專用文字處理"""
        engine = self._get_engine()
        model = model or config.get_refinement_model()
        options = options or {}
        return engine.process_text(text, model, options)

    def check_health(self) -> bool:
        """檢查 Refinement 引擎健康狀態"""
        engine = self._get_engine()
        return engine.check_health()

    def get_current_model(self) -> str:
        """獲取 Refinement 使用的模型"""
        return config.get_refinement_model()

# 全局 AI 引擎管理器實例
ai_engine_manager = AIEngineManager()
# Refinement 專用引擎管理器
refinement_engine_manager = RefinementEngineManager()