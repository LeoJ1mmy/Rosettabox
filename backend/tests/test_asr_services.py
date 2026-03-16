"""
ASR 服務單元測試

測試 ASR 抽象層的各個組件：
- ASREngine 抽象接口
- WhisperASRAdapter 適配器
- ASRFactory 工廠
- ASRService 服務
"""

import unittest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 確保可以導入 backend 模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestASREngineInterface(unittest.TestCase):
    """測試 ASREngine 抽象接口"""

    def test_asr_engine_is_abstract(self):
        """確認 ASREngine 是抽象類，不能直接實例化"""
        from services.asr_engine import ASREngine

        with self.assertRaises(TypeError):
            ASREngine()

    def test_asr_engine_has_required_methods(self):
        """確認 ASREngine 定義了所有必需的抽象方法"""
        from services.asr_engine import ASREngine
        import inspect

        # 獲取所有抽象方法
        abstract_methods = []
        for name, method in inspect.getmembers(ASREngine, predicate=inspect.isfunction):
            if getattr(method, '__isabstractmethod__', False):
                abstract_methods.append(name)

        # 確認必需的方法存在
        required_methods = ['load_model', 'transcribe', 'cleanup', 'get_model_info']
        for method in required_methods:
            self.assertIn(method, abstract_methods, f"缺少抽象方法: {method}")

    def test_asr_engine_default_methods(self):
        """測試 ASREngine 的默認方法實現"""
        from services.asr_engine import ASREngine

        # 創建一個具體的測試實現
        class TestEngine(ASREngine):
            def load_model(self): return True
            def transcribe(self, audio, **kwargs): return {}
            def cleanup(self): pass
            def get_model_info(self): return {}
            @property
            def is_loaded(self): return True

        engine = TestEngine()

        # 測試默認方法
        self.assertFalse(engine.supports_vad())
        self.assertFalse(engine.supports_word_timestamps())
        self.assertIsInstance(engine.get_supported_languages(), list)
        self.assertFalse(engine.switch_backend("test"))


class TestWhisperASRAdapter(unittest.TestCase):
    """測試 WhisperASRAdapter 適配器"""

    def test_adapter_initialization(self):
        """測試適配器初始化（使用真實 WhisperManager）"""
        from services.whisper_adapter import WhisperASRAdapter

        adapter = WhisperASRAdapter(backend="faster_whisper", model_size="base")

        # 確認適配器正確初始化
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.model_size, "base")
        self.assertEqual(adapter.backend, "faster_whisper")

    def test_adapter_implements_asr_engine(self):
        """測試適配器實現了 ASREngine 接口"""
        from services.whisper_adapter import WhisperASRAdapter
        from services.asr_engine import ASREngine

        adapter = WhisperASRAdapter()
        self.assertIsInstance(adapter, ASREngine)

    def test_adapter_has_required_methods(self):
        """測試適配器具有所有必需的方法"""
        from services.whisper_adapter import WhisperASRAdapter

        adapter = WhisperASRAdapter()

        # 確認所有必需方法存在
        self.assertTrue(hasattr(adapter, 'load_model'))
        self.assertTrue(hasattr(adapter, 'transcribe'))
        self.assertTrue(hasattr(adapter, 'cleanup'))
        self.assertTrue(hasattr(adapter, 'get_model_info'))
        self.assertTrue(hasattr(adapter, 'is_loaded'))

    def test_adapter_get_model_info_before_load(self):
        """測試載入前獲取模型信息"""
        from services.whisper_adapter import WhisperASRAdapter

        adapter = WhisperASRAdapter(backend="auto", model_size="base")
        info = adapter.get_model_info()

        self.assertEqual(info["engine"], "whisper")
        self.assertEqual(info["model_size"], "base")
        self.assertFalse(info["is_loaded"])

    def test_adapter_properties(self):
        """測試適配器屬性訪問"""
        from services.whisper_adapter import WhisperASRAdapter

        adapter = WhisperASRAdapter(backend="auto", model_size="large")

        self.assertEqual(adapter.model_size, "large")
        # backend 在初始化時會自動選擇（auto -> faster_whisper/ctranslate2/transformers）
        self.assertIn(adapter.backend, ["auto", "faster_whisper", "ctranslate2", "transformers"])
        self.assertFalse(adapter.is_loaded)

    def test_adapter_supports_vad(self):
        """測試 VAD 支持檢查"""
        from services.whisper_adapter import WhisperASRAdapter

        adapter = WhisperASRAdapter(backend="faster_whisper", model_size="base")
        # faster_whisper 後端支持 VAD
        # 但在載入前 current_backend 為 None，所以不支持
        self.assertIsInstance(adapter.supports_vad(), bool)

    def test_adapter_supports_word_timestamps(self):
        """測試詞級時間戳支持檢查"""
        from services.whisper_adapter import WhisperASRAdapter

        adapter = WhisperASRAdapter(backend="faster_whisper", model_size="base")
        self.assertIsInstance(adapter.supports_word_timestamps(), bool)

    def test_adapter_get_supported_languages(self):
        """測試獲取支持的語言"""
        from services.whisper_adapter import WhisperASRAdapter

        adapter = WhisperASRAdapter()
        languages = adapter.get_supported_languages()

        self.assertIsInstance(languages, list)
        self.assertIn("zh", languages)
        self.assertIn("en", languages)

    def test_adapter_manager_property(self):
        """測試獲取底層 manager"""
        from services.whisper_adapter import WhisperASRAdapter
        from whisper_integration import WhisperManager

        adapter = WhisperASRAdapter()
        manager = adapter.manager

        self.assertIsInstance(manager, WhisperManager)


class TestASRFactory(unittest.TestCase):
    """測試 ASRFactory 工廠"""

    def test_factory_supported_engines(self):
        """測試工廠支持的引擎列表"""
        from services.asr_factory import ASRFactory

        supported = ASRFactory.SUPPORTED_ENGINES
        self.assertIn("whisper", supported)
        self.assertIn("vosk", supported)
        self.assertIn("huggingface", supported)

    def test_factory_get_registered_engines(self):
        """測試獲取已註冊的引擎"""
        from services.asr_factory import ASRFactory

        engines = ASRFactory.get_registered_engines()
        self.assertIsInstance(engines, list)
        self.assertIn("whisper", engines)

    def test_factory_get_available_engines(self):
        """測試獲取可用引擎狀態"""
        from services.asr_factory import ASRFactory

        available = ASRFactory.get_available_engines()
        self.assertIsInstance(available, dict)
        self.assertIn("whisper", available)
        # Whisper 應該是可用的
        self.assertTrue(available["whisper"])

    def test_factory_create_whisper(self):
        """測試工廠創建 Whisper 引擎"""
        from services.asr_factory import ASRFactory
        from services.whisper_adapter import WhisperASRAdapter

        engine = ASRFactory.create("whisper", backend="auto", model_size="base")

        self.assertIsInstance(engine, WhisperASRAdapter)
        self.assertEqual(engine.model_size, "base")

    def test_factory_create_unknown_engine(self):
        """測試工廠創建未知引擎時拋出異常"""
        from services.asr_factory import ASRFactory

        with self.assertRaises(ValueError) as context:
            ASRFactory.create("unknown_engine")

        self.assertIn("未知的 ASR 引擎類型", str(context.exception))

    def test_factory_is_available_whisper(self):
        """測試 Whisper 可用性檢查"""
        from services.asr_factory import ASRFactory

        # Whisper 應該是可用的（因為 whisper_integration 存在）
        self.assertTrue(ASRFactory.is_available("whisper"))

    def test_factory_is_available_unknown(self):
        """測試未知引擎的可用性檢查"""
        from services.asr_factory import ASRFactory

        self.assertFalse(ASRFactory.is_available("nonexistent_engine"))

    def test_factory_get_engine_info(self):
        """測試獲取引擎信息"""
        from services.asr_factory import ASRFactory

        info = ASRFactory.get_engine_info("whisper")

        self.assertEqual(info["name"], "whisper")
        self.assertIn("description", info)
        self.assertIn("available", info)
        self.assertIn("registered", info)

    def test_factory_register_custom_engine(self):
        """測試註冊自定義引擎"""
        from services.asr_factory import ASRFactory
        from services.asr_engine import ASREngine

        # 創建一個測試引擎類
        class CustomEngine(ASREngine):
            def load_model(self): return True
            def transcribe(self, audio, **kwargs): return {"text": "custom"}
            def cleanup(self): pass
            def get_model_info(self): return {"engine": "custom"}
            @property
            def is_loaded(self): return True

        # 註冊
        ASRFactory.register("custom_test", CustomEngine)

        # 確認已註冊
        self.assertIn("custom_test", ASRFactory.get_registered_engines())

        # 清理
        del ASRFactory._engines["custom_test"]


class TestASRService(unittest.TestCase):
    """測試 ASRService 服務"""

    def setUp(self):
        """每個測試前重置單例"""
        from services.asr_service import ASRService
        ASRService.reset_instance()

    def tearDown(self):
        """每個測試後重置單例"""
        from services.asr_service import ASRService
        ASRService.reset_instance()

    def test_service_singleton(self):
        """測試服務單例模式"""
        from services.asr_service import ASRService, get_asr_service

        service1 = ASRService.get_instance()
        service2 = ASRService.get_instance()
        service3 = get_asr_service()

        self.assertIs(service1, service2)
        self.assertIs(service2, service3)

    @patch('services.asr_service.ASRFactory')
    def test_service_get_engine(self, mock_factory):
        """測試服務獲取引擎"""
        from services.asr_service import ASRService

        mock_engine = Mock()
        mock_engine.is_loaded = False
        mock_factory.create.return_value = mock_engine

        service = ASRService.get_instance()
        engine = service.get_engine(backend="auto", model_size="base")

        self.assertEqual(engine, mock_engine)
        mock_factory.create.assert_called_once()

    @patch('services.asr_service.ASRFactory')
    def test_service_get_engine_caching(self, mock_factory):
        """測試服務引擎緩存"""
        from services.asr_service import ASRService

        mock_engine = Mock()
        mock_engine.is_loaded = True
        mock_factory.create.return_value = mock_engine

        service = ASRService.get_instance()

        # 第一次獲取
        engine1 = service.get_engine(backend="auto", model_size="base")
        # 第二次獲取（相同配置）
        engine2 = service.get_engine(backend="auto", model_size="base")

        # 應該只創建一次
        self.assertEqual(mock_factory.create.call_count, 1)
        self.assertIs(engine1, engine2)

    @patch('services.asr_service.ASRFactory')
    def test_service_cleanup(self, mock_factory):
        """測試服務清理"""
        from services.asr_service import ASRService

        mock_engine = Mock()
        mock_factory.create.return_value = mock_engine

        service = ASRService.get_instance()
        service.get_engine()
        service.cleanup()

        mock_engine.cleanup.assert_called_once()

    @patch('services.asr_service.ASRFactory')
    def test_service_get_model_info_not_loaded(self, mock_factory):
        """測試未載入時獲取模型信息"""
        from services.asr_service import ASRService

        service = ASRService.get_instance()
        info = service.get_model_info()

        self.assertEqual(info["status"], "not_loaded")

    @patch('services.asr_service.ASRFactory')
    def test_service_get_model_info_loaded(self, mock_factory):
        """測試已載入時獲取模型信息"""
        from services.asr_service import ASRService

        mock_engine = Mock()
        mock_engine.is_loaded = True
        mock_engine.get_model_info.return_value = {
            "engine": "whisper",
            "backend": "faster_whisper"
        }
        mock_factory.create.return_value = mock_engine

        service = ASRService.get_instance()
        service.get_engine()
        info = service.get_model_info()

        self.assertEqual(info["engine"], "whisper")

    @patch('services.asr_service.ASRFactory')
    def test_service_is_ready(self, mock_factory):
        """測試服務就緒狀態"""
        from services.asr_service import ASRService

        service = ASRService.get_instance()

        # 初始狀態應該不就緒
        self.assertFalse(service.is_ready())

        # 創建引擎並設置為已載入
        mock_engine = Mock()
        mock_engine.is_loaded = True
        mock_factory.create.return_value = mock_engine

        service.get_engine()
        self.assertTrue(service.is_ready())


class TestBackwardCompatibility(unittest.TestCase):
    """測試向後兼容性"""

    def test_whisper_manager_still_importable(self):
        """確認 WhisperManager 仍可直接導入"""
        try:
            from whisper_integration import WhisperManager
            self.assertTrue(True)
        except ImportError:
            self.fail("WhisperManager 無法導入")

    def test_get_whisper_model_info_function(self):
        """測試向後兼容的 get_whisper_model_info 函數"""
        from services.asr_service import get_whisper_model_info

        info = get_whisper_model_info()

        # 應該返回舊格式
        self.assertIn("model_loaded", info)
        self.assertIn("model_size", info)
        self.assertIn("backend", info)
        self.assertIn("device", info)


class TestGLMASRAdapter(unittest.TestCase):
    """測試 GLMASRAdapter 適配器"""

    def test_adapter_initialization(self):
        """測試 GLM-ASR 適配器初始化"""
        from services.glm_asr_adapter import GLMASRAdapter

        adapter = GLMASRAdapter(model_id="zai-org/GLM-ASR-Nano-2512")

        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.model_id, "zai-org/GLM-ASR-Nano-2512")
        self.assertFalse(adapter.is_loaded)

    def test_adapter_implements_asr_engine(self):
        """測試適配器實現了 ASREngine 接口"""
        from services.glm_asr_adapter import GLMASRAdapter
        from services.asr_engine import ASREngine

        adapter = GLMASRAdapter()
        self.assertIsInstance(adapter, ASREngine)

    def test_adapter_has_required_methods(self):
        """測試適配器具有所有必需的方法"""
        from services.glm_asr_adapter import GLMASRAdapter

        adapter = GLMASRAdapter()

        self.assertTrue(hasattr(adapter, 'load_model'))
        self.assertTrue(hasattr(adapter, 'transcribe'))
        self.assertTrue(hasattr(adapter, 'cleanup'))
        self.assertTrue(hasattr(adapter, 'get_model_info'))
        self.assertTrue(hasattr(adapter, 'is_loaded'))

    def test_adapter_get_model_info_before_load(self):
        """測試載入前獲取模型信息"""
        from services.glm_asr_adapter import GLMASRAdapter

        adapter = GLMASRAdapter(model_id="zai-org/GLM-ASR-Nano-2512")
        info = adapter.get_model_info()

        self.assertEqual(info["engine"], "glm_asr")
        self.assertEqual(info["backend"], "transformers")
        self.assertEqual(info["model_size"], "zai-org/GLM-ASR-Nano-2512")
        self.assertFalse(info["is_loaded"])

    def test_adapter_supports_vad(self):
        """測試 VAD 支持檢查 - GLM-ASR 不內置 VAD"""
        from services.glm_asr_adapter import GLMASRAdapter

        adapter = GLMASRAdapter()
        self.assertFalse(adapter.supports_vad())

    def test_adapter_supports_word_timestamps(self):
        """測試詞級時間戳支持檢查 - GLM-ASR 不直接支持"""
        from services.glm_asr_adapter import GLMASRAdapter

        adapter = GLMASRAdapter()
        self.assertFalse(adapter.supports_word_timestamps())

    def test_adapter_get_supported_languages(self):
        """測試獲取支持的語言"""
        from services.glm_asr_adapter import GLMASRAdapter

        adapter = GLMASRAdapter()
        languages = adapter.get_supported_languages()

        self.assertIsInstance(languages, list)
        self.assertIn("zh", languages)  # 中文
        self.assertIn("en", languages)  # 英文
        self.assertIn("yue", languages)  # 粵語

    def test_transcribe_without_model_returns_error(self):
        """測試未載入模型時轉錄返回錯誤"""
        from services.glm_asr_adapter import GLMASRAdapter
        import numpy as np

        adapter = GLMASRAdapter()
        audio = np.zeros(16000, dtype=np.float32)

        result = adapter.transcribe(audio)
        self.assertEqual(result["text"], "")
        self.assertIn("error", result)


class TestASRFactoryGLMASR(unittest.TestCase):
    """測試 ASRFactory 的 GLM-ASR 支持"""

    def test_factory_supports_glm_asr(self):
        """測試工廠支持 GLM-ASR 引擎"""
        from services.asr_factory import ASRFactory

        supported = ASRFactory.SUPPORTED_ENGINES
        self.assertIn("glm_asr", supported)

    def test_factory_create_glm_asr(self):
        """測試工廠創建 GLM-ASR 引擎"""
        from services.asr_factory import ASRFactory
        from services.glm_asr_adapter import GLMASRAdapter

        engine = ASRFactory.create("glm_asr", model_id="zai-org/GLM-ASR-Nano-2512")

        self.assertIsInstance(engine, GLMASRAdapter)
        self.assertEqual(engine.model_id, "zai-org/GLM-ASR-Nano-2512")

    def test_factory_is_available_glm_asr(self):
        """測試 GLM-ASR 可用性檢查"""
        from services.asr_factory import ASRFactory

        # GLM-ASR 依賴 transformers 和 torch
        # 如果已安裝則應該是可用的
        is_available = ASRFactory.is_available("glm_asr")
        self.assertIsInstance(is_available, bool)

    def test_factory_get_engine_info_glm_asr(self):
        """測試獲取 GLM-ASR 引擎信息"""
        from services.asr_factory import ASRFactory

        info = ASRFactory.get_engine_info("glm_asr")

        self.assertEqual(info["name"], "glm_asr")
        self.assertIn("description", info)
        self.assertIn("available", info)


class TestIntegration(unittest.TestCase):
    """整合測試（需要實際的 Whisper 環境）"""

    @unittest.skipIf(
        os.environ.get('SKIP_INTEGRATION_TESTS', 'true').lower() == 'true',
        "跳過整合測試（設置 SKIP_INTEGRATION_TESTS=false 來執行）"
    )
    def test_whisper_adapter_real_initialization(self):
        """測試 Whisper 適配器實際初始化"""
        from services.whisper_adapter import WhisperASRAdapter

        adapter = WhisperASRAdapter(backend="auto", model_size="base")

        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.model_size, "base")

    @unittest.skipIf(
        os.environ.get('SKIP_INTEGRATION_TESTS', 'true').lower() == 'true',
        "跳過整合測試（設置 SKIP_INTEGRATION_TESTS=false 來執行）"
    )
    def test_factory_create_real_whisper(self):
        """測試工廠實際創建 Whisper 引擎"""
        from services.asr_factory import ASRFactory

        engine = ASRFactory.create("whisper", backend="auto", model_size="base")

        self.assertIsNotNone(engine)
        info = engine.get_model_info()
        self.assertEqual(info["engine"], "whisper")


if __name__ == '__main__':
    unittest.main(verbosity=2)
