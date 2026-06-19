"""MegaBot entrypoint.

Run with:  python main.py
"""

from __future__ import annotations

import asyncio
import logging

from pyrogram import idle

from config import config
from megabot.bot import app, mega
from megabot.handlers import register_all
from megabot.mega_client import MegaError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("megabot.main")


async def _startup() -> None:
    """Verify MegaCMD, optionally auto-login, and report access policy."""
    try:
        version = await mega.ensure_available()
        log.info("MegaCMD detected: %s", version.splitlines()[0] if version else "unknown")
    except MegaError as exc:
        log.warning("MegaCMD not ready: %s", exc)

    if config.public_access:
        log.warning(
            "ALLOWED_USERS is empty: the bot is OPEN TO EVERYONE. Set "
            "ALLOWED_USERS in your .env to restrict access to your Mega account."
        )
    else:
        log.info("Access restricted to %d user(s).", len(config.allowed_users))

    if config.auto_login:
        log.info("Attempting auto-login for %s ...", config.mega_email)
        try:
            await mega.login(config.mega_email, config.mega_password)  # type: ignore[arg-type]
            log.info("Auto-login successful.")
        except MegaError as exc:
            log.warning("Auto-login failed: %s", exc)


async def main() -> None:
    register_all(app)
    await app.start()
    await _startup()
    me = await app.get_me()
    log.info("Bot started as @%s. Press Ctrl+C to stop.", me.username)
    await idle()
    await app.stop()
    log.info("Bot stopped.")


if __name__ == "__main__":
    # The Pyrogram Client is created at import time and binds to the event loop
    # that exists then (Client.__init__ calls asyncio.get_event_loop()). We must
    # run main() on that SAME loop, otherwise session objects raise
    # "attached to a different loop" on Python 3.12.
    #
    # asyncio.run() would create a *new* loop (the bug we hit), and this
    # Kurigram build's app.run() takes no coroutine argument — so we drive the
    # client's own loop directly.
    loop = getattr(app, "loop", None) or asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
