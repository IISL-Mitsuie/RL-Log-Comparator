"""
画像差分計算モジュール (Qt 非依存)
"""

import numpy as np


def compute_abs_diff(a: np.ndarray, b: np.ndarray, gain: float = 1.0) -> np.ndarray:
    """2つの RGBA 画像配列の差の絶対値を計算し、gain を乗じてクリップした RGBA 配列を返す。

    Args:
        a: 形状 (H, W, 4)、dtype uint8 の RGBA 画像
        b: 形状 (H, W, 4)、dtype uint8 の RGBA 画像
        gain: 差分の増幅率 (>= 0.0)

    Returns:
        形状 (H, W, 4)、dtype uint8 の差分 RGBA 画像 (アルファは 255)

    Raises:
        ValueError: 配列の形状やチャンネル数が不一致の場合
    """
    _validate_inputs(a, b)
    if gain < 0:
        raise ValueError(f"gain must be non-negative, got {gain}")

    # RGB 各チャンネルの差の絶対値を計算
    # 符号なし8ビット整数のオーバーフローを防ぐため int32 にキャスト
    diff_rgb = np.abs(a[..., :3].astype(np.int32) - b[..., :3].astype(np.int32))
    diff_scaled = np.clip(diff_rgb * gain, 0, 255).astype(np.uint8)

    # 出力用 RGBA 配列を作成 (アルファチャンネルは 255)
    h, w = a.shape[:2]
    result = np.empty((h, w, 4), dtype=np.uint8)
    result[..., :3] = diff_scaled
    result[..., 3] = 255
    return result


def diff_ratio(a: np.ndarray, b: np.ndarray, threshold: int = 16) -> float:
    """2つの RGBA 画像間で、いずれかの RGB チャンネルの差が threshold を超える画素の割合を計算する。

    Args:
        a: 形状 (H, W, 4)、dtype uint8 の RGBA 画像
        b: 形状 (H, W, 4)、dtype uint8 の RGBA 画像
        threshold: 差分とみなす閾値 (0〜255)

    Returns:
        差分画素の割合 (0.0 〜 1.0)

    Raises:
        ValueError: 配列の形状やチャンネル数が不一致の場合
    """
    _validate_inputs(a, b)

    h, w = a.shape[:2]
    total_pixels = h * w
    if total_pixels == 0:
        return 0.0

    diff_rgb = np.abs(a[..., :3].astype(np.int32) - b[..., :3].astype(np.int32))
    has_diff = np.any(diff_rgb > threshold, axis=-1)
    diff_count = int(np.count_nonzero(has_diff))
    return float(diff_count / total_pixels)


def _validate_inputs(a: np.ndarray, b: np.ndarray) -> None:
    if not isinstance(a, np.ndarray) or not isinstance(b, np.ndarray):
        raise ValueError("Inputs must be numpy ndarrays")
    if a.shape != b.shape:
        raise ValueError(f"Shape mismatch: {a.shape} vs {b.shape}")
    if a.ndim != 3 or a.shape[2] != 4:
        raise ValueError(f"Expected RGBA shape (H, W, 4), got {a.shape}")
