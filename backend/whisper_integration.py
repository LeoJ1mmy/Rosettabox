"""
Whisper 整合模組
提供標準 Transformers Whisper 和 CTranslate2 優化版本的選擇
強制使用 GPU 模式以獲得最佳效能
"""

import os
import sys
import time
import logging
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
import torch

# 🔧 Fix cuDNN library path for ctranslate2
# Add cuDNN libraries from venv to LD_LIBRARY_PATH - MUST be done before importing ctranslate2
if torch.cuda.is_available():
    try:
        import site
        import ctypes
        site_packages = site.getsitepackages()[0] if site.getsitepackages() else None
        if not site_packages:
            # Fallback for venv
            site_packages = os.path.join(sys.prefix, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')

        # Add ctranslate2.libs path first (it has its own cuDNN)
        ct2_libs_path = os.path.join(site_packages, 'ctranslate2.libs')
        cudnn_lib_path = os.path.join(site_packages, 'nvidia', 'cudnn', 'lib')
        
        current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        paths_to_add = []
        
        if os.path.exists(ct2_libs_path) and ct2_libs_path not in current_ld_path:
            paths_to_add.append(ct2_libs_path)
        
        if os.path.exists(cudnn_lib_path) and cudnn_lib_path not in current_ld_path:
            paths_to_add.append(cudnn_lib_path)
        
        if paths_to_add:
            new_ld_path = ':'.join(paths_to_add)
            if current_ld_path:
                os.environ['LD_LIBRARY_PATH'] = f"{new_ld_path}:{current_ld_path}"
            else:
                os.environ['LD_LIBRARY_PATH'] = new_ld_path
            
            # Preload cuDNN libraries in correct dependency order
            # Must load base libraries before dependent ones
            cudnn_libs_to_load = [
                # Base cuDNN library (from nvidia/cudnn/lib)
                (cudnn_lib_path, 'libcudnn.so.9'),
                # cuDNN ops and other dependencies
                (cudnn_lib_path, 'libcudnn_ops.so.9'),
                (cudnn_lib_path, 'libcudnn_cnn.so.9'),
                (cudnn_lib_path, 'libcudnn_adv.so.9'),
            ]

            loaded_count = 0
            for lib_dir, lib_name in cudnn_libs_to_load:
                lib_path = os.path.join(lib_dir, lib_name)
                if os.path.exists(lib_path):
                    try:
                        ctypes.CDLL(lib_path, mode=ctypes.RTLD_GLOBAL)
                        loaded_count += 1
                    except Exception as e:
                        print(f"⚠️ 無法載入 {lib_name}: {e}")

            if loaded_count > 0:
                print(f"✅ 成功預載入 {loaded_count} 個 cuDNN 庫")
    except Exception as e:
        print(f"⚠️ cuDNN 庫路徑設置失敗: {e}")
        pass  # Silent fail, will fall back to CPU if needed

logger = logging.getLogger(__name__)

# ============================================================================
# 🚫 Whisper 幻覺過濾
# ============================================================================

# 已知的 Whisper 幻覺短語（來自 YouTube 字幕訓練數據）
_KNOWN_HALLUCINATION_PHRASES = [
    "字幕志願者",
    "李宗盛",
    "中文字幕",
    "字幕由",
    "字幕提供",
    "字幕製作",
    "字幕校對",
    "感謝觀看",
    "謝謝觀看",
    "訂閱頻道",
    "請訂閱",
    "按讚訂閱",
    "小鈴鐺",
    "Amara.org",
    "Subtitles by",
    "Subscribe",
]

import re as _re

# 預編譯幻覺 pattern
_HALLUCINATION_PATTERN = _re.compile(
    '|'.join(_re.escape(p) for p in _KNOWN_HALLUCINATION_PHRASES),
    _re.IGNORECASE
)


def _is_hallucinated_segment(text: str) -> bool:
    """判斷一個 Whisper segment 是否為幻覺文字

    判斷標準：
    1. 文字過短（單字或空白）且無實質內容
    2. 包含已知幻覺短語
    3. 高重複率（同一字元佔比過高）
    """
    if not text or len(text.strip()) == 0:
        return True

    cleaned = text.strip()

    # 已知幻覺短語偵測
    if _HALLUCINATION_PATTERN.search(cleaned):
        return True

    # 高重複率偵測：如果去重後的字元種類太少，代表是重複幻覺
    # 例如「中中中中中」或「者者者者」
    if len(cleaned) >= 4:
        unique_chars = set(cleaned.replace(' ', ''))
        if len(unique_chars) <= 2:
            return True

    return False


def normalize_language_code(language: str) -> str:
    """標準化語言代碼，將 'chinese' 轉換為 'zh'"""
    language_mapping = {
        'chinese': 'zh',
        'chinese_traditional': 'zh',
        'chinese_simplified': 'zh',
        'mandarin': 'zh',
        'cantonese': 'yue',
        'english': 'en',
        'japanese': 'ja',
        'korean': 'ko',
        'spanish': 'es',
        'french': 'fr',
        'german': 'de',
        'italian': 'it',
        'portuguese': 'pt',
        'russian': 'ru',
        'arabic': 'ar',
        'hindi': 'hi',
        'thai': 'th',
        'vietnamese': 'vi',
        'indonesian': 'id',
        'malay': 'ms',
        'turkish': 'tr',
        'polish': 'pl',
        'dutch': 'nl',
        'swedish': 'sv',
        'norwegian': 'no',
        'danish': 'da',
        'finnish': 'fi',
        'greek': 'el',
        'hebrew': 'he',
        'ukrainian': 'uk',
        'czech': 'cs',
        'hungarian': 'hu',
        'romanian': 'ro',
        'bulgarian': 'bg',
        'croatian': 'hr',
        'serbian': 'sr',
        'slovak': 'sk',
        'slovenian': 'sl',
        'estonian': 'et',
        'latvian': 'lv',
        'lithuanian': 'lt',
        'maltese': 'mt',
        'irish': 'ga',
        'welsh': 'cy',
        'basque': 'eu',
        'catalan': 'ca',
        'galician': 'gl',
        'afrikaans': 'af',
        'albanian': 'sq',
        'amharic': 'am',
        'azerbaijani': 'az',
        'bengali': 'bn',
        'bosnian': 'bs',
        'burmese': 'my',
        'dari': 'fa',
        'filipino': 'tl',
        'georgian': 'ka',
        'gujarati': 'gu',
        'hausa': 'ha',
        'hawaiian': 'haw',
        'icelandic': 'is',
        'igbo': 'ig',
        'javanese': 'jw',
        'kannada': 'kn',
        'kazakh': 'kk',
        'khmer': 'km',
        'lao': 'lo',
        'latvian': 'lv',
        'macedonian': 'mk',
        'malagasy': 'mg',
        'malayalam': 'ml',
        'maori': 'mi',
        'marathi': 'mr',
        'mongolian': 'mn',
        'nepali': 'ne',
        'odia': 'or',
        'pashto': 'ps',
        'persian': 'fa',
        'punjabi': 'pa',
        'samoan': 'sm',
        'scottish_gaelic': 'gd',
        'shona': 'sn',
        'sindhi': 'sd',
        'sinhala': 'si',
        'somali': 'so',
        'sundanese': 'su',
        'swahili': 'sw',
        'tajik': 'tg',
        'tamil': 'ta',
        'telugu': 'te',
        'tigrinya': 'ti',
        'turkmen': 'tk',
        'urdu': 'ur',
        'uzbek': 'uz',
        'yiddish': 'yi',
        'yoruba': 'yo',
        'zulu': 'zu'
    }
    
    # 如果已經是標準代碼，直接返回
    if language in language_mapping.values():
        return language
    
    # 轉換為小寫並查找映射
    normalized = language.lower().replace('_', ' ').replace('-', ' ')
    for key, value in language_mapping.items():
        if normalized == key.replace('_', ' '):
            return value
    
    # 如果找不到映射，返回原始值（讓 faster-whisper 自己處理）
    return language

# 檢查 GPU 可用性，CPU 作為備用
def check_gpu_requirement():
    """檢查 GPU 要求，支持 CPU 備用，優化 GB10 Grace Blackwell 支援"""
    # Check if WHISPER_DEVICE is explicitly set in environment
    whisper_device_override = os.getenv('WHISPER_DEVICE', '').lower()
    if whisper_device_override == 'cpu':
        logger.info("🔧 WHISPER_DEVICE=cpu 已設置，強制使用 CPU 模式")
        return "cpu"
    elif whisper_device_override in ('gpu', 'cuda'):
        logger.info("🔧 WHISPER_DEVICE=cuda 已設置，強制使用 GPU 模式")
        # For GB10/Blackwell, force GPU mode even if torch.cuda.is_available() has issues
        try:
            # Try to initialize CUDA
            if not torch.cuda.is_available():
                # Try reinitializing CUDA for GB10
                torch.cuda.init()

            gpu_count = torch.cuda.device_count()
            if gpu_count > 0:
                torch.cuda.set_device(0)
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"✅ GPU 強制模式成功: {gpu_name}")
                return "gpu"
        except Exception as e:
            logger.warning(f"⚠️ GPU 強制模式失敗: {e}")
        # Continue to normal detection below

    if torch.cuda.is_available():
        try:
            gpu_count = torch.cuda.device_count()

            # GB10 只有一個 GPU，直接使用 GPU 0
            # 對於多 GPU 系統，為 Whisper 設定使用 GPU 1，避免與 vLLM (GPU 0) 衝突
            whisper_gpu = 0 if gpu_count == 1 else (1 if gpu_count > 1 else 0)
            torch.cuda.set_device(whisper_gpu)

            current_gpu = torch.cuda.current_device()
            gpu_name = torch.cuda.get_device_name(current_gpu)

            # GB10 使用統一記憶體，記憶體報告可能不準確
            try:
                gpu_memory = torch.cuda.get_device_properties(current_gpu).total_memory / 1024**3
            except:
                gpu_memory = 128.0  # GB10 預設 128GB 統一記憶體

            logger.info(f"✅ GPU 檢測成功:")
            logger.info(f"   GPU 數量: {gpu_count}")
            logger.info(f"   當前 GPU: {current_gpu}")
            logger.info(f"   GPU 名稱: {gpu_name}")
            logger.info(f"   GPU 記憶體: {gpu_memory:.1f} GB")

            # 檢測 GB10 Blackwell 架構
            if 'GB10' in gpu_name or 'Blackwell' in gpu_name.lower():
                logger.info(f"   🚀 檢測到 GB10 Grace Blackwell 架構")
                logger.info(f"   🚀 統一記憶體架構: 128GB 共享")

            return "gpu"
        except Exception as e:
            logger.warning(f"⚠️ GPU 檢測失敗: {e}")
            logger.info("🔄 切換到 CPU 模式...")
            return "cpu"
    else:
        logger.info("⚠️ GPU 不可用，使用 CPU 模式")
        return "cpu"

# 嘗試導入 faster-whisper 版本
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
    logger.info("✅ faster-whisper 可用")
except ImportError as e:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning(f"faster-whisper 不可用: {e}")

# 嘗試導入 CTranslate2 版本
try:
    from whisper_ctranslate2 import WhisperCTranslate2, create_ctranslate2_whisper
    CT2_AVAILABLE = True
    logger.info("✅ CTranslate2 可用")
except ImportError as e:
    CT2_AVAILABLE = False
    logger.warning(f"CTranslate2 不可用: {e}")

# 標準 Transformers 版本
try:
    from transformers import WhisperProcessor, WhisperForConditionalGeneration
    TRANSFORMERS_AVAILABLE = True
    logger.info("✅ Transformers Whisper 可用")
except ImportError as e:
    TRANSFORMERS_AVAILABLE = False
    logger.warning(f"Transformers Whisper 不可用: {e}")


class WhisperManager:
    """Whisper 模型管理器，支持多種後端，GPU 優先 CPU 備用"""
    
    def __init__(self, backend: str = "auto", model_size: str = "base"):
        """
        初始化 Whisper 管理器
        
        Args:
            backend: 後端類型 (auto, faster_whisper, ctranslate2, transformers)
            model_size: 模型大小或 Hugging Face 模型名稱
        """
        # 檢查 GPU 要求，CPU 作為備用
        self.device_type = check_gpu_requirement()
        
        self.backend = backend
        self.model_size = model_size
        self.current_backend = None
        self.model = None
        self.processor = None
        self.tokenizer = None
        self.is_loaded = False
        
        # 自動選擇最佳後端
        if backend == "auto":
            if FASTER_WHISPER_AVAILABLE:
                self.backend = "faster_whisper"
                logger.info("自動選擇 faster-whisper 後端")
            elif CT2_AVAILABLE:
                self.backend = "ctranslate2"
                logger.info("自動選擇 CTranslate2 後端")
            elif TRANSFORMERS_AVAILABLE:
                self.backend = "transformers"
                logger.info("自動選擇 Transformers 後端")
            else:
                raise RuntimeError("沒有可用的 Whisper 後端")
        
        logger.info(f"使用 Whisper 後端: {self.backend}")

    def _build_initial_prompt(self) -> str:
        """
        構建包含熱詞的 initial_prompt
        從 hot_words.json 讀取高優先級術語，注入到 Whisper 的提示詞中
        """
        base_prompt = "以下是台灣繁體中文的語音轉錄，使用台灣慣用詞彙（如：軟體、資料庫、網路、伺服器）。"

        try:
            import json
            import os

            # 獲取熱詞配置文件路徑
            config_dir = os.path.join(os.path.dirname(__file__), 'config')
            hot_words_path = os.path.join(config_dir, 'hot_words.json')

            if not os.path.exists(hot_words_path):
                logger.debug(f"熱詞配置文件不存在: {hot_words_path}")
                return base_prompt

            with open(hot_words_path, 'r', encoding='utf-8') as f:
                hot_words_config = json.load(f)

            # 檢查是否啟用 Whisper prompt 注入
            global_settings = hot_words_config.get('global_settings', {})
            if not global_settings.get('use_in_whisper_prompt', False):
                logger.debug("熱詞 Whisper prompt 注入未啟用")
                return base_prompt

            # 收集高優先級術語 (highest 和 high)
            terms = []
            categories = hot_words_config.get('categories', {})

            for cat_name, category in categories.items():
                if not category.get('enabled', False):
                    continue

                priority = category.get('priority', 'medium')
                if priority not in ['highest', 'high']:
                    continue

                for term in category.get('terms', []):
                    word = term.get('word', '')
                    if word:
                        terms.append(word)
                    # 也添加別名
                    aliases = term.get('aliases', [])
                    for alias in aliases:
                        if alias and alias not in terms:
                            terms.append(alias)

            # 限制術語數量，避免 prompt 過長 (最多 50 個)
            max_terms = global_settings.get('max_words_per_request', 50)
            terms = list(dict.fromkeys(terms))[:max_terms]  # 去重並限制數量

            if terms:
                terms_str = '、'.join(terms)
                prompt = f"{base_prompt} 重要術語：{terms_str}。"
                logger.info(f"🔑 熱詞注入 initial_prompt: {len(terms)} 個術語")
                return prompt

        except Exception as e:
            logger.warning(f"載入熱詞失敗: {e}")

        return base_prompt

    def _get_adaptive_beam_size(self, audio: np.ndarray, sampling_rate: int) -> int:
        """
        根據音頻前 5 秒的識別信心度自適應調整 beam_size

        策略:
        - 高品質音頻 (高信心度): 使用較小 beam_size，加快處理速度
        - 低品質/有噪音音頻: 使用較大 beam_size，提高準確性
        """
        try:
            from config import config

            # 檢查是否啟用自適應 beam_size
            if not getattr(config, 'WHISPER_ADAPTIVE_BEAM', True):
                return getattr(config, 'WHISPER_BEAM_SIZE', 5)

            beam_min = getattr(config, 'WHISPER_BEAM_SIZE_MIN', 3)
            beam_max = getattr(config, 'WHISPER_BEAM_SIZE_MAX', 10)
            beam_default = getattr(config, 'WHISPER_BEAM_SIZE', 5)

            # 確保模型已載入
            if not self.model:
                logger.warning("模型未載入，使用默認 beam_size")
                return beam_default

            # 取前 5 秒音頻做快速測試
            test_duration = min(5, len(audio) / sampling_rate)
            if test_duration < 1:
                # 音頻太短，使用默認值
                return beam_default

            test_samples = int(test_duration * sampling_rate)
            test_audio = audio[:test_samples]

            # 用最小 beam_size 快速識別測試片段
            logger.debug(f"🔍 自適應 beam_size: 分析前 {test_duration:.1f} 秒音頻...")

            segments, _ = self.model.transcribe(
                test_audio,
                language="zh",
                beam_size=1,  # 最快速度
                temperature=0.0,
                vad_filter=True
            )

            # 計算平均置信度
            segments_list = list(segments)
            if not segments_list:
                logger.debug("測試片段無語音，使用默認 beam_size")
                return beam_default

            avg_logprob = sum(s.avg_logprob for s in segments_list) / len(segments_list)
            avg_no_speech = sum(s.no_speech_prob for s in segments_list) / len(segments_list)

            # 根據置信度選擇 beam_size
            if avg_logprob > -0.3 and avg_no_speech < 0.3:
                beam_size = beam_min  # 高品質音頻，快速處理
                quality = "高品質"
            elif avg_logprob > -0.6 and avg_no_speech < 0.5:
                beam_size = beam_default  # 中等品質，平衡
                quality = "中等品質"
            else:
                beam_size = beam_max  # 低品質/噪音，深搜索
                quality = "低品質/有噪音"

            logger.info(f"🎯 自適應 beam_size: {quality} 音頻 (avg_logprob={avg_logprob:.2f}, no_speech={avg_no_speech:.2f}) → beam_size={beam_size}")
            return beam_size

        except Exception as e:
            logger.warning(f"自適應 beam_size 檢測失敗: {e}，使用默認值")
            try:
                from config import config
                return getattr(config, 'WHISPER_BEAM_SIZE', 5)
            except:
                return 5

    def _cleanup_gpu_memory(self):
        """清理 GPU 記憶體（CPU 模式下只清理 Python 記憶體）"""
        import gc
        try:
            # 清理 Python 垃圾回收
            gc.collect()
            
            # 只在 GPU 模式下清理 GPU 記憶體
            if self.device_type == "gpu" and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                
                # 記錄當前記憶體使用狀況
                allocated = torch.cuda.memory_allocated() / 1024**3
                reserved = torch.cuda.memory_reserved() / 1024**3
                logger.info(f"GPU 記憶體清理後: 已分配 {allocated:.2f} GB, 已預留 {reserved:.2f} GB")
            elif self.device_type == "cpu":
                logger.info("CPU 模式記憶體清理完成")
                
        except Exception as e:
            logger.warning(f"記憶體清理失敗: {e}")
        
        # 清理 CTranslate2 模型記憶體（僅在 GPU 模式下）
        try:
            if self.device_type == "gpu" and hasattr(self, 'model') and self.model is not None:
                if hasattr(self.model, 'model') and hasattr(self.model.model, 'unload_model'):
                    self.model.model.unload_model()
                    logger.info("CTranslate2 模型已從 GPU 卸載")
        except Exception as e:
            logger.warning(f"CTranslate2 模型卸載失敗: {e}")
    
    def _unload_ollama_models(self):
        """卸載 Ollama 模型以釋放 GPU 記憶體"""
        try:
            import requests
            from config import config
            
            logger.info("🧹 卸載 Ollama 模型以釋放 GPU 記憶體...")
            response = requests.get(f"{config.OLLAMA_URL}/api/ps", timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                for model in models:
                    model_name = model.get('name', '')
                    if model_name:
                        # 設置 keep_alive=0 來卸載模型
                        requests.post(
                            f"{config.OLLAMA_URL}/api/generate",
                            json={"model": model_name, "keep_alive": 0},
                            timeout=10
                        )
                        logger.info(f"✅ 已卸載 Ollama 模型: {model_name}")
            else:
                logger.warning(f"無法獲取 Ollama 模型狀態: {response.status_code}")
        except Exception as e:
            logger.warning(f"卸載 Ollama 模型失敗: {e}")
    
    def _get_available_gpu_memory(self) -> float:
        """獲取可用 GPU 記憶體（GB），CPU 模式返回無限制"""
        try:
            if self.device_type == "cpu":
                logger.info("CPU 模式: 記憶體無限制")
                return float('inf')  # CPU 模式返回無限制
                
            if not torch.cuda.is_available():
                return 0.0

            # 獲取總記憶體和已使用記憶體
            device_id = torch.cuda.current_device()
            total_memory = torch.cuda.get_device_properties(device_id).total_memory / 1024**3
            allocated_memory = torch.cuda.memory_allocated(device_id) / 1024**3
            
            # 計算可用記憶體（保守估計，保留 1GB 緩衝）
            available_memory = total_memory - allocated_memory - 1.0
            
            logger.info(f"GPU 記憶體狀態: 總計 {total_memory:.2f} GB, 已用 {allocated_memory:.2f} GB, 可用 {available_memory:.2f} GB")
            
            return max(0.0, available_memory)
            
        except Exception as e:
            logger.warning(f"獲取 GPU 記憶體資訊失敗: {e}")
            return 0.0
    
    def load_model(self) -> bool:
        """載入 Whisper 模型（固定使用指定模型，不做 fallback）"""
        # 載入模型前先清理記憶體
        self._cleanup_gpu_memory()

        # 卸載 Ollama 模型以釋放記憶體
        self._unload_ollama_models()

        model_name = self.model_size
        logger.info(f"📦 載入 Whisper 模型: {model_name}")

        try:
            if self.backend == "faster_whisper":
                if not FASTER_WHISPER_AVAILABLE:
                    raise RuntimeError("faster-whisper 後端不可用")

                success = self._load_faster_whisper_model(model_name)
                if success:
                    self.current_backend = "faster_whisper"
                    self.is_loaded = True
                    logger.info(f"✅ 成功載入 Whisper {model_name} 模型 (faster-whisper)")
                    return True

            elif self.backend == "ctranslate2":
                if not CT2_AVAILABLE:
                    raise RuntimeError("CTranslate2 後端不可用")

                device = "cuda" if self.device_type == "gpu" else "cpu"
                self.model = create_ctranslate2_whisper(model_name, device=device)
                success = self.model.load_model()
                if success:
                    self.processor = self.model.processor
                    self.tokenizer = self.model.tokenizer
                    self.current_backend = "ctranslate2"
                    self.is_loaded = True
                    logger.info(f"✅ 成功載入 Whisper {model_name} 模型 (CTranslate2)")
                    return True

            elif self.backend == "transformers":
                if not TRANSFORMERS_AVAILABLE:
                    raise RuntimeError("Transformers 後端不可用")

                success = self._load_transformers_model(model_name)
                if success:
                    self.current_backend = "transformers"
                    self.is_loaded = True
                    logger.info(f"✅ 成功載入 Whisper {model_name} 模型 (官方 Whisper)")
                    return True
            else:
                raise ValueError(f"不支持的後端: {self.backend}")

        except Exception as e:
            logger.error(f"❌ 載入 Whisper {model_name} 模型失敗: {str(e)}")
            return False

        logger.error(f"❌ 載入 Whisper {model_name} 模型失敗")
        return False
    
    def _load_faster_whisper_model(self, model_size: str = None) -> bool:
        """載入 faster-whisper 模型"""
        try:
            logger.info(f"正在載入 faster-whisper 模型: {model_size or self.model_size}")
            
            # 載入前先清理 GPU 記憶體
            self._cleanup_gpu_memory()
            
            # 使用 faster-whisper 載入模型
            # 支持 Hugging Face 模型名稱和標準模型大小
            model_name = model_size or self.model_size
            
            # 檢查可用 GPU 記憶體並選擇最佳配置
            available_memory = self._get_available_gpu_memory()
            logger.info(f"可用 GPU 記憶體: {available_memory:.2f} GB")
            
            # 根據可用記憶體選擇計算類型
            if available_memory < 2.0:
                compute_type = "int8"  # 最節省記憶體
                logger.info("記憶體不足，使用 int8 量化")
            elif available_memory < 4.0:
                compute_type = "int16"  # 中等記憶體使用
                logger.info("記憶體有限，使用 int16 量化")
            else:
                compute_type = "float16"  # 標準配置
                logger.info("記憶體充足，使用 float16")
            
            # 根據設備類型選擇配置
            if self.device_type == "gpu":
                device = "cuda"
                logger.info(f"使用 GPU 配置: {compute_type}")
                try:
                    self.model = WhisperModel(
                        model_name,
                        device=device,
                        compute_type=compute_type,
                        num_workers=1,  # 使用單個工作線程
                        cpu_threads=0,  # 讓 CTranslate2 自動選擇 CPU 線程數
                        device_index=torch.cuda.current_device()  # 使用當前設定的 GPU
                    )
                except Exception as gpu_error:
                    # Check if it's a cuDNN library error
                    error_str = str(gpu_error)
                    if "cudnn" in error_str.lower() or "libcudnn" in error_str.lower():
                        logger.warning(f"⚠️ GPU 載入失敗 (cuDNN library issue): {error_str}")
                        logger.warning("🔄 自動切換到 CPU 模式作為備用...")
                        # Fall back to CPU
                        device = "cpu"
                        compute_type = "int8"
                        self.device_type = "cpu"  # Update device type
                        self.model = WhisperModel(
                            model_name,
                            device=device,
                            compute_type=compute_type,
                            num_workers=1,
                            cpu_threads=0
                        )
                        logger.info("✅ 已切換到 CPU 模式")
                    else:
                        # Re-raise if it's a different error
                        raise
            else:
                device = "cpu"
                compute_type = "int8"  # CPU 使用 int8 以提高速度
                logger.info("使用 CPU 配置: int8")
                self.model = WhisperModel(
                    model_name,
                    device=device,
                    compute_type=compute_type,
                    num_workers=1,  # 使用單個工作線程
                    cpu_threads=0   # 讓 CTranslate2 自動選擇 CPU 線程數
                    # CPU 模式不需要 device_index 參數
                )
            
            self.processor = None  # faster-whisper 不需要 processor
            self.tokenizer = None  # faster-whisper 不需要 tokenizer
            self.current_backend = "faster_whisper"  # 設置當前後端
            self.is_loaded = True  # 設置載入狀態
            
            logger.info(f"✅ faster-whisper 模型載入成功: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"載入 faster-whisper 模型失敗: {str(e)}")
            return False
    
    def _load_transformers_model(self, model_size: str = None) -> bool:
        """載入官方 Whisper 模型作為後端"""
        try:
            import whisper
            
            logger.info(f"正在載入官方 Whisper 模型: {model_size or self.model_size}")
            
            # 使用官方 Whisper 庫
            self.model = whisper.load_model(model_size or self.model_size)
            self.processor = None  # 官方庫不需要 processor
            self.tokenizer = None  # 官方庫不需要 tokenizer
            
            logger.info(f"✅ 官方 Whisper 模型載入成功")
            return True
            
        except Exception as e:
            logger.error(f"載入官方 Whisper 模型失敗: {str(e)}")
            return False
    
    def transcribe(self, audio: np.ndarray, sampling_rate: int = 16000, 
                   language: str = "zh", task: str = "transcribe",
                   **kwargs) -> Dict[str, Any]:
        """轉錄音頻，支持時間戳"""
        if not self.is_loaded:
            raise RuntimeError("模型未載入，請先調用 load_model()")
        
        if self.current_backend == "faster_whisper":
            return self._transcribe_faster_whisper(audio, sampling_rate, language, task, **kwargs)
        elif self.current_backend == "ctranslate2":
            return self.model.transcribe(audio, sampling_rate, language, task, **kwargs)
        elif self.current_backend == "transformers":
            return self._transcribe_official_whisper(audio, sampling_rate, language, task, **kwargs)
        else:
            raise RuntimeError("後端未正確初始化")
    
    def _transcribe_faster_whisper(self, audio: np.ndarray, sampling_rate: int = 16000,
                                  language: str = "zh", task: str = "transcribe",
                                  **kwargs) -> Dict[str, Any]:
        """使用 faster-whisper 進行轉錄 - 簡化版本"""
        try:
            import time
            start_time = time.time()

            # 標準化語言代碼
            normalized_language = normalize_language_code(language)

            # 🔧 VAD (語音活動檢測) 參數 - 根據 overlap mode 選擇
            from config import config as app_config
            overlap_mode = getattr(app_config, 'WHISPER_OVERLAP_MODE', False)

            if overlap_mode:
                # 🔧 重疊語音優化模式：放寬參數，保留多人同時說話的段落
                vad_parameters = {
                    "threshold": 0.35,              # 更敏感偵測重疊語音（原 0.5）
                    "min_speech_duration_ms": 100,   # 允許短插話如「對」「嗯」（原 250）
                    "min_silence_duration_ms": 100,  # 不變
                    "speech_pad_ms": 150             # 更多邊界填充，覆蓋重疊邊緣（原 30）
                }
                transcribe_filter_params = {
                    "compression_ratio_threshold": 2.4,    # 放寬：重疊語音壓縮比較高（原 1.8）
                    "log_prob_threshold": -1.0,            # 回復預設：容忍低信心度（原 -0.8）
                    "no_speech_threshold": 0.6,            # 回復預設：不過度過濾（原 0.5）
                    "hallucination_silence_threshold": 2.0 # 回復預設：不跳過短靜音（原 1.0）
                }
                logger.info("🔊 Whisper Overlap Mode: ON - 使用放寬參數保留重疊語音")
            else:
                # 原始嚴格模式：防重複/防幻覺優先
                vad_parameters = {
                    "threshold": 0.5,
                    "min_speech_duration_ms": 250,
                    "min_silence_duration_ms": 100,
                    "speech_pad_ms": 30
                }
                transcribe_filter_params = {
                    "compression_ratio_threshold": 1.8,
                    "log_prob_threshold": -0.8,
                    "no_speech_threshold": 0.5,
                    "hallucination_silence_threshold": 1.0
                }

            # 使用 faster-whisper 進行轉錄 - 強化防重複參數
            # 🔧 自適應 beam_size: 根據音頻品質動態調整
            beam_size = self._get_adaptive_beam_size(audio, sampling_rate)

            # 🔧 構建包含熱詞的 initial_prompt
            initial_prompt = self._build_initial_prompt()

            segments, info = self.model.transcribe(
                audio,
                language=normalized_language,
                beam_size=beam_size,
                best_of=beam_size,
                temperature=0.0,
                initial_prompt=initial_prompt,  # 🔧 包含熱詞的風格引導提示詞
                condition_on_previous_text=False,   # 🔧 關閉：防止基於前文產生循環重複
                word_timestamps=True,               # 🔧 開啟：讓 hallucination_silence_threshold 生效
                vad_filter=True,                    # 🔧 啟用 VAD 過濾
                vad_parameters=vad_parameters,      # 🔧 VAD 參數
                # 🔧 強化防重複參數
                no_repeat_ngram_size=5,             # 🔧 提高：禁止 5-gram 重複（原 3）
                repetition_penalty=1.5,             # 🔧 提高：更強的重複懲罰（原 1.2）
                compression_ratio_threshold=transcribe_filter_params["compression_ratio_threshold"],
                log_prob_threshold=transcribe_filter_params["log_prob_threshold"],
                no_speech_threshold=transcribe_filter_params["no_speech_threshold"],
                hallucination_silence_threshold=transcribe_filter_params["hallucination_silence_threshold"]
            )

            inference_time = time.time() - start_time

            # 收集所有段落文本（含 segment 級幻覺過濾）
            text_parts = []
            timestamps = []
            hallucination_filtered = 0

            for segment in segments:
                seg_text = segment.text.strip()

                # 🔧 Segment 級幻覺過濾
                if _is_hallucinated_segment(seg_text):
                    hallucination_filtered += 1
                    logger.debug(f"🚫 過濾幻覺片段 [{segment.start:.1f}-{segment.end:.1f}]: {seg_text[:50]}")
                    continue

                # 🔧 清除 Whisper 停頓標記 "..."（模型對語音停頓產生的省略號）
                seg_text = re.sub(r'\.{2,}', '', seg_text)   # 連續兩個以上的點
                seg_text = re.sub(r'…+', '', seg_text)        # Unicode 省略號
                seg_text = seg_text.strip()
                if not seg_text:
                    continue

                # 🔧 計算置信度分數 (0-1)
                # avg_logprob 通常在 -1.0 ~ 0 之間，轉換為 0-1
                avg_logprob = getattr(segment, 'avg_logprob', -0.5)
                no_speech_prob = getattr(segment, 'no_speech_prob', 0.0)
                log_prob_score = min(1.0, max(0.0, (avg_logprob + 1.0)))
                speech_score = 1.0 - no_speech_prob
                # 綜合置信度：70% 對數概率 + 30% 語音概率
                confidence = (log_prob_score * 0.7 + speech_score * 0.3)

                text_parts.append(seg_text)
                timestamps.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": seg_text,
                    "confidence": round(confidence, 3),
                    "avg_logprob": round(avg_logprob, 3),
                    "no_speech_prob": round(no_speech_prob, 3)
                })

            if hallucination_filtered > 0:
                logger.warning(f"🚫 已過濾 {hallucination_filtered} 個幻覺片段")

            full_text = " ".join(text_parts)

            # 計算整體平均置信度
            avg_confidence = 0.0
            low_confidence_count = 0
            if timestamps:
                confidence_values = [t.get('confidence', 0) for t in timestamps]
                avg_confidence = sum(confidence_values) / len(confidence_values)
                low_confidence_count = sum(1 for c in confidence_values if c < 0.5)

            # 構建結果
            response = {
                "text": full_text,
                "language": info.language if hasattr(info, 'language') else language,
                "task": task,
                "inference_time": inference_time,
                "model_size": self.model_size,
                "backend": "faster_whisper",
                "segments": timestamps,
                "duration": len(audio) / sampling_rate,
                "avg_confidence": round(avg_confidence, 3),
                "low_confidence_count": low_confidence_count
            }
            
            # 添加帶時間戳的文本
            if timestamps:
                response["text_with_timestamps"] = self._format_text_with_timestamps(full_text, timestamps)
                confidence_emoji = "🟢" if avg_confidence >= 0.8 else "🟡" if avg_confidence >= 0.5 else "🔴"
                logger.info(f"✅ faster-whisper 轉錄完成: {len(timestamps)} 個段落, 總長度 {response['duration']:.1f}秒, {confidence_emoji} 平均信心度 {avg_confidence:.1%}")
                if low_confidence_count > 0:
                    logger.warning(f"⚠️ {low_confidence_count} 個低信心段落需審核")
            else:
                logger.warning("⚠️ faster-whisper 未返回段落信息")
            
            return response
            
        except Exception as e:
            logger.error(f"faster-whisper 轉錄失敗: {str(e)}")
            return {"text": "", "error": str(e)}

    def _format_text_with_timestamps(self, text: str, timestamps: List[Dict]) -> str:
        """格式化帶時間戳的文本"""
        if not timestamps:
            return text
        
        formatted_parts = []
        for ts in timestamps:
            start_time = f"{int(ts['start']//60):02d}:{int(ts['start']%60):02d}"
            end_time = f"{int(ts['end']//60):02d}:{int(ts['end']%60):02d}"
            formatted_parts.append(f"[{start_time}-{end_time}] {ts['text']}")
        
        return "\n".join(formatted_parts)
    
    def _transcribe_official_whisper(self, audio: np.ndarray, sampling_rate: int = 16000,
                                   language: str = "zh", task: str = "transcribe",
                                   **kwargs) -> Dict[str, Any]:
        """使用官方 Whisper 庫進行轉錄 - 支持完整音頻長度"""
        try:
            import whisper
            import time

            # 過濾掉 whisper.transcribe 不支援的參數
            kwargs.pop('progress_callback', None)
            kwargs.pop('estimated_speakers', None)

            start_time = time.time()

            # 🔧 修復：不截斷音頻，使用完整音頻進行轉錄
            # 移除 pad_or_trim，讓 Whisper 處理完整音頻
            audio_whisper = audio  # 使用完整音頻

            # 轉錄完整音頻
            result = self.model.transcribe(
                audio_whisper,
                language=language,
                task=task,
                initial_prompt="繁體中文，台灣，會議記錄，技術討論。",  # 🔧 風格引導（非指令）
                verbose=True,  # 啟用詳細模式以獲取更多信息
                **kwargs
            )
            
            inference_time = time.time() - start_time
            
            # 構建結果，包含更詳細的信息
            response = {
                "text": result["text"],
                "language": result.get("language", language),
                "task": task,
                "inference_time": inference_time,
                "model_size": self.model_size,
                "backend": "official_whisper",
                "segments": result.get("segments", []),  # 包含時間戳段落
                "duration": len(audio) / sampling_rate   # 音頻總長度
            }
            
            # 如果有段落信息，添加詳細的時間戳
            if "segments" in result and result["segments"]:
                response["timestamps"] = [
                    {
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"]
                    }
                    for seg in result["segments"]
                ]
                logger.info(f"✅ 官方 Whisper 轉錄完成: {len(result['segments'])} 個段落, 總長度 {response['duration']:.1f}秒")
            else:
                logger.warning("⚠️ 官方 Whisper 未返回段落信息")
            
            return response
            
        except Exception as e:
            logger.error(f"官方 Whisper 推理失敗: {str(e)}")
            return {"text": "", "error": str(e)}
    
    def _transcribe_transformers(self, audio: np.ndarray, sampling_rate: int = 16000,
                                language: str = "zh", task: str = "transcribe",
                                **kwargs) -> Dict[str, Any]:
        """使用 Transformers 後端進行轉錄，支持時間戳"""
        try:
            start_time = time.time()
            
            # 準備音頻特徵
            inputs = self.processor(
                audio, 
                sampling_rate=sampling_rate, 
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=30 * sampling_rate
            )
            
            # 移動到 GPU
            device = self.model.device
            model_dtype = next(self.model.parameters()).dtype
            inputs = {k: v.to(device=device, dtype=model_dtype) for k, v in inputs.items()}
            
            with torch.no_grad():
                # 設置生成參數，啟用時間戳
                generate_kwargs = {
                    "max_length": 1024,  # 增加最大長度以支持更長的轉錄
                    "num_beams": 1,
                    "do_sample": False,
                    "early_stopping": False,  # 禁用早期停止以獲得完整轉錄
                    "use_cache": True,
                    "pad_token_id": self.processor.tokenizer.pad_token_id,
                    "eos_token_id": self.processor.tokenizer.eos_token_id,
                    # 移除 forced_decoder_ids 讓模型自動檢測語言
                    # "forced_decoder_ids": self.processor.get_decoder_prompt_ids(language=language, task=task),
                    "return_timestamps": True  # Transformers 支持時間戳
                }
                
                # 生成文本
                generated_ids = self.model.generate(
                    inputs["input_features"],
                    **generate_kwargs
                )
            
            # 解碼文本
            decoded_texts = self.processor.batch_decode(
                generated_ids, 
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True
            )
            
            text = decoded_texts[0] if decoded_texts else ""
            inference_time = time.time() - start_time
            
            # 構建結果
            result = {
                "text": text,
                "language": language,
                "task": task,
                "inference_time": inference_time,
                "model_size": self.model_size,
                "backend": "transformers"
            }
            
            # 嘗試提取時間戳
            try:
                timestamps = self._extract_timestamps_from_transformers(generated_ids[0], sampling_rate)
                if timestamps:
                    result["timestamps"] = timestamps
                    result["text_with_timestamps"] = self._format_text_with_timestamps(text, timestamps)
                    logger.info(f"✅ Transformers 成功提取時間戳: {len(timestamps)} 個片段")
                else:
                    logger.warning("⚠️ Transformers 無法提取時間戳")
            except Exception as e:
                logger.warning(f"Transformers 時間戳提取失敗: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Transformers 推理失敗: {str(e)}")
            return {"text": "", "error": str(e)}
    
    def transcribe_batch(self, audio_list: List[np.ndarray], 
                         sampling_rate: int = 16000, **kwargs) -> List[Dict[str, Any]]:
        """批量轉錄"""
        if not self.is_loaded:
            raise RuntimeError("模型未載入，請先調用 load_model()")
        
        if self.current_backend == "faster_whisper":
            # faster-whisper 的批量處理
            results = []
            for i, audio in enumerate(audio_list):
                logger.info(f"處理音頻 {i+1}/{len(audio_list)}")
                result = self._transcribe_faster_whisper(audio, sampling_rate, **kwargs)
                results.append(result)
            return results
        elif self.current_backend == "ctranslate2":
            return self.model.transcribe_batch(audio_list, sampling_rate, **kwargs)
        else:
            # Transformers 後端的批量處理
            results = []
            for i, audio in enumerate(audio_list):
                logger.info(f"處理音頻 {i+1}/{len(audio_list)}")
                result = self._transcribe_transformers(audio, sampling_rate, **kwargs)
                results.append(result)
            return results
    
    def get_model_info(self) -> Dict[str, Any]:
        """獲取模型信息"""
        if not self.is_loaded:
            return {"status": "未載入"}
        
        info = {
            "status": "已載入",
            "backend": self.current_backend,
            "model_size": self.model_size
        }
        
        if self.current_backend == "faster_whisper":
            info.update({
                "device": "cuda",
                "compute_type": "float16",
                "backend": "faster_whisper"
            })
        elif self.current_backend == "ctranslate2":
            info.update(self.model.get_model_info())
        elif self.current_backend == "transformers":
            info.update({
                "device": str(self.model.device),
                "dtype": str(next(self.model.parameters()).dtype),
                "backend": "transformers"
            })
        
        return info
    
    def switch_backend(self, new_backend: str) -> bool:
        """切換後端"""
        if new_backend == self.current_backend:
            logger.info(f"後端已經是 {new_backend}")
            return True
        
        if new_backend == "faster_whisper" and not FASTER_WHISPER_AVAILABLE:
            logger.error("faster-whisper 後端不可用")
            return False
        
        if new_backend == "ctranslate2" and not CT2_AVAILABLE:
            logger.error("CTranslate2 後端不可用")
            return False
        
        if new_backend == "transformers" and not TRANSFORMERS_AVAILABLE:
            logger.error("Transformers 後端不可用")
            return False
        
        # 清理當前模型
        self.cleanup()
        
        # 切換後端
        self.backend = new_backend
        logger.info(f"切換到 {new_backend} 後端")
        
        # 重新載入模型
        return self.load_model()
    
    def cleanup(self):
        """清理資源"""
        if self.current_backend == "faster_whisper" and self.model:
            # faster-whisper 模型清理
            try:
                del self.model
                self.model = None
            except Exception as e:
                logger.warning(f"faster-whisper 模型清理警告: {e}")
        elif self.current_backend == "ctranslate2" and self.model:
            self.model.cleanup()
        elif self.current_backend == "transformers" and self.model:
            # 移動模型到 CPU 然後刪除
            try:
                if hasattr(self.model, 'cpu'):
                    self.model.cpu()
                del self.model
                self.model = None
            except Exception as e:
                logger.warning(f"模型清理警告: {e}")
        
        if self.processor:
            del self.processor
            self.processor = None
        
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None
        
        self.current_backend = None
        self.is_loaded = False
        
        # 強制進行 GPU 記憶體清理
        try:
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                logger.info(f"GPU 記憶體已清理，當前使用: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")
        except Exception as e:
            logger.warning(f"GPU 記憶體清理警告: {e}")
        
        logger.info("Whisper 模型資源已清理")


def get_available_backends() -> List[str]:
    """獲取可用的後端列表"""
    backends = []
    if FASTER_WHISPER_AVAILABLE:
        backends.append("faster_whisper")
    if CT2_AVAILABLE:
        backends.append("ctranslate2")
    if TRANSFORMERS_AVAILABLE:
        backends.append("transformers")
    return backends


def create_whisper_manager(backend: str = "auto", model_size: str = "base") -> WhisperManager:
    """創建 Whisper 管理器的工廠函數"""
    return WhisperManager(backend, model_size)

