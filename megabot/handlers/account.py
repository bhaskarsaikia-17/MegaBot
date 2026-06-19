"""Account handlers: /login, /logout, /me, /storage, /ls."""

from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from ..auth import allowed_filter, require_auth
from ..bot import mega
from ..mega_client import MegaError


def _code_block(text: str, limit: int = 3800) -> str:
    """Wrap output in a fenced block, truncating to stay under Telegram limits."""
    text = text or "(no output)"
    if len(text) > limit:
        text = text[:limit] + "\n... (truncated)"
    return f"```\n{text}\n```"


@require_auth
async def login_cmd(client: Client, message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.reply_text(
            "Usage: `/login <email> <password>`\n\n"
            "\u26a0\ufe0f For your security, delete the message containing your "
            "password after logging in."
        )
        return
    email, password = parts[1], parts[2]
    status = await message.reply_text("\U0001f510 Logging in...")
    try:
        output = await mega.login(email, password)
    except MegaError as exc:
        await status.edit_text(f"\u274c Login failed:\n{_code_block(str(exc))}")
        return
    await status.edit_text(f"\u2705 {output.splitlines()[-1] if output else 'Logged in.'}")


@require_auth
async def logout_cmd(client: Client, message: Message) -> None:
    output = await mega.logout()
    await message.reply_text(f"\U0001f44b {output.splitlines()[-1] if output else 'Logged out.'}")


@require_auth
async def me_cmd(client: Client, message: Message) -> None:
    try:
        info = await mega.whoami()
    except MegaError as exc:
        await message.reply_text(f"\u274c {exc}")
        return
    await message.reply_text(f"**Account**\n{_code_block(info)}")


@require_auth
async def storage_cmd(client: Client, message: Message) -> None:
    try:
        info = await mega.storage()
    except MegaError as exc:
        await message.reply_text(f"\u274c {exc}")
        return
    await message.reply_text(f"**Storage**\n{_code_block(info)}")


@require_auth
async def ls_cmd(client: Client, message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    remote_path = parts[1].strip() if len(parts) > 1 else "/"
    try:
        listing = await mega.ls(remote_path)
    except MegaError as exc:
        await message.reply_text(f"\u274c {exc}")
        return
    await message.reply_text(f"**{remote_path}**\n{_code_block(listing)}")


def register(app: Client) -> None:
    app.add_handler(MessageHandler(login_cmd, filters.command("login") & allowed_filter))
    app.add_handler(MessageHandler(logout_cmd, filters.command("logout") & allowed_filter))
    app.add_handler(MessageHandler(me_cmd, filters.command("me") & allowed_filter))
    app.add_handler(MessageHandler(storage_cmd, filters.command("storage") & allowed_filter))
    app.add_handler(MessageHandler(ls_cmd, filters.command("ls") & allowed_filter))
