"""
文字處理服務 - 支援 Ollama 和 vLLM 的統一介面
"""
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from .ai_engine_service import ai_engine_manager
from prompt_config.prompt_config import PromptConfig, ProcessingMode, DetailLevel

logger = logging.getLogger(__name__)

class TextService:
    """文字處理服務 - 統一的 AI 引擎整合"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.ai_engine = ai_engine_manager
    
    def _check_ai_engine_status(self) -> bool:
        """檢查當前 AI 引擎狀態"""
        return self.ai_engine.check_health()
    
    async def process_text_async(self, text: str, model: str = None,
                                 mode: str = "default", detail_level: str = "normal",
                                 custom_mode_prompt: str = None, custom_detail_prompt: str = None,
                                 custom_format_template: str = None, selected_tags: List[str] = None,
                                 custom_prompt: str = None) -> str:  # 🔧 修復：添加 custom_prompt 參數
        """異步處理文字"""
        # 🔥 優先檢查是否使用自定義 Prompt（完全繞過標籤處理）
        if selected_tags and "custom" in selected_tags and custom_prompt:
            prompt = f"""{custom_prompt.strip()}

【原始內容】
{text.strip()}"""
            logger.info(f"✅ [text_service async] 使用自定義 Prompt（長度: {len(custom_prompt)} 字符）")
        else:
            prompt = self._generate_prompt(
                text, mode, detail_level,
                custom_mode_prompt, custom_detail_prompt, custom_format_template, selected_tags
            )
        
        # 準備處理選項
        options = self._get_processing_options(detail_level)
        
        # 使用統一的 AI 引擎處理
        try:
            result = await self.ai_engine.process_text_async(prompt, model, options)
            return result
        except Exception as e:
            logger.error(f"異步文字處理失敗: {str(e)}")
            return text
    
    def process_text_batch(self, texts: List[str], model: str = None,
                          mode: str = "default", detail_level: str = "normal",
                          custom_mode_prompt: str = None, custom_detail_prompt: str = None,
                          custom_format_template: str = None, selected_tags: List[str] = None,
                          custom_prompt: str = None) -> List[str]:  # 🔧 修復：添加 custom_prompt 參數
        """批次處理文字"""
        results = []

        for text in texts:
            try:
                result = self.process_text_sync(
                    text, model, mode, detail_level,
                    custom_mode_prompt, custom_detail_prompt, custom_format_template, selected_tags,
                    custom_prompt  # 🔧 修復：傳遞 custom_prompt
                )
                results.append(result)
            except Exception as e:
                logger.error(f"批次處理失敗: {str(e)}")
                results.append(text)
        
        return results
    
    def process_text_sync(self, text: str, model: str = None,
                         mode: str = "default", detail_level: str = "normal",
                         custom_mode_prompt: str = None, custom_detail_prompt: str = None,
                         custom_format_template: str = None, selected_tags: List[str] = None,
                         custom_prompt: str = None) -> str:  # 🔧 修復：添加 custom_prompt 參數
        """同步處理文字"""
        # 🔥 優先檢查是否使用自定義 Prompt（完全繞過標籤處理）
        if selected_tags and "custom" in selected_tags and custom_prompt:
            prompt = f"""{custom_prompt.strip()}

【原始內容】
{text.strip()}"""
            logger.info(f"✅ [text_service] 使用自定義 Prompt（長度: {len(custom_prompt)} 字符）")
        else:
            prompt = self._generate_prompt(
                text, mode, detail_level,
                custom_mode_prompt, custom_detail_prompt, custom_format_template, selected_tags
            )
        
        # 準備處理選項
        options = self._get_processing_options(detail_level)
        
        # 使用統一的 AI 引擎處理
        try:
            result = self.ai_engine.process_text(prompt, model, options)
            return result
        except Exception as e:
            logger.error(f"同步文字處理失敗: {str(e)}")
            return text
    
    def _get_processing_options(self, detail_level: str = "detailed") -> Dict[str, Any]:
        """獲取處理選項 - 固定使用詳細模式，無輸出限制"""
        # 固定使用 detailed 模式配置
        # 🔧 優化：降低懲罰參數，讓模型能更自然地展開論述
        return {
            "num_predict": -1,        # -1 = 無限制輸出（Ollama 特性）
            "temperature": 0.3,       # 較低溫度，確保輸出穩定性
            "num_ctx": 32768,         # 32k 上下文窗口
            "top_p": 0.95,            # 鼓勵持續生成
            "repeat_penalty": 1.05,   # 🔧 降低：允許更自然的重複（相關概念展開）
            "top_k": 80,              # 🔧 提高：更多詞彙選擇
            "mirostat": 0,
            "presence_penalty": 0.6,  # 🔧 降低：允許重複提及重要概念
            "frequency_penalty": 0.8  # 🔧 降低：允許詳細闘述
        }
    
    def _generate_prompt(self, text: str, mode: str, detail_level: str,
                        custom_mode_prompt: str = None, custom_detail_prompt: str = None,
                        custom_format_template: str = None, selected_tags: List[str] = None) -> str:
        """生成提示詞 - 使用完整的 PromptConfig 系統"""
        try:
            # Convert string parameters to enum values
            mode_enum = ProcessingMode(mode) if mode else ProcessingMode.DEFAULT
            # 固定使用 DETAILED 模式，忽略傳入的 detail_level 參數
            detail_enum = DetailLevel.DETAILED

            # Use PromptConfig to generate the full prompt with tag support
            prompt = PromptConfig.generate_prompt(
                text=text,
                mode=mode_enum,
                detail_level=detail_enum,
                custom_mode_prompt=custom_mode_prompt,
                custom_detail_prompt=custom_detail_prompt,
                custom_format_template=custom_format_template,
                selected_tags=selected_tags
            )
            return prompt

        except ValueError as e:
            # Fallback to simple prompt if parameter conversion fails
            logger.warning(f"無法使用 PromptConfig 生成提示詞: {e}，使用簡化版")
            return f"請整理以下內容的重點：\n\n{text.strip()}"
        except Exception as e:
            logger.error(f"生成提示詞時發生錯誤: {e}，使用簡化版")
            return f"請整理以下內容的重點：\n\n{text.strip()}"
    
    def chunk_text(self, text: str, max_chars: int = 2000) -> List[str]:
        """將長文字分割成塊"""
        if len(text) <= max_chars:
            return [text]
        
        chunks = []
        sentences = text.split('。')
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= max_chars:
                current_chunk += sentence + '。'
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence + '。'
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def get_available_models(self) -> List[str]:
        """獲取可用的模型列表"""
        return self.ai_engine.get_available_models()
    
    def get_engine_info(self) -> Dict[str, Any]:
        """獲取當前引擎資訊"""
        return self.ai_engine.get_engine_info()
    
    def switch_engine(self, engine_type: str):
        """切換 AI 引擎"""
        self.ai_engine.switch_engine(engine_type)
        logger.info(f"🔄 TextService 已切換至 {engine_type} 引擎")

# 單例模式
text_service = TextService()