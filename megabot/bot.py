"""Pyrogram client setup and shared singletons.

Exposes:
* ``app``  – the configured Pyrogram :class:`~pyrogram.Client`.
* ``mega`` – the shared :class:`~megabot.mega_client.MegaClient` instance used
  by every handler.
"""

from __future__ import annotations

import logging

from pyrogram import Client

from config import config

from .mega_client import MegaClient

log = logging.getLogger("megabot")

# Single bot client. ``name`` controls the on-disk session file. ``in_memory``
# keeps a bot session in RAM so we don't leave a *.session file lying around;
# bots authenticate purely with the token so persistence isn't required.
app: Client = Client(
    name="megabot",
    api_id=config.api_id,
    api_hash=config.api_hash,
    bot_token=config.bot_token,
    in_memory=True,
)

# Shared Mega backend. MegaCMD keeps the session server-side, so one instance is
# all the handlers need.
mega: MegaClient = MegaClient(megacmd_path=config.megacmd_path)
