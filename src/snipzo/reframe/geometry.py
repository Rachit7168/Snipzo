"""9:16 crop-window math."""

from __future__ import annotations

TARGET_ASPECT = 9 / 16


def even(value: int) -> int:
    """Round down to the nearest even integer (required for yuv420p)."""
    return int(value) - (int(value) % 2)


def crop_size(
    width: int, height: int, aspect: float = TARGET_ASPECT
) -> tuple[int, int]:
    """Return an even 9:16 crop size that fits inside the source frame."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    source_aspect = width / height
    if source_aspect > aspect:
        crop_h = even(height)
        crop_w = even(int(round(crop_h * aspect)))
    else:
        crop_w = even(width)
        crop_h = even(int(round(crop_w / aspect)))
    crop_w = max(2, min(crop_w, even(width)))
    crop_h = max(2, min(crop_h, even(height)))
    return crop_w, crop_h


def clamp_origin(
    x: float, y: float, width: int, height: int, crop_w: int, crop_h: int
) -> tuple[float, float]:
    """Keep the crop window fully inside the source frame."""
    max_x = max(0.0, float(width - crop_w))
    max_y = max(0.0, float(height - crop_h))
    return min(max(x, 0.0), max_x), min(max(y, 0.0), max_y)


def center_origin(
    width: int, height: int, crop_w: int, crop_h: int
) -> tuple[float, float]:
    """Return the top-left of a centered crop window."""
    return clamp_origin(
        (width - crop_w) / 2.0, (height - crop_h) / 2.0, width, height, crop_w, crop_h
    )


def origin_from_point(
    cx: float,
    cy: float,
    width: int,
    height: int,
    crop_w: int,
    crop_h: int,
) -> tuple[float, float]:
    """Place the crop so that (cx, cy) is as close to the center as possible."""
    return clamp_origin(
        cx - crop_w / 2.0, cy - crop_h / 2.0, width, height, crop_w, crop_h
    )


def smooth_series(values: list[float], alpha: float = 0.3) -> list[float]:
    """Exponential moving average to reduce crop jitter."""
    if not values:
        return []
    alpha = min(1.0, max(0.0, alpha))
    smoothed = [values[0]]
    for value in values[1:]:
        smoothed.append(alpha * value + (1.0 - alpha) * smoothed[-1])
    return smoothed
