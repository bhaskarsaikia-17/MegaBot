"""Info handlers: /info (public link), /details (remote file), /export."""

from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from ..auth import allowed_filter, require_auth
from ..bot import mega
from ..mega_client import MegaError


def _code_block(text: str, limit: int = 3800) -> str:
    text = text or "(no output)"
    if len(text) > limit:
        text = text[:limit] + "\n... (truncated)"
    return f"```\n{text}\n```"


def _looks_like_link(text: str) -> bool:
    return "mega.nz/" in text or "mega.co.nz/" in text


@require_auth
async def info_cmd(client: Client, message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2 or not _looks_like_link(parts[1]):
        await message.reply_text("Usage: `/info <mega_public_link>`")
        return
    status = await message.reply_text("\U0001f50d Inspecting link...")
    try:
        details = await mega.link_info(parts[1])
    except MegaError as exc:
        await status.edit_text(f"\u274c {exc}")
        return
    await status.edit_text(f"**Link contents**\n{_code_block(details)}")


@require_auth
async def details_cmd(client: Client, message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply_text("Usage: `/details </remote/path>`")
        return
    try:
        details = await mega.file_info(parts[1].strip())
    except MegaError as exc:
        await message.reply_text(f"\u274c {exc}")
        return
    await message.reply_text(f"**Details**\n{_code_block(details)}")


@require_auth
async def export_cmd(client: Client, message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply_text("Usage: `/export </remote/path>`")
        return
    status = await message.reply_text("\U0001f517 Creating public link...")
    try:
        output = await mega.export(parts[1].strip())
    except MegaError as exc:
        await status.edit_text(f"\u274c {exc}")
        return
    await status.edit_text(f"**Public link**\n{_code_block(output)}")


def register(app: Client) -> None:
    app.add_handler(MessageHandler(info_cmd, filters.command("info") & allowed_filter))
    app.add_handler(MessageHandler(details_cmd, filters.command("details") & allowed_filter))
    app.add_handler(MessageHandler(export_cmd, filters.command("export") & allowed_filter))
