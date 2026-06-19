"""Throttled progress callback for Pyrogram up/downloads."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .format import human_size, progress_bar

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyrogram.types import Message


class ProgressReporter:
    """Edits a Telegram status message to reflect transfer progress.

    Pyrogram calls the instance (``__call__``) with ``(current, total)`` for
    every chunk. Edits are throttled to avoid hitting Telegram's flood limits.
    """

    def __init__(self, status_message: "Message", action: str, *, min_interval: float = 4.0) -> None:
        self._message = status_message
        self._action = action
        self._min_interval = min_interval
        self._start = time.monotonic()
        self._last_edit = 0.0
        self._last_text = ""

    async def __call__(self, current: int, total: int) -> None:
        now = time.monotonic()
        is_final = total and current >= total
        if not is_final and (now - self._last_edit) < self._min_interval:
            return

        elapsed = max(now - self._start, 1e-6)
        speed = current / elapsed
        eta = (total - current) / speed if speed > 0 and total else 0

        text = (
            f"**{self._action}**\n"
            f"`{progress_bar(current, total)}`\n"
            f"{human_size(current)} / {human_size(total)}\n"
            f"Speed: {human_size(speed)}/s"
        )
        if eta:
            from .format import human_duration

            text += f" · ETA: {human_duration(eta)}"

        if text == self._last_text:
            return
        self._last_text = text
        self._last_edit = now
        try:
            await self._message.edit_text(text)
        except Exception:
            # Never let a status-edit failure (flood wait, message deleted,
            # identical content) abort the actual transfer.
            pass
