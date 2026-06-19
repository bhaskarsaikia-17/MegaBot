"""Access control: gate the bot to the configured allow-list of users.

This bot can read and modify a Mega account, so by default it must only respond
to the Telegram user IDs listed in ``ALLOWED_USERS``. If that list is empty the
bot is open to everyone, which is logged loudly as a warning at startup.
"""

from __future__ import annotations

import functools
import logging
from typing import Awaitable, Callable

from pyrogram import filters
from pyrogram.types import Message

from config import config

log = logging.getLogger("megabot.auth")

# A Pyrogram filter that matches only allowed users. Used when registering
# handlers so unauthorised messages are ignored at the framework level.
allowed_filter = filters.create(
    lambda _flt, _client, message: (
        message.from_user is not None and config.is_allowed(message.from_user.id)
    )
)


def require_auth(
    handler: Callable[..., Awaitable[None]],
) -> Callable[..., Awaitable[None]]:
    """Decorator that rejects messages from users not in the allow-list.

    This is defence-in-depth on top of :data:`allowed_filter`: even if a handler
    is registered without the filter, it still cannot run for an unauthorised
    user.
    """

    @functools.wraps(handler)
    async def wrapper(client, message: Message, *args, **kwargs):
        user = message.from_user
        if user is None or not config.is_allowed(user.id):
            uid = user.id if user else "unknown"
            log.warning("Rejected unauthorised user: %s", uid)
            try:
                await message.reply_text(
                    "\u26d4 You are not authorised to use this bot.\n"
                    f"Your Telegram ID is `{uid}`."
                )
            except Exception:
                pass
            return
        return await handler(client, message, *args, **kwargs)

    return wrapper
