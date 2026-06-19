"""Asynchronous wrapper around the MegaCMD scriptable commands.

MegaCMD (https://mega.nz/cmd) ships a set of ``mega-*`` commands that talk to a
background server which keeps the login session alive between invocations. This
module shells out to those commands with :mod:`asyncio` subprocesses so the bot
never blocks its event loop on a transfer.

Why MegaCMD instead of a pure-Python library: it handles arbitrarily large
files, resumable transfers and the full account API reliably, which the
unmaintained ``mega.py`` package does not.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

# Commands that may legitimately take a long time (actual data transfers).
_TRANSFER_TIMEOUT = 60 * 60 * 6  # 6 hours
# Commands that should return quickly (metadata / account queries).
_QUICK_TIMEOUT = 120

_IS_WINDOWS = sys.platform.startswith("win")


class MegaError(RuntimeError):
    """Raised when a MegaCMD command fails or is not available."""


@dataclass
class CommandResult:
    """Result of a single MegaCMD invocation."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        """Combined stdout/stderr, stripped — handy for surfacing errors."""
        return (self.stdout + ("\n" + self.stderr if self.stderr else "")).strip()


class MegaClient:
    """Thin async interface over the ``mega-*`` MegaCMD commands."""

    def __init__(self, megacmd_path: str | None = None) -> None:
        # Directory containing the mega-* scriptable commands. When provided it
        # is prepended to PATH for every invocation so commands resolve even if
        # MegaCMD is not globally on PATH.
        self._megacmd_path = megacmd_path
        self._lock = asyncio.Lock()

    # -- low level ---------------------------------------------------------

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        if self._megacmd_path:
            env["PATH"] = self._megacmd_path + os.pathsep + env.get("PATH", "")
        return env

    @staticmethod
    def _argv(command: str, args: list[str]) -> list[str]:
        # On Windows the scriptable commands are .bat files which CreateProcess
        # cannot launch directly; route them through cmd.exe. On POSIX they are
        # ordinary executables.
        if _IS_WINDOWS:
            return ["cmd", "/c", command, *args]
        return [command, *args]

    async def _run(
        self,
        command: str,
        *args: str,
        timeout: int = _QUICK_TIMEOUT,
        check: bool = True,
    ) -> CommandResult:
        """Run a single ``mega-*`` command and capture its output."""
        argv = self._argv(command, list(args))
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._build_env(),
            )
        except FileNotFoundError as exc:
            raise MegaError(
                f"Could not find '{command}'. Is MegaCMD installed and on PATH "
                f"(or MEGACMD_PATH set correctly)? Original error: {exc}"
            ) from exc

        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise MegaError(f"Command '{command}' timed out after {timeout}s.") from exc

        result = CommandResult(
            returncode=proc.returncode if proc.returncode is not None else -1,
            stdout=stdout_b.decode("utf-8", errors="replace"),
            stderr=stderr_b.decode("utf-8", errors="replace"),
        )
        if check and not result.ok:
            raise MegaError(result.output or f"'{command}' failed with code {result.returncode}.")
        return result

    # -- availability ------------------------------------------------------

    async def ensure_available(self) -> str:
        """Return the MegaCMD version string, or raise if not installed."""
        result = await self._run("mega-version", check=False)
        if not result.ok and not result.stdout:
            raise MegaError(
                "MegaCMD does not appear to be installed. Download it from "
                "https://mega.nz/cmd and/or set MEGACMD_PATH."
            )
        return result.output

    # -- session -----------------------------------------------------------

    async def is_logged_in(self) -> bool:
        result = await self._run("mega-whoami", check=False)
        text = result.output.lower()
        if not result.ok:
            return False
        return "not logged in" not in text and "@" in text

    async def login(self, email: str, password: str) -> str:
        """Log into a Mega account. Serialised to avoid concurrent sessions."""
        async with self._lock:
            if await self.is_logged_in():
                # MegaCMD only allows one logged-in entity at a time.
                await self._run("mega-logout", check=False)
            result = await self._run("mega-login", email, password, timeout=_QUICK_TIMEOUT)
        return result.output or "Login complete."

    async def logout(self) -> str:
        async with self._lock:
            result = await self._run("mega-logout", check=False)
        return result.output or "Logged out."

    async def whoami(self) -> str:
        result = await self._run("mega-whoami", "-l")
        return result.output

    async def storage(self) -> str:
        result = await self._run("mega-df", "-h")
        return result.output

    # -- browsing ----------------------------------------------------------

    async def ls(self, remote_path: str = "/") -> str:
        result = await self._run("mega-ls", "-l", remote_path)
        return result.output

    async def file_info(self, remote_path: str) -> str:
        """Detailed listing (size, handle, dates) for a remote file/folder."""
        result = await self._run(
            "mega-ls", "-l", "--show-handles", "--time-format=ISO6081_WITH_TIME", remote_path
        )
        return result.output

    # -- transfers ---------------------------------------------------------

    async def download(self, link_or_remote_path: str, dest_dir: Path) -> list[Path]:
        """Download a public link or remote path into a fresh sub-directory.

        Returns the list of files that were downloaded. A unique sub-directory
        is used so the new files can be identified unambiguously.
        """
        target = Path(dest_dir) / f"dl_{uuid.uuid4().hex[:12]}"
        target.mkdir(parents=True, exist_ok=True)
        await self._run(
            "mega-get",
            link_or_remote_path,
            str(target),
            timeout=_TRANSFER_TIMEOUT,
        )
        files = [p for p in target.rglob("*") if p.is_file()]
        if not files:
            raise MegaError("Download reported success but no file was produced.")
        return files

    async def upload(self, local_path: Path, remote_path: str = "/") -> str:
        """Upload a local file/folder to a remote path in the account."""
        if not Path(local_path).exists():
            raise MegaError(f"Local path does not exist: {local_path}")
        result = await self._run(
            "mega-put",
            str(local_path),
            remote_path,
            timeout=_TRANSFER_TIMEOUT,
        )
        return result.output or "Upload finished."

    # -- sharing / links ---------------------------------------------------

    async def export(self, remote_path: str) -> str:
        """Create (or fetch) a public link for a remote path."""
        result = await self._run("mega-export", "-a", "-f", remote_path)
        return result.output

    async def import_link(self, link: str, remote_path: str = "/") -> str:
        """Import the contents of a public link into the account."""
        result = await self._run("mega-import", link, remote_path, timeout=_TRANSFER_TIMEOUT)
        return result.output

    async def link_info(self, link: str) -> str:
        """Inspect a public link without downloading its contents.

        Implemented by importing the link's metadata into a temporary folder in
        the (logged-in) account, listing it, then removing it again. Importing
        copies node metadata only — it does not transfer file contents — so it
        is fast and works for both file and folder links.

        Requires being logged in. Raises :class:`MegaError` otherwise.
        """
        if not await self.is_logged_in():
            raise MegaError(
                "Inspecting a public link requires being logged in. "
                "Use /login first, then try again."
            )
        tmp_remote = f"/.megabot_linkinfo_{uuid.uuid4().hex[:10]}"
        async with self._lock:
            await self._run("mega-mkdir", "-p", tmp_remote, check=False)
            try:
                await self._run("mega-import", link, tmp_remote, timeout=_TRANSFER_TIMEOUT)
                listing = await self._run(
                    "mega-ls",
                    "-l",
                    "-R",
                    "--time-format=ISO6081_WITH_TIME",
                    tmp_remote,
                )
                usage = await self._run("mega-du", "-h", tmp_remote, check=False)
            finally:
                # Always clean up the temporary metadata copy.
                await self._run("mega-rm", "-r", "-f", tmp_remote, check=False)
        return (listing.output + "\n\n" + usage.output).strip()


def cleanup_dir(path: Path) -> None:
    """Best-effort recursive delete of a working directory."""
    shutil.rmtree(path, ignore_errors=True)
