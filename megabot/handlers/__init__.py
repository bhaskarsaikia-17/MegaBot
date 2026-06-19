"""Handler registration.

Each submodule exposes a ``register(app)`` function. :func:`register_all` wires
them all onto the Pyrogram client. Importing handlers lazily here keeps the
import graph simple and avoids circular imports with :mod:`megabot.bot`.
"""

from __future__ import annotations

from pyrogram import Client

from . import account, basic, info, transfer


def register_all(app: Client) -> None:
    basic.register(app)
    account.register(app)
    transfer.register(app)
    info.register(app)
