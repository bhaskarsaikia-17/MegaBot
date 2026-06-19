"""Basic handlers: /start, /help, /status."""

from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from ..auth import allowed_filter, require_auth
from ..bot import mega
from ..mega_client import MegaError

HELP_TEXT = (
    "**MegaBot — Mega.nz over Telegram**\n\n"
    "**Account**\n"
    "/login `<email> <password>` — log into a Mega account\n"
    "/logout — log out of the current account\n"
    "/me — account info (whoami)\n"
    "/storage — storage usage\n"
    "/ls `[remote_path]` — list files (default `/`)\n\n"
    "**Transfer**\n"
    "/download `<mega_link | /remote/path>` — download then send it here\n"
    "/upload `<mega_link>` — import a public link into your account\n"
    "Send me any file/document — I upload it to your Mega account\n\n"
    "**Info & links**\n"
    "/info `<mega_link>` — inspect a public link without downloading\n"
    "/details `</remote/path>` — details of a file in your account\n"
    "/export `</remote/path>` — create a public share link\n\n"
    "**Misc**\n"
    "/status — bot & MegaCMD status\n"
    "/help — this message"
)


@require_auth
async def start_cmd(client: Client, message: Message) -> None:
    name = message.from_user.first_name if message.from_user else "there"
    await message.reply_text(
        f"\U0001f44b Hi {name}!\n\n"
        "I can download from and upload to a Mega.nz account, inspect public "
        "links and report file details.\n\n"
        "Send /help to see everything I can do."
    )


@require_auth
async def help_cmd(client: Client, message: Message) -> None:
    await message.reply_text(HELP_TEXT, disable_web_page_preview=True)


@require_auth
async def status_cmd(client: Client, message: Message) -> None:
    try:
        version = await mega.ensure_available()
        logged_in = await mega.is_logged_in()
    except MegaError as exc:
        await message.reply_text(f"\u26a0\ufe0f MegaCMD problem:\n`{exc}`")
        return
    session = "\u2705 logged in" if logged_in else "\u274c logged out"
    await message.reply_text(
        f"**Bot status**\n"
        f"MegaCMD: `{version.splitlines()[0] if version else 'unknown'}`\n"
        f"Session: {session}"
    )


def register(app: Client) -> None:
    from pyrogram.handlers import MessageHandler

    app.add_handler(MessageHandler(start_cmd, filters.command("start") & allowed_filter))
    app.add_handler(MessageHandler(help_cmd, filters.command("help") & allowed_filter))
    app.add_handler(MessageHandler(status_cmd, filters.command("status") & allowed_filter))
