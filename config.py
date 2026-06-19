"""Configuration loading and validation.

All runtime configuration comes from environment variables (optionally loaded
from a local ``.env`` file). Import :data:`config` from this module to access
the validated, typed configuration object.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a .env file in the project root if present. Real
# environment variables always take precedence over .env values.
load_dotenv()


class ConfigError(RuntimeError):
    """Raised when the environment configuration is missing or invalid."""


def _get_str(name: str, default: str | None = None, *, required: bool = False) -> str | None:
    value = os.getenv(name, default)
    if value is not None:
        value = value.strip()
    if required and not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value or default


def _get_int(name: str, *, required: bool = False) -> int | None:
    raw = _get_str(name, required=required)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer, got {raw!r}") from exc


def _get_id_set(name: str) -> set[int]:
    raw = _get_str(name, default="") or ""
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError as exc:
            raise ConfigError(
                f"Environment variable {name} contains a non-numeric ID: {part!r}"
            ) from exc
    return ids


@dataclass(frozen=True)
class Config:
    """Validated application configuration."""

    api_id: int
    api_hash: str
    bot_token: str
    allowed_users: frozenset[int]
    mega_email: str | None
    mega_password: str | None
    download_dir: Path
    megacmd_path: str | None

    @property
    def auto_login(self) -> bool:
        """Whether credentials are present for startup auto-login."""
        return bool(self.mega_email and self.mega_password)

    @property
    def public_access(self) -> bool:
        """True when no allow-list is configured (bot open to everyone)."""
        return not self.allowed_users

    def is_allowed(self, user_id: int) -> bool:
        """Return True if the given Telegram user id may use the bot."""
        return self.public_access or user_id in self.allowed_users


def load_config() -> Config:
    """Build and validate a :class:`Config` from the environment."""
    api_id = _get_int("API_ID", required=True)
    api_hash = _get_str("API_HASH", required=True)
    bot_token = _get_str("BOT_TOKEN", required=True)

    download_dir = Path(_get_str("DOWNLOAD_DIR", default="./downloads")).expanduser()
    download_dir.mkdir(parents=True, exist_ok=True)

    megacmd_path = _get_str("MEGACMD_PATH", default="") or None

    return Config(
        api_id=api_id,  # type: ignore[arg-type]  # required=True guarantees not None
        api_hash=api_hash,  # type: ignore[arg-type]
        bot_token=bot_token,  # type: ignore[arg-type]
        allowed_users=frozenset(_get_id_set("ALLOWED_USERS")),
        mega_email=_get_str("MEGA_EMAIL", default="") or None,
        mega_password=_get_str("MEGA_PASSWORD", default="") or None,
        download_dir=download_dir,
        megacmd_path=megacmd_path,
    )


# Eagerly load configuration at import time so misconfiguration fails fast.
config: Config = load_config()
