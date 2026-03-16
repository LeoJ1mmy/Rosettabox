"""
音頻響度正規化與增強模組

提供完整的音頻前處理管線：
- High-Pass Filter: 移除低頻隆隆聲（冷氣、交通、電源哼聲）
- Noise Reduction: 頻譜閘門降噪（穩態背景噪音）
- Dynamic Range Compression (DRC): 壓縮動態範圍
- LUFS 正規化: 統一響度
- Per-Speaker Normalization: 每位說話人獨立音量校正

Pipeline:
  Peak Norm → High-Pass → Noise Reduction → DRC → LUFS → Silence Trim
  (Diarization 後) → Per-Speaker Norm
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)


def normalize_loudness(
    audio: np.ndarray,
    sample_rate: int = 16000,
    enable_drc: bool = True,
    enable_lufs: bool = True,
    drc_threshold_db: float = -20.0,
    drc_ratio: float = 4.0,
    drc_attack_sec: float = 0.01,
    drc_release_sec: float = 0.1,
    drc_knee_db: float = 6.0,
    drc_rms_window_sec: float = 0.05,
    lufs_target: float = -16.0,
) -> np.ndarray:
    """套用響度正規化（DRC + LUFS）

    Args:
        audio: mono float32 音頻陣列（預期已做 peak normalization）
        sample_rate: 取樣率（應為 16000）
        enable_drc: 是否套用動態範圍壓縮
        enable_lufs: 是否套用 LUFS 正規化
        drc_threshold_db: DRC 閾值 (dBFS)
        drc_ratio: 壓縮比（4.0 = 4:1）
        drc_attack_sec: Attack 時間（秒）
        drc_release_sec: Release 時間（秒）
        drc_knee_db: Soft knee 寬度 (dB)
        drc_rms_window_sec: RMS envelope 窗口（秒）
        lufs_target: 目標 LUFS 值

    Returns:
        正規化後的音頻陣列 (float32, clipped to [-1, 1])
    """
    # 太短的音頻跳過
    if len(audio) < sample_rate * 0.1:
        logger.warning("音頻太短 (<100ms)，跳過響度正規化")
        return audio

    # 全靜音跳過
    if np.max(np.abs(audio)) < 1e-6:
        logger.warning("音頻為靜音，跳過響度正規化")
        return audio

    if enable_drc:
        original_rms = np.sqrt(np.mean(audio ** 2))
        audio = apply_dynamic_range_compression(
            audio, sample_rate,
            threshold_db=drc_threshold_db,
            ratio=drc_ratio,
            attack_sec=drc_attack_sec,
            release_sec=drc_release_sec,
            knee_db=drc_knee_db,
            rms_window_sec=drc_rms_window_sec,
        )
        new_rms = np.sqrt(np.mean(audio ** 2))
        logger.info(f"🔊 DRC 完成: RMS {original_rms:.4f} → {new_rms:.4f}")

    if enable_lufs:
        audio = apply_lufs_normalization(audio, sample_rate, target_lufs=lufs_target)

    # 防止 clipping
    audio = np.clip(audio, -1.0, 1.0).astype(np.float32)

    return audio


def apply_dynamic_range_compression(
    audio: np.ndarray,
    sample_rate: int,
    threshold_db: float = -20.0,
    ratio: float = 4.0,
    attack_sec: float = 0.01,
    release_sec: float = 0.1,
    knee_db: float = 6.0,
    rms_window_sec: float = 0.05,
) -> np.ndarray:
    """Feed-forward 動態範圍壓縮器（soft knee）

    使用 RMS envelope 偵測音量，套用 soft-knee 壓縮曲線，
    再以 scipy.signal.lfilter 向量化平滑 gain curve。

    Args:
        audio: 輸入音頻
        sample_rate: 取樣率
        threshold_db: 壓縮閾值 (dBFS)
        ratio: 壓縮比
        attack_sec: Attack 時間
        release_sec: Release 時間
        knee_db: Soft knee 寬度
        rms_window_sec: RMS 偵測窗口

    Returns:
        壓縮後的音頻
    """
    from scipy.signal import lfilter

    # 全靜音保護
    if np.max(np.abs(audio)) < 1e-10:
        return audio

    # 1. 計算 RMS envelope（窗口不超過音頻長度）
    window_samples = max(int(sample_rate * rms_window_sec), 1)
    window_samples = min(window_samples, len(audio))
    window = np.ones(window_samples) / window_samples
    rms_envelope = np.sqrt(np.convolve(audio ** 2, window, mode='same'))
    rms_envelope = np.maximum(rms_envelope, 1e-10)

    # 2. 轉 dB
    envelope_db = 20.0 * np.log10(rms_envelope)

    # 3. Soft-knee 壓縮曲線
    half_knee = knee_db / 2.0
    gain_db = np.zeros_like(envelope_db)

    # 低於 knee 下緣：無壓縮
    below = envelope_db < (threshold_db - half_knee)
    # gain_db[below] = 0.0 (already zero)

    # 在 knee 範圍內：漸進壓縮
    in_knee = (~below) & (envelope_db < (threshold_db + half_knee))
    if np.any(in_knee):
        x = envelope_db[in_knee] - threshold_db + half_knee
        gain_db[in_knee] = -((1.0 - 1.0 / ratio) * x ** 2) / (2.0 * knee_db)

    # 高於 knee 上緣：完全壓縮
    above = envelope_db >= (threshold_db + half_knee)
    gain_db[above] = -(1.0 - 1.0 / ratio) * (envelope_db[above] - threshold_db)

    # 4. 用 lfilter 向量化平滑 gain（attack/release 近似）
    # 使用 release 係數作為主要平滑，這是語音壓縮的常見近似
    release_coeff = np.exp(-1.0 / (sample_rate * release_sec)) if release_sec > 0 else 0.0
    attack_coeff = np.exp(-1.0 / (sample_rate * attack_sec)) if attack_sec > 0 else 0.0

    # 雙通道平滑：attack envelope (快) + release envelope (慢)
    b_attack = np.array([1.0 - attack_coeff])
    a_attack = np.array([1.0, -attack_coeff])
    attack_env = lfilter(b_attack, a_attack, gain_db)

    b_release = np.array([1.0 - release_coeff])
    a_release = np.array([1.0, -release_coeff])
    release_env = lfilter(b_release, a_release, gain_db)

    # 取兩者中較小值（壓縮更多的那個）
    smoothed_gain_db = np.minimum(attack_env, release_env)

    # 5. 套用 gain
    gain_linear = 10.0 ** (smoothed_gain_db / 20.0)
    compressed = audio * gain_linear

    # 6. Auto makeup gain：恢復原始 RMS
    compressed_rms = np.sqrt(np.mean(compressed ** 2))
    original_rms = np.sqrt(np.mean(audio ** 2))
    if compressed_rms > 1e-10:
        makeup = original_rms / compressed_rms
        compressed = compressed * makeup

    return compressed


def apply_lufs_normalization(
    audio: np.ndarray,
    sample_rate: int,
    target_lufs: float = -16.0,
) -> np.ndarray:
    """使用 pyloudnorm 將音頻正規化到目標 LUFS

    Args:
        audio: 輸入音頻
        sample_rate: 取樣率
        target_lufs: 目標 LUFS 值（EBU R128 = -16.0）

    Returns:
        LUFS 正規化後的音頻
    """
    try:
        import pyloudnorm as pyln
    except ImportError:
        logger.warning("pyloudnorm 未安裝，跳過 LUFS 正規化 (pip install pyloudnorm)")
        return audio

    meter = pyln.Meter(sample_rate)
    current_loudness = meter.integrated_loudness(audio)

    # 靜音或極低音量返回 -inf
    if not np.isfinite(current_loudness):
        logger.warning(f"LUFS 測量值為 {current_loudness}，跳過正規化")
        return audio

    # 已在目標附近 (±0.5 dB)
    if abs(current_loudness - target_lufs) < 0.5:
        logger.info(f"🔊 LUFS 已接近目標: {current_loudness:.1f} LUFS (目標: {target_lufs:.1f})")
        return audio

    logger.info(f"🔊 LUFS 正規化: {current_loudness:.1f} → {target_lufs:.1f} LUFS")
    normalized = pyln.normalize.loudness(audio, current_loudness, target_lufs)

    return normalized


def apply_highpass_filter(
    audio: np.ndarray,
    sample_rate: int = 16000,
    cutoff_hz: int = 80,
    order: int = 2,
) -> np.ndarray:
    """Butterworth 高通濾波器，移除低頻隆隆聲

    移除 cutoff_hz 以下的低頻能量（冷氣、交通、電源哼聲、麥克風碰觸），
    這些頻率不含語音資訊但會污染 mel spectrogram。

    Butterworth 2 階在 cutoff 處僅 -3dB，斜率平緩，
    對最低男聲基頻（~85Hz）幾乎無影響。

    Args:
        audio: 輸入音頻 (float32, mono)
        sample_rate: 取樣率
        cutoff_hz: 截止頻率 (Hz)，預設 80Hz
        order: 濾波器階數，預設 2（12dB/octave 斜率）

    Returns:
        濾波後的音頻 (float32)
    """
    from scipy.signal import butter, sosfilt

    if len(audio) < sample_rate * 0.1:
        return audio

    if np.max(np.abs(audio)) < 1e-6:
        return audio

    # Nyquist 頻率保護
    nyquist = sample_rate / 2.0
    if cutoff_hz >= nyquist:
        logger.warning(f"高通截止頻率 {cutoff_hz}Hz >= Nyquist {nyquist}Hz，跳過濾波")
        return audio

    sos = butter(order, cutoff_hz, btype='highpass', fs=sample_rate, output='sos')
    filtered = sosfilt(sos, audio).astype(np.float32)

    logger.info(f"🔊 高通濾波完成: cutoff={cutoff_hz}Hz, order={order}")
    return filtered


def apply_noise_reduction(
    audio: np.ndarray,
    sample_rate: int = 16000,
    stationary: bool = True,
    prop_decrease: float = 0.6,
    n_std_thresh: float = 2.5,
) -> np.ndarray:
    """頻譜閘門降噪（noisereduce）

    使用保守參數移除穩態背景噪音（冷氣、風扇、電流哼聲）。

    注意：2025 研究《When De-noising Hurts》顯示過度降噪會傷害 ASR，
    因此預設使用保守參數（prop_decrease=0.6, n_std_thresh=2.5）。

    Args:
        audio: 輸入音頻 (float32, mono)
        sample_rate: 取樣率
        stationary: True=只處理穩態噪音（更安全），False=也處理非穩態噪音
        prop_decrease: 降噪強度 (0-1)，越低越保守。0.6 = 移除 60% 噪音
        n_std_thresh: 噪音閾值（標準差倍數），越高越保守

    Returns:
        降噪後的音頻 (float32)
    """
    try:
        import noisereduce as nr
    except ImportError:
        logger.warning("noisereduce 未安裝，跳過降噪 (pip install noisereduce)")
        return audio

    if len(audio) < sample_rate * 0.1:
        return audio

    if np.max(np.abs(audio)) < 1e-6:
        return audio

    original_rms = np.sqrt(np.mean(audio ** 2))

    reduced = nr.reduce_noise(
        y=audio,
        sr=sample_rate,
        stationary=stationary,
        prop_decrease=prop_decrease,
        n_std_thresh_stationary=n_std_thresh,
    ).astype(np.float32)

    new_rms = np.sqrt(np.mean(reduced ** 2))
    logger.info(f"🔊 降噪完成: stationary={stationary}, strength={prop_decrease}, "
                f"RMS {original_rms:.4f} → {new_rms:.4f}")

    return reduced


def normalize_per_speaker(
    audio: np.ndarray,
    sample_rate: int,
    diarization_segments: list,
    target_lufs: float = -16.0,
) -> np.ndarray:
    """對每位說話人獨立正規化音量

    收集每位說話人的所有片段，計算整體 LUFS（或 RMS），
    然後對該說話人的所有片段套用統一 gain，使各說話人響度一致。

    長片段（≥3s 串接總長）使用 LUFS 測量，短片段使用 RMS。

    Args:
        audio: 完整音頻 (float32, mono)
        sample_rate: 取樣率
        diarization_segments: 說話人分離片段列表，每個含 speaker_id, start, end
        target_lufs: 目標 LUFS 值

    Returns:
        正規化後的完整音頻 (float32, clipped to [-1, 1])
    """
    if not diarization_segments:
        return audio

    # 按說話人分組
    from collections import defaultdict
    speaker_segments = defaultdict(list)
    for seg in diarization_segments:
        speaker_id = seg.get('speaker_id', seg.get('speaker', 'unknown'))
        speaker_segments[speaker_id].append(seg)

    if len(speaker_segments) < 2:
        logger.info("🔊 Per-speaker norm: 只有 1 位說話人，跳過")
        return audio

    result = audio.copy()
    min_lufs_duration = 3.0  # LUFS 最小可靠測量時長（秒）

    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sample_rate)
        has_pyloudnorm = True
    except ImportError:
        has_pyloudnorm = False

    gains_applied = {}

    for speaker_id, segments in speaker_segments.items():
        # 串接該說話人的所有片段
        speaker_chunks = []
        for seg in segments:
            start_sample = int(seg['start'] * sample_rate)
            end_sample = int(seg['end'] * sample_rate)
            start_sample = max(0, start_sample)
            end_sample = min(len(audio), end_sample)
            if end_sample > start_sample:
                speaker_chunks.append(audio[start_sample:end_sample])

        if not speaker_chunks:
            continue

        speaker_audio = np.concatenate(speaker_chunks)
        total_duration = len(speaker_audio) / sample_rate

        if np.max(np.abs(speaker_audio)) < 1e-6:
            continue

        # 根據總時長選擇 LUFS 或 RMS
        gain_db = 0.0
        if has_pyloudnorm and total_duration >= min_lufs_duration:
            current_lufs = meter.integrated_loudness(speaker_audio)
            if np.isfinite(current_lufs):
                gain_db = target_lufs - current_lufs
                method = "LUFS"
            else:
                # LUFS 測量失敗，fallback 到 RMS
                gain_db = _compute_rms_gain(speaker_audio, target_lufs)
                method = "RMS(fallback)"
        else:
            gain_db = _compute_rms_gain(speaker_audio, target_lufs)
            method = "RMS"

        # 限制最大增益調整範圍（±12dB）避免極端值
        gain_db = np.clip(gain_db, -12.0, 12.0)
        gain_linear = 10.0 ** (gain_db / 20.0)

        if abs(gain_db) < 0.5:
            logger.debug(f"🔊 Per-speaker [{speaker_id}]: 已接近目標，跳過 (gain={gain_db:+.1f}dB)")
            continue

        # 套用 gain 到該說話人的所有片段
        for seg in segments:
            start_sample = int(seg['start'] * sample_rate)
            end_sample = int(seg['end'] * sample_rate)
            start_sample = max(0, start_sample)
            end_sample = min(len(result), end_sample)
            if end_sample > start_sample:
                result[start_sample:end_sample] = result[start_sample:end_sample] * gain_linear

        gains_applied[speaker_id] = (gain_db, method)
        logger.info(f"🔊 Per-speaker [{speaker_id}]: {method} gain={gain_db:+.1f}dB "
                    f"(duration={total_duration:.1f}s, segments={len(segments)})")

    if gains_applied:
        logger.info(f"🔊 Per-speaker norm 完成: {len(gains_applied)} 位說話人已調整")

    return np.clip(result, -1.0, 1.0).astype(np.float32)


def _compute_rms_gain(audio: np.ndarray, target_lufs: float) -> float:
    """用 RMS 估算需要的增益（dB），用於 LUFS 不可靠的短片段

    將 target_lufs 近似轉換為 RMS 目標，計算所需增益。
    LUFS ≈ RMS_dBFS - 0.691（粗略近似，對語音足夠準確）

    Args:
        audio: 音頻片段
        target_lufs: 目標 LUFS

    Returns:
        需要的增益 (dB)
    """
    rms = np.sqrt(np.mean(audio ** 2))
    if rms < 1e-10:
        return 0.0
    current_rms_db = 20.0 * np.log10(rms)
    target_rms_db = target_lufs + 0.691  # LUFS ≈ RMS_dBFS - 0.691
    return target_rms_db - current_rms_db
