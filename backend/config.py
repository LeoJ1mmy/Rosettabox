import os
from dataclasses import dataclass
from typing import Optional, Union

# 載入 .env 文件
try:
    from dotenv import load_dotenv
    from pathlib import Path

    # 查找 .env 文件 - 先檢查項目根目錄（backend的父目錄）
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ .env 文件已載入: {env_path}")
    else:
        # 嘗試當前目錄
        load_dotenv()
        print("✅ .env 文件已載入（當前目錄）")
except ImportError:
    print("⚠️ python-dotenv 未安裝，請運行: pip install python-dotenv")
except Exception as e:
    print(f"⚠️ 載入 .env 文件失敗: {e}")

@dataclass
class AppConfig:
    """應用配置"""
    # 服務器配置
    HOST: str = "0.0.0.0"
    PORT: int = 3080
    DEBUG: bool = False
    
    # 文件上傳配置
    MAX_CONTENT_LENGTH: int = 3 * 1024 * 1024 * 1024  # 3GB
    UPLOAD_FOLDER: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    ALLOWED_EXTENSIONS: set = None

    # 活動日誌配置 - 使用絕對路徑確保無論從哪裡運行都能正確定位
    # 僅記錄 IP 操作日誌，不儲存敏感資料（音檔、摘要結果等）
    ACTIVITY_LOG_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "activity_logs")
    ACTIVITY_LOG_RETENTION_DAYS: int = 30  # 日誌保留天數
    
    # 網路模式配置
    NETWORK_MODE_ENABLED: bool = False
    
    # Email 配置
    EMAIL_ENABLED: bool = True  # 啟用 Email 功能
    EMAIL_SMTP_SERVER: str = "smtp.gmail.com"
    EMAIL_SMTP_PORT: int = 587
    EMAIL_USERNAME: str = ""
    EMAIL_PASSWORD: str = ""
    EMAIL_FROM_NAME: str = "語音處理系統"
    EMAIL_TO_ADDRESS: str = ""

    # 管理員配置
    ADMIN_PASSWORD: Optional[str] = None  # Hot Words 管理員密碼

    # 模型固定模式配置
    WHISPER_MODEL_FIXED: Optional[str] = None
    # AI 模型配置 (依引擎類型)
    OLLAMA_MODEL_FIXED: Optional[str] = None
    VLLM_MODEL_FIXED: Optional[str] = None
    
    # 快取配置
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 3600  # 1小時
    CACHE_MAX_SIZE: int = 100
    
    # 模型配置
    # DEFAULT_WHISPER_MODEL 從環境變數讀取，如未設定則使用 large-v3-turbo
    DEFAULT_WHISPER_MODEL: str = os.getenv('WHISPER_MODEL_FIXED', 'large-v3-turbo')
    DEFAULT_AI_MODEL: str = os.getenv('OLLAMA_MODEL_FIXED', 'gpt-oss:20b')
    OLLAMA_THINK_MODE: str = os.getenv('OLLAMA_THINK_MODE', 'off')  # off, low, medium, high
    OLLAMA_NUM_CTX: int = int(os.getenv('OLLAMA_NUM_CTX', '65536'))
    OLLAMA_NUM_PREDICT: int = int(os.getenv('OLLAMA_NUM_PREDICT', '16384'))
    MODEL_CACHE_SIZE: int = 3

    # 🔧 Refinement Agent 專用引擎和模型
    # 可以獨立於主 AI_ENGINE 使用不同的引擎
    # 例如：摘要用 Ollama (gpt-oss:120b)，refinement 用 vLLM (gemma-3-27b-it)
    REFINEMENT_ENGINE: str = os.getenv('REFINEMENT_ENGINE', 'vllm')  # ollama 或 vllm
    # Ollama 格式 (e.g., gemma3:27b)
    OLLAMA_REFINEMENT_MODEL: Optional[str] = os.getenv('OLLAMA_REFINEMENT_MODEL', 'gemma3:27b')
    # vLLM 格式 (e.g., google/gemma-3-27b-it)
    VLLM_REFINEMENT_MODEL: Optional[str] = os.getenv('VLLM_REFINEMENT_MODEL', 'google/gemma-3-27b-it')
    
    # ASR 引擎配置
    ASR_ENGINE: str = os.getenv('ASR_ENGINE', 'whisper')  # whisper, glm_asr, funasr, vibevoice, etc.

    # GLM-ASR 配置
    GLM_ASR_MODEL: str = "zai-org/GLM-ASR-Nano-2512"
    GLM_ASR_DEVICE: str = "auto"  # auto, cuda, cpu
    GLM_ASR_DTYPE: str = "auto"  # auto, bfloat16, float16, float32

    # FunASR 配置
    FUNASR_MODEL: str = "paraformer-zh"  # paraformer-zh, paraformer-en
    FUNASR_VAD_MODEL: str = "fsmn-vad"
    FUNASR_PUNC_MODEL: str = "ct-punc-c"
    FUNASR_DEVICE: str = "cuda"  # cuda, cpu
    FUNASR_BATCH_SIZE_S: int = 300  # 批次處理音頻長度（秒）

    # VibeVoice 配置
    VIBEVOICE_MODEL: str = "microsoft/VibeVoice-ASR"
    VIBEVOICE_LANGUAGE_MODEL: str = "Qwen/Qwen2.5-7B"
    VIBEVOICE_DEVICE: str = "cuda"  # cuda, cpu
    VIBEVOICE_DTYPE: str = "bfloat16"  # bfloat16, float16, float32
    VIBEVOICE_MAX_NEW_TOKENS: int = 8192

    # Whisper 後端配置
    WHISPER_BACKEND: str = "auto"  # auto, faster_whisper, ctranslate2, transformers
    WHISPER_COMPUTE_TYPE: str = "float16"  # float16, float32, int8, int16
    WHISPER_DEVICE: Optional[str] = None  # cpu or gpu, None for auto-detect
    WHISPER_BEAM_SIZE: int = 5  # beam search size (higher = better quality, more VRAM)
    WHISPER_ADAPTIVE_BEAM: bool = True  # 是否啟用自適應 beam_size
    WHISPER_BEAM_SIZE_MIN: int = 3  # 自適應 beam_size 最小值
    WHISPER_BEAM_SIZE_MAX: int = 10  # 自適應 beam_size 最大值

    # 音頻前處理配置
    AUDIO_HIGHPASS_ENABLED: bool = True        # 高通濾波器（移除低頻隆隆聲，零風險）
    AUDIO_HIGHPASS_CUTOFF_HZ: int = 80         # 高通截止頻率 (Hz)，80Hz 安全不影響人聲
    AUDIO_NOISE_REDUCTION_ENABLED: bool = False # 頻譜閘門降噪（預設關閉，避免傷害 ASR）
    AUDIO_NOISE_REDUCTION_STATIONARY: bool = True  # True=只處理穩態噪音（更安全）
    AUDIO_NOISE_REDUCTION_STRENGTH: float = 0.6    # 降噪強度 (0-1)，越低越保守

    # 音頻響度正規化配置
    AUDIO_LOUDNESS_NORMALIZATION: bool = True  # 總開關：啟用 DRC + LUFS 響度正規化
    AUDIO_DRC_ENABLED: bool = True             # DRC（動態範圍壓縮）開關
    AUDIO_LUFS_ENABLED: bool = True            # LUFS 正規化開關
    AUDIO_LUFS_TARGET: float = -16.0           # 目標 LUFS 值（EBU R128 廣播標準）
    AUDIO_DRC_THRESHOLD: float = -20.0         # DRC 閾值 (dBFS)，高於此值的訊號被壓縮
    AUDIO_DRC_RATIO: float = 4.0               # DRC 壓縮比（4:1）

    # Per-Speaker 響度正規化（Diarization 後）
    AUDIO_PER_SPEAKER_NORM_ENABLED: bool = True    # 每位說話人獨立音量校正
    AUDIO_PER_SPEAKER_NORM_TARGET: float = -16.0   # 目標 LUFS

    # 語音增強配置（神經網路，預設關閉）
    AUDIO_SPEECH_ENHANCEMENT_ENABLED: bool = False  # ClearerVoice 語音增強
    AUDIO_SPEECH_ENHANCEMENT_MODEL: str = "MossFormerGAN_SE_16K"  # 增強模型

    # 多人重疊語音優化配置
    WHISPER_OVERLAP_MODE: bool = True  # 放寬 Whisper VAD/過濾參數，保留重疊語音

    # AI 引擎配置
    AI_ENGINE: str = "ollama"  # ollama 或 vllm
    
    # Ollama 配置
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_TIMEOUT: int = 1800  # 30分鐘
    
    # vLLM 配置
    VLLM_URL: str = "http://localhost:8000"
    VLLM_TIMEOUT: int = 1800  # 30分鐘
    HF_TOKEN: Optional[str] = None  # Hugging Face Token
    
    # 資源管理配置
    CLEANUP_INTERVAL: int = 300  # 5分鐘
    MAX_MEMORY_GB: float = 8.0
    GPU_MEMORY_FRACTION: float = 0.8
    
    # 任務隊列配置
    MAX_QUEUE_SIZE: int = 100
    TASK_TIMEOUT: int = 3600  # 60分鐘
    MAX_CONCURRENT_TASKS: int = 2
    
    # 上傳限制配置
    MAX_BATCH_UPLOAD_COUNT: int = 5
    AUTO_RETRY_COUNT: int = 3
    RETRY_INTERVAL: int = 5
    
    # 文件清理配置
    # 注意：上傳的音視頻文件將在任務完成後自動刪除
    
    # 音頻處理配置
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHUNK_DURATION: int = 120  # 秒 - 調整為120秒以提供更好的轉錄連貫性
    AUDIO_MAX_DURATION: int = int(os.getenv('AUDIO_MAX_DURATION', 43200))  # 預設12小時，可通過環境變數配置
    
    # 日誌配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = "app.log"
    
    def __post_init__(self):
        """初始化後處理"""
        if self.ALLOWED_EXTENSIONS is None:
            self.ALLOWED_EXTENSIONS = {
                # 音頻格式
                '.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac', '.wma',
                # 影片格式
                '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'
            }

        # 創建必要的目錄
        os.makedirs(self.UPLOAD_FOLDER, exist_ok=True)
        # 注意：Docker 環境的 URL 調整已移至 from_env() 方法中
        # 必須在載入環境變數後執行，否則會被 .env 文件覆蓋
    
    @classmethod
    def from_env(cls):
        """從環境變數載入配置"""
        config = cls()
        loaded_vars = []
        
        print("🔧 開始載入環境變數配置...")
        
        # 覆蓋環境變數中的設置
        for field in config.__dataclass_fields__:
            env_value = os.getenv(field)
            if env_value is not None and env_value.strip():  # 只處理非空值
                # 類型轉換
                field_type = config.__dataclass_fields__[field].type
                try:
                    old_value = getattr(config, field)
                    if field_type == bool:
                        new_value = env_value.lower() in ('true', '1', 'yes')
                        setattr(config, field, new_value)
                    elif field_type == int:
                        new_value = int(env_value)
                        setattr(config, field, new_value)
                    elif field_type == float:
                        new_value = float(env_value)
                        setattr(config, field, new_value)
                    elif hasattr(field_type, '__origin__') and field_type.__origin__ is Union:
                        # 處理 Optional[str] 類型
                        if env_value.strip():
                            new_value = env_value
                            setattr(config, field, new_value)
                        else:
                            new_value = None
                            setattr(config, field, new_value)
                    else:
                        new_value = env_value
                        setattr(config, field, new_value)
                    
                    loaded_vars.append(f"  {field}: {old_value} → {new_value}")
                    
                except (ValueError, TypeError) as e:
                    print(f"⚠️ Invalid value for {field}: {env_value}, using default")
        
        # 特殊處理：從MB轉換為字節
        max_upload_mb = os.getenv('MAX_UPLOAD_SIZE')
        if max_upload_mb:
            try:
                old_value = config.MAX_CONTENT_LENGTH
                config.MAX_CONTENT_LENGTH = int(max_upload_mb) * 1024 * 1024
                loaded_vars.append(f"  MAX_CONTENT_LENGTH: {old_value} → {config.MAX_CONTENT_LENGTH} (from MAX_UPLOAD_SIZE={max_upload_mb}MB)")
            except ValueError:
                print(f"⚠️ Invalid MAX_UPLOAD_SIZE value: {max_upload_mb}")
        
        # 特殊處理：處理超時設定
        timeout = os.getenv('PROCESSING_TIMEOUT')
        if timeout:
            try:
                old_value = config.TASK_TIMEOUT
                config.TASK_TIMEOUT = int(timeout)
                loaded_vars.append(f"  TASK_TIMEOUT: {old_value} → {config.TASK_TIMEOUT} (from PROCESSING_TIMEOUT={timeout})")
            except ValueError:
                print(f"⚠️ Invalid PROCESSING_TIMEOUT value: {timeout}")
        
        if loaded_vars:
            # 只顯示摘要，避免每個 worker 都打印詳細配置
            worker_id = os.getenv('GUNICORN_WORKER_ID', str(os.getpid()))
            print(f"✅ 配置已載入 ({len(loaded_vars)} 個環境變數) [Worker: {worker_id}]")
        else:
            print("ℹ️ 使用默認配置")

        # 🎯 智能主機地址檢測（跨平台支持）
        # 如果 OLLAMA_URL 環境變量未設置，則自動檢測最佳主機地址
        if not os.getenv('OLLAMA_URL'):
            try:
                from utils.host_detector import get_ollama_url
                detected_url = get_ollama_url()
                if detected_url != config.OLLAMA_URL:
                    old_url = config.OLLAMA_URL
                    config.OLLAMA_URL = detected_url
                    print(f"🔍 自動檢測：Ollama URL {old_url} → {config.OLLAMA_URL}")
            except ImportError:
                print("⚠️ host_detector 模塊未找到，使用默認配置")
            except Exception as e:
                print(f"⚠️ 自動檢測失敗: {e}，使用默認配置")

        return config
    
    def get_current_ai_model(self) -> str:
        """根據目前引擎類型返回對應的AI模型（摘要用）"""
        if self.AI_ENGINE == "vllm":
            return self.VLLM_MODEL_FIXED or self.DEFAULT_AI_MODEL
        else:  # ollama
            return self.OLLAMA_MODEL_FIXED or self.DEFAULT_AI_MODEL

    def get_refinement_model(self) -> str:
        """獲取 Refinement Agent 專用模型

        根據 REFINEMENT_ENGINE 類型返回對應的 Refinement 模型。
        支持混合引擎：例如摘要用 Ollama，refinement 用 vLLM。

        Returns:
            Refinement Agent 使用的模型名稱
        """
        if self.REFINEMENT_ENGINE == "vllm":
            return self.VLLM_REFINEMENT_MODEL or self.get_current_ai_model()
        else:  # ollama
            return self.OLLAMA_REFINEMENT_MODEL or self.get_current_ai_model()

    def get_refinement_url(self) -> str:
        """獲取 Refinement 引擎的 API URL"""
        if self.REFINEMENT_ENGINE == "vllm":
            return self.VLLM_URL
        else:
            return self.OLLAMA_URL

    def get_refinement_timeout(self) -> int:
        """獲取 Refinement 引擎的超時設定"""
        if self.REFINEMENT_ENGINE == "vllm":
            return self.VLLM_TIMEOUT
        else:
            return self.OLLAMA_TIMEOUT
    
    def get_current_ai_url(self) -> str:
        """根據目前引擎類型返回對應的API URL"""
        if self.AI_ENGINE == "vllm":
            return self.VLLM_URL
        else:  # ollama
            return self.OLLAMA_URL
    
    def get_current_ai_timeout(self) -> int:
        """根據目前引擎類型返回對應的超時設定"""
        if self.AI_ENGINE == "vllm":
            return self.VLLM_TIMEOUT
        else:  # ollama
            return self.OLLAMA_TIMEOUT
    
    @property
    def AI_MODEL_FIXED(self) -> str:
        """向後兼容屬性 - 重定向到當前引擎的模型"""
        return self.get_current_ai_model()

# 全局配置實例
config = AppConfig.from_env()