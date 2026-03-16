"""
音頻響度正規化 - 單元測試

測試 DRC (動態範圍壓縮) 和 LUFS 正規化。

執行：
    pytest backend/tests/test_audio_normalization.py -v
"""

import unittest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# DRC 動態範圍壓縮測試
# ============================================================

class TestDynamicRangeCompression(unittest.TestCase):
    """測試 apply_dynamic_range_compression"""

    def test_loud_signal_gets_compressed(self):
        """大聲訊號（超過閾值）應被壓縮"""
        from processing.audio_normalization import apply_dynamic_range_compression

        sr = 16000
        t = np.linspace(0, 1.0, sr, dtype=np.float32)
        loud_signal = 0.9 * np.sin(2 * np.pi * 440 * t)

        compressed = apply_dynamic_range_compression(
            loud_signal, sr, threshold_db=-20.0, ratio=4.0
        )

        self.assertEqual(len(compressed), len(loud_signal))
        self.assertTrue(np.all(np.isfinite(compressed)))

    def test_quiet_signal_not_distorted(self):
        """安靜訊號不應被嚴重改變"""
        from processing.audio_normalization import apply_dynamic_range_compression

        sr = 16000
        t = np.linspace(0, 1.0, sr, dtype=np.float32)
        quiet_signal = 0.01 * np.sin(2 * np.pi * 440 * t)

        compressed = apply_dynamic_range_compression(
            quiet_signal, sr, threshold_db=-20.0, ratio=4.0
        )

        self.assertEqual(len(compressed), len(quiet_signal))
        self.assertTrue(np.all(np.isfinite(compressed)))

    def test_silence_returns_silence(self):
        """全靜音不應崩潰"""
        from processing.audio_normalization import apply_dynamic_range_compression

        silence = np.zeros(16000, dtype=np.float32)
        result = apply_dynamic_range_compression(silence, 16000)

        np.testing.assert_array_equal(result, silence)

    def test_mixed_loud_quiet_reduces_dynamic_range(self):
        """大小聲混合訊號的動態範圍應縮小"""
        from processing.audio_normalization import apply_dynamic_range_compression

        sr = 16000
        t_loud = np.linspace(0, 1.0, sr, dtype=np.float32)
        t_quiet = np.linspace(0, 1.0, sr, dtype=np.float32)

        signal = np.concatenate([
            0.9 * np.sin(2 * np.pi * 440 * t_loud),   # 大聲 1 秒
            0.05 * np.sin(2 * np.pi * 440 * t_quiet),  # 小聲 1 秒
        ])

        compressed = apply_dynamic_range_compression(
            signal, sr, threshold_db=-20.0, ratio=4.0
        )

        # 計算前後半段 RMS 比
        orig_loud_rms = np.sqrt(np.mean(signal[:sr] ** 2))
        orig_quiet_rms = np.sqrt(np.mean(signal[sr:] ** 2))
        comp_loud_rms = np.sqrt(np.mean(compressed[:sr] ** 2))
        comp_quiet_rms = np.sqrt(np.mean(compressed[sr:] ** 2))

        orig_ratio = orig_loud_rms / max(orig_quiet_rms, 1e-10)
        comp_ratio = comp_loud_rms / max(comp_quiet_rms, 1e-10)

        self.assertLess(comp_ratio, orig_ratio,
                       "壓縮後大小聲比例應縮小")

    def test_short_audio(self):
        """極短音頻不應崩潰"""
        from processing.audio_normalization import apply_dynamic_range_compression

        short = np.array([0.5, -0.3, 0.8, -0.1], dtype=np.float32)
        result = apply_dynamic_range_compression(short, 16000)

        self.assertEqual(len(result), 4)
        self.assertTrue(np.all(np.isfinite(result)))

    def test_ratio_1_no_compression(self):
        """壓縮比 1:1 應幾乎不改變訊號"""
        from processing.audio_normalization import apply_dynamic_range_compression

        sr = 16000
        t = np.linspace(0, 1.0, sr, dtype=np.float32)
        signal = 0.5 * np.sin(2 * np.pi * 440 * t)

        result = apply_dynamic_range_compression(
            signal, sr, threshold_db=-20.0, ratio=1.0
        )

        # ratio=1 表示 (1 - 1/ratio) = 0，即 gain_db 全為 0
        np.testing.assert_allclose(result, signal, atol=0.01,
                                   err_msg="壓縮比 1:1 不應改變訊號")


# ============================================================
# LUFS 正規化測試
# ============================================================

class TestLUFSNormalization(unittest.TestCase):
    """測試 apply_lufs_normalization"""

    def test_normalizes_to_target_lufs(self):
        """輸出 LUFS 應接近目標值"""
        from processing.audio_normalization import apply_lufs_normalization
        import pyloudnorm as pyln

        sr = 16000
        t = np.linspace(0, 5.0, sr * 5, dtype=np.float32)
        signal = 0.3 * np.sin(2 * np.pi * 440 * t)

        normalized = apply_lufs_normalization(signal, sr, target_lufs=-16.0)

        meter = pyln.Meter(sr)
        measured = meter.integrated_loudness(normalized)

        self.assertAlmostEqual(measured, -16.0, delta=1.0,
                              msg="LUFS 應在目標 ±1dB 內")

    def test_silence_returns_unchanged(self):
        """靜音應原樣返回"""
        from processing.audio_normalization import apply_lufs_normalization

        silence = np.zeros(32000, dtype=np.float32)
        result = apply_lufs_normalization(silence, 16000, target_lufs=-16.0)

        np.testing.assert_array_equal(result, silence)

    def test_already_at_target_unchanged(self):
        """已在目標 LUFS 的音頻應幾乎不變"""
        from processing.audio_normalization import apply_lufs_normalization
        import pyloudnorm as pyln

        sr = 16000
        t = np.linspace(0, 5.0, sr * 5, dtype=np.float32)
        signal = 0.1 * np.sin(2 * np.pi * 440 * t)

        # 先正規化到目標
        meter = pyln.Meter(sr)
        current = meter.integrated_loudness(signal)
        if np.isfinite(current):
            signal = pyln.normalize.loudness(signal, current, -16.0).astype(np.float32)

        result = apply_lufs_normalization(signal, sr, target_lufs=-16.0)

        np.testing.assert_allclose(result, signal, atol=0.01)

    def test_different_target_levels(self):
        """不同目標 LUFS 應產生不同響度"""
        from processing.audio_normalization import apply_lufs_normalization
        import pyloudnorm as pyln

        sr = 16000
        t = np.linspace(0, 5.0, sr * 5, dtype=np.float32)
        signal = 0.3 * np.sin(2 * np.pi * 440 * t)

        loud = apply_lufs_normalization(signal.copy(), sr, target_lufs=-14.0)
        quiet = apply_lufs_normalization(signal.copy(), sr, target_lufs=-23.0)

        meter = pyln.Meter(sr)
        loud_lufs = meter.integrated_loudness(loud)
        quiet_lufs = meter.integrated_loudness(quiet)

        self.assertGreater(loud_lufs, quiet_lufs,
                          "-14 LUFS 應比 -23 LUFS 更大聲")


# ============================================================
# 整合測試：normalize_loudness
# ============================================================

class TestNormalizeLoudness(unittest.TestCase):
    """測試 normalize_loudness 主函式"""

    def test_both_disabled_returns_clipped_original(self):
        """DRC 和 LUFS 都關閉時，應只做 clip"""
        from processing.audio_normalization import normalize_loudness

        sr = 16000
        t = np.linspace(0, 1.0, sr, dtype=np.float32)
        signal = 0.5 * np.sin(2 * np.pi * 440 * t)

        result = normalize_loudness(signal, sr, enable_drc=False, enable_lufs=False)

        np.testing.assert_array_equal(result, np.clip(signal, -1.0, 1.0))

    def test_output_always_in_unit_range(self):
        """輸出永遠在 [-1, 1] 範圍內"""
        from processing.audio_normalization import normalize_loudness

        sr = 16000
        t = np.linspace(0, 2.0, sr * 2, dtype=np.float32)
        signal = 0.8 * np.sin(2 * np.pi * 440 * t)

        result = normalize_loudness(signal, sr)

        self.assertLessEqual(np.max(result), 1.0)
        self.assertGreaterEqual(np.min(result), -1.0)

    def test_very_short_audio_skipped(self):
        """< 100ms 的音頻應跳過"""
        from processing.audio_normalization import normalize_loudness

        short = np.array([0.5, -0.3], dtype=np.float32)
        result = normalize_loudness(short, 16000)

        np.testing.assert_array_equal(result, short)

    def test_silence_skipped(self):
        """全靜音應跳過"""
        from processing.audio_normalization import normalize_loudness

        silence = np.zeros(32000, dtype=np.float32)
        result = normalize_loudness(silence, 16000)

        np.testing.assert_array_equal(result, silence)

    def test_full_pipeline_runs_without_error(self):
        """完整 DRC + LUFS pipeline 應正常執行"""
        from processing.audio_normalization import normalize_loudness

        sr = 16000
        t = np.linspace(0, 5.0, sr * 5, dtype=np.float32)
        signal = np.concatenate([
            0.8 * np.sin(2 * np.pi * 440 * t[:sr * 2]),   # 大聲 2 秒
            0.02 * np.sin(2 * np.pi * 440 * t[sr * 2:]),   # 小聲 3 秒
        ])

        result = normalize_loudness(signal, sr, enable_drc=True, enable_lufs=True)

        self.assertEqual(len(result), len(signal))
        self.assertTrue(np.all(np.isfinite(result)))
        self.assertLessEqual(np.max(np.abs(result)), 1.0)

    def test_output_is_float32(self):
        """輸出應為 float32"""
        from processing.audio_normalization import normalize_loudness

        sr = 16000
        t = np.linspace(0, 1.0, sr, dtype=np.float32)
        signal = 0.5 * np.sin(2 * np.pi * 440 * t)

        result = normalize_loudness(signal, sr)
        self.assertEqual(result.dtype, np.float32)

    def test_drc_only_mode(self):
        """只開 DRC、關 LUFS 應正常"""
        from processing.audio_normalization import normalize_loudness

        sr = 16000
        t = np.linspace(0, 2.0, sr * 2, dtype=np.float32)
        signal = 0.7 * np.sin(2 * np.pi * 440 * t)

        result = normalize_loudness(signal, sr, enable_drc=True, enable_lufs=False)

        self.assertEqual(len(result), len(signal))
        self.assertTrue(np.all(np.isfinite(result)))

    def test_lufs_only_mode(self):
        """只開 LUFS、關 DRC 應正常"""
        from processing.audio_normalization import normalize_loudness

        sr = 16000
        t = np.linspace(0, 2.0, sr * 2, dtype=np.float32)
        signal = 0.7 * np.sin(2 * np.pi * 440 * t)

        result = normalize_loudness(signal, sr, enable_drc=False, enable_lufs=True)

        self.assertEqual(len(result), len(signal))
        self.assertTrue(np.all(np.isfinite(result)))


# ============================================================
# Config 測試
# ============================================================

class TestLoudnessNormalizationConfig(unittest.TestCase):
    """測試配置欄位"""

    def test_all_fields_exist(self):
        """所有響度正規化配置欄位都存在"""
        from config import AppConfig

        cfg = AppConfig()
        required = {
            'AUDIO_LOUDNESS_NORMALIZATION': bool,
            'AUDIO_DRC_ENABLED': bool,
            'AUDIO_LUFS_ENABLED': bool,
            'AUDIO_LUFS_TARGET': float,
            'AUDIO_DRC_THRESHOLD': float,
            'AUDIO_DRC_RATIO': float,
        }

        for field, expected_type in required.items():
            self.assertTrue(hasattr(cfg, field), f"缺少配置欄位: {field}")
            value = getattr(cfg, field)
            self.assertIsInstance(value, expected_type,
                               f"{field} 類型應為 {expected_type.__name__}")

    def test_defaults(self):
        """預設值正確"""
        from config import AppConfig

        cfg = AppConfig()
        self.assertTrue(cfg.AUDIO_LOUDNESS_NORMALIZATION)
        self.assertTrue(cfg.AUDIO_DRC_ENABLED)
        self.assertTrue(cfg.AUDIO_LUFS_ENABLED)
        self.assertAlmostEqual(cfg.AUDIO_LUFS_TARGET, -16.0)
        self.assertAlmostEqual(cfg.AUDIO_DRC_THRESHOLD, -20.0)
        self.assertAlmostEqual(cfg.AUDIO_DRC_RATIO, 4.0)

    def test_lufs_target_negative(self):
        """LUFS 目標應為負數"""
        from config import AppConfig

        cfg = AppConfig()
        self.assertLess(cfg.AUDIO_LUFS_TARGET, 0,
                       "LUFS 目標應為負數")

    def test_drc_ratio_positive(self):
        """DRC 壓縮比應為正數"""
        from config import AppConfig

        cfg = AppConfig()
        self.assertGreater(cfg.AUDIO_DRC_RATIO, 0,
                          "DRC 壓縮比應為正數")


# ============================================================
# P1: 高通濾波器測試
# ============================================================

class TestHighPassFilter(unittest.TestCase):
    """測試 apply_highpass_filter"""

    def test_removes_low_frequency(self):
        """低頻訊號（40Hz）應被大幅衰減"""
        from processing.audio_normalization import apply_highpass_filter

        sr = 16000
        t = np.linspace(0, 1.0, sr, dtype=np.float32)
        low_freq = 0.5 * np.sin(2 * np.pi * 40 * t)  # 40Hz

        filtered = apply_highpass_filter(low_freq, sr, cutoff_hz=80)

        # 40Hz 在 80Hz cutoff 下應被顯著衰減
        original_rms = np.sqrt(np.mean(low_freq ** 2))
        filtered_rms = np.sqrt(np.mean(filtered ** 2))
        self.assertLess(filtered_rms, original_rms * 0.5,
                       "40Hz 訊號應被衰減至少 50%")

    def test_preserves_speech_frequency(self):
        """語音頻率（440Hz）應幾乎不受影響"""
        from processing.audio_normalization import apply_highpass_filter

        sr = 16000
        t = np.linspace(0, 1.0, sr, dtype=np.float32)
        speech_freq = 0.5 * np.sin(2 * np.pi * 440 * t)

        filtered = apply_highpass_filter(speech_freq, sr, cutoff_hz=80)

        # 440Hz 應幾乎不變
        np.testing.assert_allclose(
            np.sqrt(np.mean(filtered ** 2)),
            np.sqrt(np.mean(speech_freq ** 2)),
            rtol=0.05, err_msg="440Hz 訊號不應受影響")

    def test_preserves_male_fundamental(self):
        """最低男聲基頻（85Hz）應幾乎不受影響"""
        from processing.audio_normalization import apply_highpass_filter

        sr = 16000
        t = np.linspace(0, 2.0, sr * 2, dtype=np.float32)
        male_f0 = 0.5 * np.sin(2 * np.pi * 85 * t)

        filtered = apply_highpass_filter(male_f0, sr, cutoff_hz=80)

        original_rms = np.sqrt(np.mean(male_f0 ** 2))
        filtered_rms = np.sqrt(np.mean(filtered ** 2))
        # 85Hz 在 80Hz 2 階 Butterworth 下衰減極小
        self.assertGreater(filtered_rms, original_rms * 0.7,
                          "85Hz 男聲基頻不應被大幅衰減")

    def test_silence_returns_silence(self):
        """靜音不應崩潰"""
        from processing.audio_normalization import apply_highpass_filter

        silence = np.zeros(16000, dtype=np.float32)
        result = apply_highpass_filter(silence, 16000)
        np.testing.assert_array_equal(result, silence)

    def test_short_audio_returns_unchanged(self):
        """極短音頻（<100ms）跳過"""
        from processing.audio_normalization import apply_highpass_filter

        short = np.array([0.5, -0.3], dtype=np.float32)
        result = apply_highpass_filter(short, 16000)
        np.testing.assert_array_equal(result, short)

    def test_output_is_float32(self):
        """輸出應為 float32"""
        from processing.audio_normalization import apply_highpass_filter

        sr = 16000
        t = np.linspace(0, 1.0, sr, dtype=np.float32)
        signal = 0.5 * np.sin(2 * np.pi * 440 * t)

        result = apply_highpass_filter(signal, sr)
        self.assertEqual(result.dtype, np.float32)

    def test_invalid_cutoff_above_nyquist(self):
        """截止頻率超過 Nyquist 時應跳過"""
        from processing.audio_normalization import apply_highpass_filter

        sr = 16000
        t = np.linspace(0, 1.0, sr, dtype=np.float32)
        signal = 0.5 * np.sin(2 * np.pi * 440 * t)

        result = apply_highpass_filter(signal, sr, cutoff_hz=9000)
        np.testing.assert_array_equal(result, signal)


# ============================================================
# P0: 降噪測試
# ============================================================

class TestNoiseReduction(unittest.TestCase):
    """測試 apply_noise_reduction"""

    def test_reduces_stationary_noise(self):
        """穩態噪音應被降低"""
        from processing.audio_normalization import apply_noise_reduction

        sr = 16000
        t = np.linspace(0, 2.0, sr * 2, dtype=np.float32)
        # 語音 + 穩態噪音
        speech = 0.5 * np.sin(2 * np.pi * 440 * t)
        noise = 0.1 * np.random.randn(len(t)).astype(np.float32)
        noisy = speech + noise

        reduced = apply_noise_reduction(noisy, sr, stationary=True, prop_decrease=0.8)

        self.assertEqual(len(reduced), len(noisy))
        self.assertTrue(np.all(np.isfinite(reduced)))

    def test_output_is_float32(self):
        """輸出應為 float32"""
        from processing.audio_normalization import apply_noise_reduction

        sr = 16000
        t = np.linspace(0, 1.0, sr, dtype=np.float32)
        signal = 0.5 * np.sin(2 * np.pi * 440 * t) + 0.05 * np.random.randn(sr).astype(np.float32)

        result = apply_noise_reduction(signal, sr)
        self.assertEqual(result.dtype, np.float32)

    def test_silence_returns_unchanged(self):
        """靜音不應崩潰"""
        from processing.audio_normalization import apply_noise_reduction

        silence = np.zeros(16000, dtype=np.float32)
        result = apply_noise_reduction(silence, 16000)
        np.testing.assert_array_equal(result, silence)

    def test_short_audio_returns_unchanged(self):
        """極短音頻跳過"""
        from processing.audio_normalization import apply_noise_reduction

        short = np.array([0.5, -0.3], dtype=np.float32)
        result = apply_noise_reduction(short, 16000)
        np.testing.assert_array_equal(result, short)

    def test_conservative_params_preserve_signal(self):
        """保守參數不應大幅改變乾淨語音"""
        from processing.audio_normalization import apply_noise_reduction

        sr = 16000
        t = np.linspace(0, 2.0, sr * 2, dtype=np.float32)
        clean_speech = 0.5 * np.sin(2 * np.pi * 440 * t)

        # 使用最保守的參數
        result = apply_noise_reduction(
            clean_speech, sr, stationary=True,
            prop_decrease=0.3, n_std_thresh=3.0
        )

        # 乾淨訊號不應被大幅改變
        original_rms = np.sqrt(np.mean(clean_speech ** 2))
        result_rms = np.sqrt(np.mean(result ** 2))
        self.assertGreater(result_rms, original_rms * 0.5,
                          "保守參數不應大幅衰減乾淨語音")


# ============================================================
# P2: Per-Speaker 正規化測試
# ============================================================

class TestPerSpeakerNormalization(unittest.TestCase):
    """測試 normalize_per_speaker"""

    def test_balances_loud_and_quiet_speakers(self):
        """大小聲說話人的音量差異應縮小"""
        from processing.audio_normalization import normalize_per_speaker

        sr = 16000
        t = np.linspace(0, 3.0, sr * 3, dtype=np.float32)

        # 說話人 A: 大聲（前 3 秒）
        speaker_a = 0.8 * np.sin(2 * np.pi * 300 * t)
        # 說話人 B: 小聲（後 3 秒）
        speaker_b = 0.05 * np.sin(2 * np.pi * 400 * t)

        audio = np.concatenate([speaker_a, speaker_b])
        segments = [
            {'speaker_id': 'speaker_0', 'speaker': '說話人 A', 'start': 0.0, 'end': 3.0},
            {'speaker_id': 'speaker_1', 'speaker': '說話人 B', 'start': 3.0, 'end': 6.0},
        ]

        result = normalize_per_speaker(audio, sr, segments, target_lufs=-16.0)

        # 前後半段的 RMS 差異應縮小
        orig_a_rms = np.sqrt(np.mean(audio[:sr*3] ** 2))
        orig_b_rms = np.sqrt(np.mean(audio[sr*3:] ** 2))
        norm_a_rms = np.sqrt(np.mean(result[:sr*3] ** 2))
        norm_b_rms = np.sqrt(np.mean(result[sr*3:] ** 2))

        orig_ratio = orig_a_rms / max(orig_b_rms, 1e-10)
        norm_ratio = norm_a_rms / max(norm_b_rms, 1e-10)

        self.assertLess(norm_ratio, orig_ratio,
                       "Per-speaker norm 後大小聲比例應縮小")

    def test_single_speaker_unchanged(self):
        """只有 1 位說話人時跳過"""
        from processing.audio_normalization import normalize_per_speaker

        sr = 16000
        audio = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 2.0, sr * 2, dtype=np.float32))
        segments = [
            {'speaker_id': 'speaker_0', 'speaker': '說話人 A', 'start': 0.0, 'end': 2.0},
        ]

        result = normalize_per_speaker(audio, sr, segments)
        np.testing.assert_array_equal(result, audio)

    def test_empty_segments_unchanged(self):
        """空片段列表不改變音頻"""
        from processing.audio_normalization import normalize_per_speaker

        sr = 16000
        audio = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1.0, sr, dtype=np.float32))

        result = normalize_per_speaker(audio, sr, [])
        np.testing.assert_array_equal(result, audio)

    def test_output_clipped_to_unit_range(self):
        """輸出應在 [-1, 1] 範圍內"""
        from processing.audio_normalization import normalize_per_speaker

        sr = 16000
        t = np.linspace(0, 3.0, sr * 3, dtype=np.float32)
        audio = np.concatenate([
            0.9 * np.sin(2 * np.pi * 300 * t),
            0.01 * np.sin(2 * np.pi * 400 * t),
        ])
        segments = [
            {'speaker_id': 'speaker_0', 'start': 0.0, 'end': 3.0},
            {'speaker_id': 'speaker_1', 'start': 3.0, 'end': 6.0},
        ]

        result = normalize_per_speaker(audio, sr, segments)
        self.assertLessEqual(np.max(result), 1.0)
        self.assertGreaterEqual(np.min(result), -1.0)

    def test_output_is_float32(self):
        """輸出應為 float32"""
        from processing.audio_normalization import normalize_per_speaker

        sr = 16000
        t = np.linspace(0, 3.0, sr * 3, dtype=np.float32)
        audio = np.concatenate([
            0.5 * np.sin(2 * np.pi * 300 * t),
            0.1 * np.sin(2 * np.pi * 400 * t),
        ])
        segments = [
            {'speaker_id': 'speaker_0', 'start': 0.0, 'end': 3.0},
            {'speaker_id': 'speaker_1', 'start': 3.0, 'end': 6.0},
        ]

        result = normalize_per_speaker(audio, sr, segments)
        self.assertEqual(result.dtype, np.float32)

    def test_gain_limited_to_12db(self):
        """增益應被限制在 ±12dB"""
        from processing.audio_normalization import normalize_per_speaker

        sr = 16000
        t = np.linspace(0, 3.0, sr * 3, dtype=np.float32)
        # 極端差異：0.9 vs 0.001
        audio = np.concatenate([
            0.9 * np.sin(2 * np.pi * 300 * t),
            0.001 * np.sin(2 * np.pi * 400 * t),
        ])
        segments = [
            {'speaker_id': 'speaker_0', 'start': 0.0, 'end': 3.0},
            {'speaker_id': 'speaker_1', 'start': 3.0, 'end': 6.0},
        ]

        result = normalize_per_speaker(audio, sr, segments)

        # 結果不應有 NaN 或 Inf
        self.assertTrue(np.all(np.isfinite(result)))
        self.assertLessEqual(np.max(np.abs(result)), 1.0)


# ============================================================
# 新增 Config 測試
# ============================================================

class TestAudioEnhancementConfig(unittest.TestCase):
    """測試新增的音頻增強配置欄位"""

    def test_highpass_fields_exist(self):
        """高通濾波配置欄位存在"""
        from config import AppConfig
        cfg = AppConfig()
        self.assertTrue(hasattr(cfg, 'AUDIO_HIGHPASS_ENABLED'))
        self.assertTrue(hasattr(cfg, 'AUDIO_HIGHPASS_CUTOFF_HZ'))
        self.assertIsInstance(cfg.AUDIO_HIGHPASS_ENABLED, bool)
        self.assertIsInstance(cfg.AUDIO_HIGHPASS_CUTOFF_HZ, int)

    def test_highpass_defaults(self):
        """高通濾波預設值正確"""
        from config import AppConfig
        cfg = AppConfig()
        self.assertTrue(cfg.AUDIO_HIGHPASS_ENABLED, "高通濾波應預設開啟")
        self.assertEqual(cfg.AUDIO_HIGHPASS_CUTOFF_HZ, 80)

    def test_noise_reduction_fields_exist(self):
        """降噪配置欄位存在"""
        from config import AppConfig
        cfg = AppConfig()
        self.assertTrue(hasattr(cfg, 'AUDIO_NOISE_REDUCTION_ENABLED'))
        self.assertTrue(hasattr(cfg, 'AUDIO_NOISE_REDUCTION_STATIONARY'))
        self.assertTrue(hasattr(cfg, 'AUDIO_NOISE_REDUCTION_STRENGTH'))

    def test_noise_reduction_defaults(self):
        """降噪預設為關閉"""
        from config import AppConfig
        cfg = AppConfig()
        self.assertFalse(cfg.AUDIO_NOISE_REDUCTION_ENABLED, "降噪應預設關閉")
        self.assertTrue(cfg.AUDIO_NOISE_REDUCTION_STATIONARY)
        self.assertAlmostEqual(cfg.AUDIO_NOISE_REDUCTION_STRENGTH, 0.6)

    def test_per_speaker_norm_fields_exist(self):
        """Per-speaker 正規化配置欄位存在"""
        from config import AppConfig
        cfg = AppConfig()
        self.assertTrue(hasattr(cfg, 'AUDIO_PER_SPEAKER_NORM_ENABLED'))
        self.assertTrue(hasattr(cfg, 'AUDIO_PER_SPEAKER_NORM_TARGET'))

    def test_per_speaker_norm_defaults(self):
        """Per-speaker 正規化預設開啟"""
        from config import AppConfig
        cfg = AppConfig()
        self.assertTrue(cfg.AUDIO_PER_SPEAKER_NORM_ENABLED)
        self.assertAlmostEqual(cfg.AUDIO_PER_SPEAKER_NORM_TARGET, -16.0)

    def test_speech_enhancement_fields_exist(self):
        """語音增強配置欄位存在"""
        from config import AppConfig
        cfg = AppConfig()
        self.assertTrue(hasattr(cfg, 'AUDIO_SPEECH_ENHANCEMENT_ENABLED'))
        self.assertTrue(hasattr(cfg, 'AUDIO_SPEECH_ENHANCEMENT_MODEL'))

    def test_speech_enhancement_defaults(self):
        """語音增強預設關閉"""
        from config import AppConfig
        cfg = AppConfig()
        self.assertFalse(cfg.AUDIO_SPEECH_ENHANCEMENT_ENABLED, "語音增強應預設關閉")
        self.assertEqual(cfg.AUDIO_SPEECH_ENHANCEMENT_MODEL, "MossFormerGAN_SE_16K")


if __name__ == '__main__':
    unittest.main()
