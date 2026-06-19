# MegaBot

A Telegram bot that drives a [Mega.nz](https://mega.nz) account: **download**,
**upload**, inspect **file details** and **public link details**, and check
**account info** — all from a Telegram chat.

It uses:

- **[Kurigram](https://pypi.org/project/Kurigram/)** — a maintained fork of
  Pyrogram (the original was archived in Dec 2024). The MTProto API lets the bot
  send/receive files up to **2 GiB** (4 GiB for premium accounts), far beyond
  the 50 MB limit of the plain Bot API.
- **[MegaCMD](https://mega.nz/cmd)** — Mega's official command-line client,
  wrapped via async subprocesses. It handles large files, resumable transfers
  and the full account API reliably.

---

## Features

| Command | What it does |
| --- | --- |
| `/start`, `/help` | Usage and command list |
| `/status` | Bot + MegaCMD status and login state |
| `/login <email> <password>` | Log into a Mega account |
| `/logout` | Log out |
| `/me` | Account info (`whoami -l`) |
| `/storage` | Storage usage (`df -h`) |
| `/ls [remote_path]` | List files in the account (default `/`) |
| `/download <link \| /remote/path>` | Download from Mega and send the file(s) to the chat |
| `/upload <mega_link>` | Import a public link into your account |
| *(send any file)* | Uploads the file to your Mega account (caption = destination folder) |
| `/info <mega_link>` | Inspect a public link **without downloading** it |
| `/details </remote/path>` | Detailed listing of a file in your account |
| `/export </remote/path>` | Create a public share link |

---

## Prerequisites

1. **Python 3.10+**
2. **MegaCMD** installed and reachable:
   - Download: <https://mega.nz/cmd>
   - **Windows:** the `mega-*` commands live in
     `C:\Users\<you>\AppData\Local\MEGAcmd`. Either add that folder to your
     `PATH`, or set `MEGACMD_PATH` in `.env`.
   - **Linux/macOS:** the commands are usually already on `PATH` after install
     (`/usr/bin`, or the `.app/Contents/MacOS` folder on macOS).
   - Verify with: `mega-version`
3. **Telegram credentials:**
   - `API_ID` and `API_HASH` from <https://my.telegram.org> → *API development tools*
   - A bot token from [@BotFather](https://t.me/BotFather)
   - Your numeric Telegram user ID from [@userinfobot](https://t.me/userinfobot)

---

## Setup

```bash
# 1. (optional) create a virtual environment
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/mac: source .venv/bin/activate

# 2. install dependencies
pip install -r requirements.txt

# 3. configure
copy .env.example .env      # Windows
# cp .env.example .env      # Linux/mac
# then edit .env and fill in your values
```

Minimum `.env` values: `API_ID`, `API_HASH`, `BOT_TOKEN`, and `ALLOWED_USERS`.

---

## Run

```bash
python main.py
```

You should see log lines confirming MegaCMD was detected and the bot started.
Open a chat with your bot and send `/start`.

You can log into Mega in two ways:

- **At runtime:** `/login your@email.com yourpassword`
  (then delete that message — it contains your password).
- **Automatically on startup:** set `MEGA_EMAIL` and `MEGA_PASSWORD` in `.env`.

---

## Security notes

- **Access control is essential.** This bot can read and modify a Mega account.
  Always set `ALLOWED_USERS` to your own Telegram ID(s). If it is left empty the
  bot logs a loud warning and responds to **everyone**.
- Credentials sent via `/login` appear in the Telegram chat history — delete
  those messages afterwards. Storing them in `.env` avoids this.
- `.env` and `*.session` files are git-ignored. Never commit them.
- MegaCMD keeps the session alive in a background server process and in a local
  cache under your home folder. Use `/logout` to end it.

---

## How public-link inspection works

Telegram/MegaCMD cannot list a *foreign* public link while you are logged into
your own account (MegaCMD allows only one logged-in entity at a time). So
`/info` imports the link's **metadata** into a temporary hidden folder in your
account (this copies node info only — it does **not** download file contents),
lists it, then deletes the temporary folder. You must be logged in for `/info`.

---

## Limitations

- **2 GiB per file** to/from Telegram (4 GiB on premium). Larger Mega downloads
  succeed on the host but cannot be forwarded into the chat; the bot reports the
  local path instead.
- **Download progress is coarse.** MegaCMD performs the transfer as one blocking
  command, so the bot shows fine-grained progress only for the
  Telegram-side send/receive, not the Mega-side transfer.
- **Single account at a time.** MegaCMD maintains one session shared by all
  authorised users of the bot.
- The bot host needs enough free disk space for the largest file being
  transferred, since files pass through local storage.

---

## Project layout

```
MegaBot/
├── main.py                  # entrypoint: starts client, auto-login, idle loop
├── config.py                # env loading & validation (fails fast)
├── requirements.txt
├── .env.example
└── megabot/
    ├── bot.py               # Pyrogram Client + shared MegaClient
    ├── auth.py              # allow-list access control
    ├── mega_client.py       # async MegaCMD subprocess wrapper
    ├── handlers/
    │   ├── basic.py         # /start /help /status
    │   ├── account.py       # /login /logout /me /storage /ls
    │   ├── transfer.py      # /download, /upload, file uploads
    │   └── info.py          # /info /details /export
    └── utils/
        ├── format.py        # human-readable sizes/durations, progress bar
        └── progress.py      # throttled Telegram progress callback
```
