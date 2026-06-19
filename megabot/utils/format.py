"""Human-readable formatting helpers."""

from __future__ import annotations

_UNITS = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]


def human_size(num_bytes: float) -> str:
    """Format a byte count as a human-readable string (binary units)."""
    size = float(num_bytes)
    for unit in _UNITS:
        if abs(size) < 1024.0 or unit == _UNITS[-1]:
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024.0
    return f"{size:.2f} {_UNITS[-1]}"  # pragma: no cover - unreachable


def human_duration(seconds: float) -> str:
    """Format a duration in seconds as e.g. ``1h 02m 03s``."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def progress_bar(current: float, total: float, width: int = 16) -> str:
    """Render a textual progress bar like ``[#####-----] 50.0%``."""
    if total <= 0:
        return "[" + "-" * width + "]   0.0%"
    fraction = max(0.0, min(1.0, current / total))
    filled = int(fraction * width)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {fraction * 100:5.1f}%"
