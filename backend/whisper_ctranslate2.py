"""
CTranslate2 優化的 Whisper 語音轉文字模組
提供比標準 Transformers 實作更快的推理速度和更低的記憶體使用
"""

import os
import time
import logging
import numpy as np
import torch
from typing import Optional, Tuple, List, Dict, Any
import ctranslate2

logger = logging.getLogger(__name__)

class WhisperCTranslate2:
    """使用 CTranslate2 優化的 Whisper 模型實作"""
    
    def __init__(self, model_path: str = None, model_size: str = "base", device: str = "auto"):
        """
        初始化 CTranslate2 Whisper 模型
        
        Args:
            model_path: 預轉換的 CTranslate2 模型路徑
            model_size: Whisper 模型大小 (tiny, base, small, medium, large)
            device: 設備類型 (auto, cpu, cuda)
        """
        self.model_path = model_path
        self.model_size = model_size
        self.device = device
        self.model = None
        self.tokenizer = None
        self.processor = None
        self.is_loaded = False
        
    def load_model(self) -> bool:
        """載入 CTranslate2 模型"""
        try:
            if self.model_path and os.path.exists(self.model_path):
                # 使用預轉換的 CTranslate2 模型
                logger.info(f"載入預轉換的 CTranslate2 模型: {self.model_path}")
                self.model = ctranslate2.models.Whisper(self.model_path, device=self.device)
            else:
                # 需要先轉換 Hugging Face 模型到 CTranslate2 格式
                logger.info(f"轉換並載入 Whisper {self.model_size} 模型到 CTranslate2 格式")
                self._convert_and_load_model()
            
            # 載入 tokenizer 和 processor
            self._load_tokenizer_and_processor()
            
            self.is_loaded = True
            logger.info(f"✅ CTranslate2 Whisper 模型載入成功")
            return True
            
        except Exception as e:
            logger.error(f"載入 CTranslate2 Whisper 模型失敗: {str(e)}")
            return False
    
    def _convert_and_load_model(self):
        """將 Hugging Face 模型轉換為 CTranslate2 格式並載入"""
        try:
            from transformers import WhisperProcessor, WhisperForConditionalGeneration
            
            # 載入原始 Hugging Face 模型
            model_id = f"openai/whisper-{self.model_size}"
            logger.info(f"正在載入原始模型: {model_id}")
            
            processor = WhisperProcessor.from_pretrained(model_id)
            model = WhisperForConditionalGeneration.from_pretrained(model_id)
            
            # 創建臨時目錄來存放轉換後的模型
            import tempfile
            temp_dir = tempfile.mkdtemp()
            ctranslate2_model_path = os.path.join(temp_dir, f"whisper-{self.model_size}-ct2")
            
            logger.info("正在轉換模型到 CTranslate2 格式...")
            
            # 轉換模型
            converter = ctranslate2.converters.TransformersConverter(
                model_id,
                load_as_float16=True,  # 使用 float16 以節省記憶體
                low_cpu_mem_usage=True
            )
            converter.convert(ctranslate2_model_path)
            
            # 載入轉換後的模型
            self.model = ctranslate2.models.Whisper(ctranslate2_model_path, device=self.device)
            
            # 保存轉換後的模型路徑
            self.model_path = ctranslate2_model_path
            
            logger.info("✅ 模型轉換完成")
            
        except Exception as e:
            logger.error(f"模型轉換失敗: {str(e)}")
            raise
    
    def _load_tokenizer_and_processor(self):
        """載入 tokenizer 和 processor"""
        try:
            from transformers import WhisperProcessor
            
            model_id = f"openai/whisper-{self.model_size}"
            self.processor = WhisperProcessor.from_pretrained(model_id)
            self.tokenizer = self.processor.tokenizer
            
        except Exception as e:
            logger.error(f"載入 tokenizer 和 processor 失敗: {str(e)}")
            raise
    
    def transcribe(self, audio: np.ndarray, sampling_rate: int = 16000, 
                   language: str = "chinese", task: str = "transcribe",
                   beam_size: int = 5, best_of: int = 5,
                   temperature: float = 0.0, initial_prompt: str = None) -> Dict[str, Any]:
        """
        使用 CTranslate2 進行語音轉文字
        
        Args:
            audio: 音頻數據 (numpy array)
            sampling_rate: 採樣率
            language: 語言代碼
            task: 任務類型 (transcribe/translate)
            beam_size: beam search 大小
            best_of: 最佳候選數量
            temperature: 溫度參數
            initial_prompt: 初始提示
            
        Returns:
            包含轉錄結果的字典
        """
        if not self.is_loaded:
            raise RuntimeError("模型未載入，請先調用 load_model()")
        
        try:
            # 準備音頻特徵
            features = self.processor(
                audio, 
                sampling_rate=sampling_rate, 
                return_tensors="pt"
            )
            
            # 將 numpy 數組轉換為 CTranslate2 的 StorageView 格式
            input_features = ctranslate2.StorageView.from_array(features["input_features"].numpy())
            
            # 設置生成參數 (只使用 CTranslate2 支持的參數)
            generation_config = {
                "beam_size": beam_size,
                "num_hypotheses": best_of,
                "sampling_temperature": temperature
            }
            
            # 根據 CTranslate2 官方文檔，Whisper 模型的 generate 方法需要 prompts 參數
            # prompts 必須是 List[List[str]] 或 List[List[int]] 格式
            try:
                # 使用 processor 來獲取正確的 forced_decoder_ids
                forced_decoder_ids = self.processor.get_decoder_prompt_ids(language=language, task=task)
                
                # 將 forced_decoder_ids 轉換為 prompts 格式
                if forced_decoder_ids is not None:
                    # 添加 <|startoftranscript|> token (ID: 50258) 到開頭
                    prompt_ids = [50258]  # <|startoftranscript|>
                    # 然後添加其他 token IDs
                    prompt_ids.extend([token_id for _, token_id in forced_decoder_ids])
                    prompts = [prompt_ids]  # 注意：必須是嵌套列表
                    logger.info(f"設置提示詞 IDs: {prompt_ids}")
                else:
                    # 如果沒有 forced_decoder_ids，至少使用 startoftranscript
                    prompts = [[50258]]  # 只包含 <|startoftranscript|>
                    logger.info("使用基本提示詞: [50258] (<|startoftranscript|>)")
            except Exception as e:
                logger.warning(f"無法獲取解碼器提示詞: {e}，使用基本提示詞")
                prompts = [[50258]]  # 使用 <|startoftranscript|>
            
            # 執行推理 (根據官方文檔格式，必須提供 prompts 參數)
            start_time = time.time()
            result = self.model.generate(input_features, prompts, **generation_config)
            inference_time = time.time() - start_time
            
            # 處理結果
            if result:
                # 解碼文本
                text = self.tokenizer.decode(result[0].sequences_ids[0])
                
                # 構建結果字典
                output = {
                    "text": text,
                    "language": language,
                    "task": task,
                    "inference_time": inference_time,
                    "model_size": self.model_size
                }
                
                # 添加語言檢測結果
                if hasattr(result[0], 'language'):
                    output["detected_language"] = result[0].language
                
                return output
            else:
                return {"text": "", "error": "推理失敗"}
                
        except Exception as e:
            logger.error(f"CTranslate2 推理失敗: {str(e)}")
            return {"text": "", "error": str(e)}
    
    def transcribe_batch(self, audio_list: List[np.ndarray], 
                         sampling_rate: int = 16000, **kwargs) -> List[Dict[str, Any]]:
        """批量轉錄多個音頻"""
        if not self.is_loaded:
            raise RuntimeError("模型未載入，請先調用 load_model()")
        
        results = []
        for i, audio in enumerate(audio_list):
            logger.info(f"處理音頻 {i+1}/{len(audio_list)}")
            result = self.transcribe(audio, sampling_rate, **kwargs)
            results.append(result)
        
        return results
    
    def get_model_info(self) -> Dict[str, Any]:
        """獲取模型信息"""
        if not self.is_loaded:
            return {"status": "未載入"}
        
        info = {
            "status": "已載入",
            "model_size": self.model_size,
            "device": self.device,
            "model_path": self.model_path,
            "backend": "CTranslate2"
        }
        
        # 獲取模型統計信息
        if hasattr(self.model, 'model_spec'):
            spec = self.model.model_spec
            info.update({
                "vocabulary_size": getattr(spec, 'vocabulary_size', 'N/A'),
                "num_layers": getattr(spec, 'num_layers', 'N/A'),
                "hidden_size": getattr(spec, 'hidden_size', 'N/A')
            })
        
        return info
    
    def cleanup(self):
        """清理資源"""
        if self.model:
            del self.model
            self.model = None
        
        if self.processor:
            del self.processor
            self.processor = None
        
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None
        
        self.is_loaded = False
        
        # 強制進行記憶體清理
        try:
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                logger.info(f"GPU 記憶體已清理，當前使用: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")
        except Exception as e:
            logger.warning(f"GPU 記憶體清理警告: {e}")
        
        logger.info("CTranslate2 Whisper 模型資源已清理")
    
    def _extract_timestamps_from_result(self, result, sampling_rate: int) -> List[Dict[str, Any]]:
        """從 CTranslate2 結果中提取時間戳"""
        try:
            timestamps = []
            
            # 檢查是否有 token 序列
            if hasattr(result, 'sequences_ids') and result.sequences_ids:
                token_ids = result.sequences_ids[0]
                
                if token_ids:
                    # 尋找時間戳 token (Whisper 的時間戳 token 範圍)
                    current_text = []
                    current_start = None
                    
                    for i, token_id in enumerate(token_ids):
                        # Whisper 的時間戳 token ID 範圍 (50362-50391，對應 0.0s-0.6s)
                        # 但實際上 Whisper 支持更長的時間範圍
                        if 50362 <= token_id <= 50461:  # 擴展到支持更長時間
                            # 計算實際時間
                            timestamp_seconds = (token_id - 50362) * 0.02  # 每個 token 代表 0.02 秒
                            
                            if current_start is None:
                                current_start = timestamp_seconds
                            
                            # 如果遇到新的時間戳，保存前一段
                            if current_text:
                                timestamps.append({
                                    'start': current_start,
                                    'end': timestamp_seconds,
                                    'text': ' '.join(current_text).strip(),
                                    'start_str': self._format_time(current_start),
                                    'end_str': self._format_time(timestamp_seconds)
                                })
                                current_text = []
                            
                            current_start = timestamp_seconds
                        else:
                            # 普通文本 token，解碼為文字
                            if token_id not in [50258, 50259, 50359, 50363]:  # 跳過特殊 token
                                token_text = self.tokenizer.decode([token_id])
                                if token_text.strip():
                                    current_text.append(token_text)
                    
                    # 處理最後一段
                    if current_text and current_start is not None:
                        # 估算結束時間（基於音頻長度）
                        audio_duration = len(token_ids) * 0.02  # 假設每個 token 代表 0.02 秒
                        timestamps.append({
                            'start': current_start,
                            'end': audio_duration,
                            'text': ' '.join(current_text).strip(),
                            'start_str': self._format_time(current_start),
                            'end_str': self._format_time(audio_duration)
                        })
            
            return timestamps
            
        except Exception as e:
            logger.error(f"時間戳提取失敗: {e}")
            return []
    
    def _format_time(self, seconds: float) -> str:
        """格式化時間為 MM:SS 格式"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def _format_text_with_timestamps(self, text: str, timestamps: List[Dict[str, Any]]) -> str:
        """格式化帶時間戳的文本"""
        if not timestamps:
            return text
        
        formatted_lines = []
        for ts in timestamps:
            if ts['text'].strip():
                formatted_lines.append(f"[{ts['start_str']}-{ts['end_str']}] {ts['text']}")
        
        return "\n".join(formatted_lines)


def create_ctranslate2_whisper(model_size: str = "base", device: str = "auto") -> WhisperCTranslate2:
    """創建 CTranslate2 Whisper 實例的工廠函數"""
    return WhisperCTranslate2(model_size=model_size, device=device)


def convert_huggingface_to_ctranslate2(model_id: str, output_dir: str, 
                                      quantization: str = "int8") -> bool:
    """
    將 Hugging Face 模型轉換為 CTranslate2 格式
    
    Args:
        model_id: Hugging Face 模型 ID
        output_dir: 輸出目錄
        quantization: 量化類型 (int8, int16, float16)
        
    Returns:
        轉換是否成功
    """
    try:
        logger.info(f"開始轉換模型 {model_id} 到 CTranslate2 格式...")
        
        # 創建輸出目錄
        os.makedirs(output_dir, exist_ok=True)
        
        # 執行轉換
        ctranslate2.converters.TransformersConverter(
            model_id,
            output_dir=output_dir,
            quantization=quantization,
            force=True
        ).convert()
        
        logger.info(f"✅ 模型轉換成功，保存在: {output_dir}")
        return True
        
    except Exception as e:
        logger.error(f"模型轉換失敗: {str(e)}")
        return False

