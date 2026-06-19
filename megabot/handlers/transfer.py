"""Transfer handlers.

* ``/download <link|/remote/path>`` — fetch from Mega, then send the file(s)
  into the chat.
* ``/upload <link>`` — import a public link into the logged-in account.
* Any uploaded document/media — saved locally then uploaded to Mega.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from config import config

from ..auth import allowed_filter, require_auth
from ..bot import mega
from ..mega_client import MegaError, cleanup_dir
from ..utils.format import human_size
from ..utils.progress import ProgressReporter

log = logging.getLogger("megabot.transfer")

# Pyrogram/Telegram hard cap for a single file over MTProto (non-premium bots).
_TELEGRAM_MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB


def _looks_like_link(text: str) -> bool:
    return "mega.nz/" in text or "mega.co.nz/" in text


@require_auth
async def download_cmd(client: Client, message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply_text("Usage: `/download <mega_link | /remote/path>`")
        return
    source = parts[1].strip()
    status = await message.reply_text("\u2b07\ufe0f Downloading from Mega...")

    dl_files: list[Path] = []
    target_dir: Path | None = None
    try:
        dl_files = await mega.download(source, config.download_dir)
        target_dir = dl_files[0].parent
        await status.edit_text(
            f"\u2705 Downloaded {len(dl_files)} file(s). Sending to Telegram..."
        )

        for path in dl_files:
            size = path.stat().st_size
            if size > _TELEGRAM_MAX_BYTES:
                await message.reply_text(
                    f"\u26a0\ufe0f `{path.name}` is {human_size(size)} — over "
                    f"Telegram's 2 GiB limit, so I can't send it here. It is "
                    f"downloaded on the bot host at:\n`{path}`"
                )
                continue
            reporter = ProgressReporter(status, f"Uploading {path.name}")
            await client.send_document(
                chat_id=message.chat.id,
                document=str(path),
                caption=f"`{path.name}` · {human_size(size)}",
                file_name=path.name,
                progress=reporter,
            )
        await status.edit_text("\u2705 Done.")
    except MegaError as exc:
        await status.edit_text(f"\u274c Download failed:\n`{exc}`")
    except Exception as exc:  # noqa: BLE001 - surface any sending error to user
        log.exception("Unexpected error during /download")
        await status.edit_text(f"\u274c Error: `{exc}`")
    finally:
        # Clean the unique per-download directory once everything is sent.
        if target_dir is not None:
            cleanup_dir(target_dir)


@require_auth
async def import_cmd(client: Client, message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2 or not _looks_like_link(parts[1]):
        await message.reply_text("Usage: `/upload <mega_public_link>`")
        return
    link = parts[1]
    remote = parts[2] if len(parts) > 2 else "/"
    status = await message.reply_text("\U0001f4e5 Importing link into your account...")
    try:
        output = await mega.import_link(link, remote)
    except MegaError as exc:
        await status.edit_text(f"\u274c Import failed:\n`{exc}`")
        return
    await status.edit_text(f"\u2705 {output or 'Imported.'}")


@require_auth
async def upload_media(client: Client, message: Message) -> None:
    """Save an uploaded document/media locally, then push it to Mega."""
    media = (
        message.document
        or message.video
        or message.audio
        or message.photo
        or message.voice
        or message.animation
    )
    if media is None:
        return

    # Optional caption -> remote destination folder (defaults to root).
    remote = (message.caption or "/").strip() or "/"
    status = await message.reply_text("\u2b07\ufe0f Receiving file from Telegram...")

    local_path: str | None = None
    try:
        reporter = ProgressReporter(status, "Downloading from Telegram")
        local_path = await message.download(
            file_name=str(config.download_dir) + "/",
            progress=reporter,
        )
        if not local_path:
            await status.edit_text("\u274c Could not download the file.")
            return

        await status.edit_text("\u2b06\ufe0f Uploading to Mega...")
        output = await mega.upload(Path(local_path), remote)
        await status.edit_text(f"\u2705 Uploaded to `{remote}`.\n`{output}`")
    except MegaError as exc:
        await status.edit_text(f"\u274c Upload failed:\n`{exc}`")
    except Exception as exc:  # noqa: BLE001
        log.exception("Unexpected error during media upload")
        await status.edit_text(f"\u274c Error: `{exc}`")
    finally:
        if local_path:
            try:
                Path(local_path).unlink(missing_ok=True)
            except OSError:
                pass


def register(app: Client) -> None:
    app.add_handler(MessageHandler(download_cmd, filters.command("download") & allowed_filter))
    app.add_handler(MessageHandler(import_cmd, filters.command("upload") & allowed_filter))
    # Any non-command message carrying a file triggers an upload to Mega.
    media_filter = (
        filters.document
        | filters.video
        | filters.audio
        | filters.photo
        | filters.voice
        | filters.animation
    )
    app.add_handler(MessageHandler(upload_media, media_filter & allowed_filter))
