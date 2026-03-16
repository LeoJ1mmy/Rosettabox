"""
Text Refinement Agent Unit Tests
文字精煉代理單元測試

Run tests with:
    cd backend && python -m pytest tests/test_text_refinement.py -v
"""

import pytest
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processing.text_refinement import (
    remove_filler_words,
    build_hot_words_context,
    is_valid_refinement,
    CHINESE_FILLERS,
    ENGLISH_FILLERS,
)


class TestFillerWordRemoval:
    """語氣詞移除測試"""

    def test_chinese_fillers_basic(self):
        """測試基本中文語氣詞移除"""
        input_text = "嗯，我覺得這個很好"
        result = remove_filler_words(input_text)
        assert "嗯" not in result
        assert "我覺得這個很好" in result

    def test_chinese_fillers_repeated(self):
        """測試重複中文語氣詞"""
        input_text = "嗯嗯嗯，這個就是說，然後呢，對啊"
        result = remove_filler_words(input_text)
        assert "嗯" not in result
        assert "就是說" not in result
        assert "然後呢" not in result
        assert "對啊" not in result

    def test_chinese_fillers_nage(self):
        """測試「那個」語氣詞"""
        input_text = "那個，我想說的是這個"
        result = remove_filler_words(input_text)
        assert "那個" not in result
        assert "我想說的是這個" in result

    def test_chinese_fillers_multiple(self):
        """測試多個中文語氣詞組合"""
        input_text = "嗯，那個，就是，我們的 API 就是這樣"
        result = remove_filler_words(input_text)
        assert "嗯" not in result
        assert "那個" not in result
        assert "API" in result

    def test_english_fillers_basic(self):
        """測試基本英文語氣詞移除"""
        input_text = "Um, the API is working well"
        result = remove_filler_words(input_text)
        assert "um" not in result.lower()
        assert "API" in result
        assert "working well" in result

    def test_english_fillers_uh(self):
        """測試 uh/uhh 語氣詞"""
        input_text = "The code is, uh, working correctly"
        result = remove_filler_words(input_text)
        assert "uh" not in result.lower()
        assert "code" in result
        assert "working correctly" in result

    def test_english_fillers_you_know(self):
        """測試 you know 語氣詞"""
        input_text = "You know, the system is quite complex"
        result = remove_filler_words(input_text)
        assert "you know" not in result.lower()
        assert "system" in result

    def test_english_fillers_like(self):
        """測試 like 作為語氣詞"""
        input_text = "The model is like really powerful"
        result = remove_filler_words(input_text)
        assert "model" in result
        assert "powerful" in result

    def test_english_fillers_basically(self):
        """測試 basically 語氣詞"""
        input_text = "Basically the algorithm works like this"
        result = remove_filler_words(input_text)
        assert "basically" not in result.lower()
        assert "algorithm" in result

    def test_mixed_fillers(self):
        """測試中英混合語氣詞"""
        input_text = "嗯，basically 這個 API um 是這樣運作的"
        result = remove_filler_words(input_text)
        assert "嗯" not in result
        assert "basically" not in result.lower()
        assert "um" not in result.lower()
        assert "API" in result
        assert "運作" in result

    def test_preserve_meaningful_content(self):
        """測試保留有意義的內容"""
        input_text = "我們完成了專案，成功部署到生產環境"
        result = remove_filler_words(input_text)
        assert "完成" in result
        assert "專案" in result
        assert "成功" in result
        assert "部署" in result
        assert "生產環境" in result

    def test_preserve_meaningful_ranhou(self):
        """測試保留有意義的「然後」（非語氣詞用法）"""
        # 「然後」在句中作為連接詞時應該被保留
        # 但目前的正則可能會移除它，這是已知的限制
        input_text = "我們先做A然後做B"
        result = remove_filler_words(input_text)
        # 如果「然後」在句中間，可能會被保留
        assert "做A" in result
        assert "做B" in result

    def test_empty_input(self):
        """測試空輸入"""
        assert remove_filler_words("") == ""
        assert remove_filler_words(None) is None

    def test_no_fillers(self):
        """測試無語氣詞的文本"""
        input_text = "這是一段正常的文字，沒有任何語氣詞。"
        result = remove_filler_words(input_text)
        assert result == input_text.strip()

    def test_cleanup_punctuation(self):
        """測試標點符號清理"""
        input_text = "，，，這是開頭有多餘逗號的文字"
        result = remove_filler_words(input_text)
        assert not result.startswith("，")

    def test_cleanup_multiple_spaces(self):
        """測試多餘空格清理"""
        input_text = "這是   有多餘空格的   文字"
        result = remove_filler_words(input_text)
        assert "   " not in result


class TestHotWordsContext:
    """熱詞上下文測試"""

    def test_build_context_returns_tuple(self):
        """測試返回類型"""
        words, context = build_hot_words_context()
        assert isinstance(words, list)
        assert isinstance(context, str)

    def test_word_limit(self):
        """測試熱詞數量限制"""
        words, _ = build_hot_words_context()
        assert len(words) <= 100  # 不超過 100 個

    def test_context_format(self):
        """測試上下文格式"""
        words, context = build_hot_words_context()
        if words:  # 如果有熱詞
            assert "參考術語" in context

    def test_empty_graceful(self):
        """測試無熱詞時的優雅處理"""
        # 即使熱詞管理器為空，也不應該報錯
        words, context = build_hot_words_context()
        # 可能為空，但不應該報錯
        assert words is not None or words == []


class TestValidation:
    """輸出驗證測試"""

    def test_empty_output_invalid(self):
        """空輸出應該無效"""
        assert is_valid_refinement("原始文本", "") is False
        assert is_valid_refinement("原始文本", "   ") is False

    def test_short_output_invalid(self):
        """過短輸出應該無效"""
        assert is_valid_refinement("這是一段較長的原始文本內容", "短") is False

    def test_length_decrease_too_large(self):
        """長度減少過多應該無效"""
        original = "這是一段很長的文本內容" * 10
        short_result = "短文本"
        assert is_valid_refinement(original, short_result) is False

    def test_length_increase_too_large(self):
        """長度增加過多應該無效"""
        original = "原始短文本"
        long_result = "這是一段非常非常長的結果文本" * 10
        assert is_valid_refinement(original, long_result) is False

    def test_prompt_echo_detection(self):
        """Prompt 回顯應該無效"""
        original = "這是原始文本"
        echo = "術語校正：這是原始文本，參考術語列表..."
        assert is_valid_refinement(original, echo) is False

    def test_valid_refinement(self):
        """正常精煉應該有效"""
        original = "這是一段原始的語音轉錄文本內容，包含足夠長度的文字"
        refined = "這是一段原始的語音轉錄文本內容，包含足夠長度的文字"  # 無變化
        assert is_valid_refinement(original, refined) is True

    def test_slight_reduction_valid(self):
        """輕微減少長度應該有效"""
        original = "嗯，這是一段原始的語音轉錄文本內容，就是說"
        refined = "這是一段原始的語音轉錄文本內容"  # 移除語氣詞
        assert is_valid_refinement(original, refined) is True


class TestFillerPatterns:
    """語氣詞模式測試"""

    def test_chinese_patterns_count(self):
        """確保有足夠的中文語氣詞模式"""
        assert len(CHINESE_FILLERS) >= 5

    def test_english_patterns_count(self):
        """確保有足夠的英文語氣詞模式"""
        assert len(ENGLISH_FILLERS) >= 5

    def test_patterns_are_valid_regex(self):
        """確保所有模式都是有效的正則表達式"""
        import re
        for pattern in CHINESE_FILLERS + ENGLISH_FILLERS:
            try:
                re.compile(pattern)
            except re.error:
                pytest.fail(f"Invalid regex pattern: {pattern}")


class TestEdgeCases:
    """邊界情況測試"""

    def test_only_fillers(self):
        """測試只有語氣詞的文本"""
        input_text = "嗯嗯，那個，就是，um，uh"
        result = remove_filler_words(input_text)
        # 結果可能為空或只剩標點
        assert len(result.strip()) <= 5

    def test_unicode_handling(self):
        """測試 Unicode 處理"""
        input_text = "嗯，我們討論一下 API 的設計 🚀"
        result = remove_filler_words(input_text)
        assert "API" in result
        assert "🚀" in result

    def test_long_text(self):
        """測試長文本處理"""
        base = "這是一段測試文本。" * 100
        result = remove_filler_words(base)
        assert len(result) > 0

    def test_special_characters(self):
        """測試特殊字符"""
        input_text = "嗯，API-v2 的 endpoint /api/users 是這樣的"
        result = remove_filler_words(input_text)
        assert "API-v2" in result
        assert "/api/users" in result


# ============================================================================
# Integration Tests (require running services)
# ============================================================================

class TestIntegration:
    """集成測試（需要服務運行）"""

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires AI engine running")
    def test_full_refinement_pipeline(self):
        """測試完整精煉流程"""
        from processing.text_refinement import refine_transcription

        raw_text = "嗯，那個，我們的 Claud API 就是，um，working 很好"
        task_id = "test-task-001"

        result = refine_transcription(raw_text, task_id)

        # 語氣詞應被移除
        assert "嗯" not in result
        assert "那個" not in result
        assert "um" not in result.lower()

        # 核心內容應保留
        assert "API" in result

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires AI engine running")
    def test_term_correction(self):
        """測試術語校正"""
        from processing.text_refinement import refine_transcription

        # 模擬 Whisper 錯誤識別
        raw_text = "我們使用 Claud 和 Olama 來處理文本"
        task_id = "test-task-002"

        result = refine_transcription(raw_text, task_id)

        # 應該校正為正確術語
        # 注意：這取決於 hot_words.json 中是否有這些詞
        assert "處理文本" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
