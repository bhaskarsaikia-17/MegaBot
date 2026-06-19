#!/usr/bin/env bash
#
# bot.sh — manage MegaBot as a systemd service for 24/7 operation.
#
# Usage:
#   ./bot.sh install     Create + enable + start the systemd service
#   ./bot.sh uninstall   Stop, disable and remove the service
#   ./bot.sh start        Start the service
#   ./bot.sh stop         Stop the service
#   ./bot.sh restart      Restart the service
#   ./bot.sh status       Show service status
#   ./bot.sh logs         Follow live logs (Ctrl+C to exit)
#   ./bot.sh enable       Start automatically on boot
#   ./bot.sh disable      Do not start on boot
#   ./bot.sh update       git pull, reinstall deps, restart
#
set -euo pipefail

# --- configuration ----------------------------------------------------------

SERVICE_NAME="megabot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Absolute path to the project directory (where this script lives).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# User the service should run as. When invoked through sudo, prefer the
# original (non-root) user so the bot uses that user's MegaCMD session/cache.
RUN_USER="${SUDO_USER:-$(id -un)}"

# Pick the interpreter: project venv first, then python3 on PATH.
if [[ -x "${SCRIPT_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "ERROR: no python3 found and no .venv present." >&2
    exit 1
fi

# --- helpers -----------------------------------------------------------------

# Run a command as root, using sudo only when not already root.
as_root() {
    if [[ "$(id -u)" -eq 0 ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        echo "ERROR: this action needs root privileges and sudo is not available." >&2
        exit 1
    fi
}

require_installed() {
    if [[ ! -f "${SERVICE_FILE}" ]]; then
        echo "Service is not installed. Run: ./bot.sh install" >&2
        exit 1
    fi
}

# Run a command as the target (non-root) service user. When the script is
# invoked through sudo, drop back to $SUDO_USER so files (the venv, caches)
# are owned by that user and not root. Otherwise run as-is.
run_as_user() {
    if [[ "$(id -u)" -eq 0 && -n "${SUDO_USER:-}" ]]; then
        sudo -u "${SUDO_USER}" "$@"
    else
        "$@"
    fi
}

# --- commands ----------------------------------------------------------------

cmd_setup() {
    local venv="${SCRIPT_DIR}/.venv"
    if ! command -v python3 >/dev/null 2>&1; then
        echo "ERROR: python3 is not installed. Install it first, e.g.:" >&2
        echo "  sudo apt update && sudo apt install -y python3 python3-venv python3-pip" >&2
        exit 1
    fi
    if [[ ! -d "${venv}" ]]; then
        echo "Creating virtualenv at ${venv} ..."
        run_as_user python3 -m venv "${venv}"
    fi
    echo "Installing dependencies into ${venv} ..."
    run_as_user "${venv}/bin/python" -m pip install --upgrade pip
    run_as_user "${venv}/bin/python" -m pip install -r "${SCRIPT_DIR}/requirements.txt"
    echo
    echo "Setup complete. Next:"
    echo "  1. Ensure .env exists (cp .env.example .env && edit it)."
    echo "  2. Install MegaCMD if you haven't: https://mega.nz/cmd"
    echo "  3. Run: sudo bash bot.sh install   (or 'restart' if already installed)"
}

cmd_install() {
    echo "Installing systemd service '${SERVICE_NAME}'..."
    echo "  Project dir : ${SCRIPT_DIR}"
    echo "  Run as user : ${RUN_USER}"
    echo "  Python      : ${PYTHON_BIN}"

    if [[ "${PYTHON_BIN}" != *"/.venv/"* ]]; then
        echo "WARNING: using system Python (${PYTHON_BIN}); no .venv detected."
        echo "         If dependencies aren't installed the bot will crash-loop."
        echo "         Recommended: run './bot.sh setup' first."
    fi
    if ! "${PYTHON_BIN}" -c "import pyrogram" >/dev/null 2>&1; then
        echo "WARNING: '${PYTHON_BIN}' cannot import pyrogram (Kurigram)."
        echo "         Run './bot.sh setup' to create a venv and install deps."
    fi

    if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
        echo "WARNING: ${SCRIPT_DIR}/.env not found. Create it before starting"
        echo "         (copy .env.example to .env and fill in your values)."
    fi

    local unit
    unit="$(cat <<EOF
[Unit]
Description=MegaBot — Telegram <-> Mega.nz bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${PYTHON_BIN} ${SCRIPT_DIR}/main.py
Restart=always
RestartSec=5
# Give in-flight transfers time to finish on stop/restart.
TimeoutStopSec=30
KillSignal=SIGINT

[Install]
WantedBy=multi-user.target
EOF
)"

    echo "${unit}" | as_root tee "${SERVICE_FILE}" >/dev/null
    as_root systemctl daemon-reload
    as_root systemctl enable --now "${SERVICE_NAME}"
    echo "Done. The bot is running and will start on boot."
    echo "Follow logs with: ./bot.sh logs"
}

cmd_uninstall() {
    require_installed
    echo "Removing systemd service '${SERVICE_NAME}'..."
    as_root systemctl disable --now "${SERVICE_NAME}" || true
    as_root rm -f "${SERVICE_FILE}"
    as_root systemctl daemon-reload
    echo "Service removed."
}

cmd_start() {
    require_installed
    as_root systemctl start "${SERVICE_NAME}"
    cmd_status
}

cmd_stop() {
    require_installed
    as_root systemctl stop "${SERVICE_NAME}"
    echo "Stopped."
}

cmd_restart() {
    require_installed
    as_root systemctl restart "${SERVICE_NAME}"
    cmd_status
}

cmd_status() {
    require_installed
    as_root systemctl status "${SERVICE_NAME}" --no-pager || true
}

cmd_logs() {
    require_installed
    # -f follow, -n recent history, -u this unit only.
    as_root journalctl -u "${SERVICE_NAME}" -n 100 -f
}

cmd_enable() {
    require_installed
    as_root systemctl enable "${SERVICE_NAME}"
    echo "Enabled on boot."
}

cmd_disable() {
    require_installed
    as_root systemctl disable "${SERVICE_NAME}"
    echo "Disabled on boot."
}

cmd_update() {
    echo "Updating MegaBot..."
    if [[ -d "${SCRIPT_DIR}/.git" ]]; then
        git -C "${SCRIPT_DIR}" pull --ff-only
    else
        echo "  (not a git checkout; skipping git pull)"
    fi
    run_as_user "${PYTHON_BIN}" -m pip install -r "${SCRIPT_DIR}/requirements.txt"
    if [[ -f "${SERVICE_FILE}" ]]; then
        cmd_restart
    else
        echo "Service not installed yet; run ./bot.sh install"
    fi
}

usage() {
    cat <<'EOF'
bot.sh — manage MegaBot as a systemd service for 24/7 operation.

Usage:
  ./bot.sh setup       Create .venv and install Python dependencies
  ./bot.sh install     Create + enable + start the systemd service
  ./bot.sh uninstall   Stop, disable and remove the service
  ./bot.sh start       Start the service
  ./bot.sh stop        Stop the service
  ./bot.sh restart     Restart the service
  ./bot.sh status      Show service status
  ./bot.sh logs        Follow live logs (Ctrl+C to exit)
  ./bot.sh enable      Start automatically on boot
  ./bot.sh disable     Do not start on boot
  ./bot.sh update      git pull, reinstall deps, restart
EOF
}

# --- dispatch ----------------------------------------------------------------

case "${1:-}" in
    setup)     cmd_setup ;;
    install)   cmd_install ;;
    uninstall) cmd_uninstall ;;
    start)     cmd_start ;;
    stop)      cmd_stop ;;
    restart)   cmd_restart ;;
    status)    cmd_status ;;
    logs)      cmd_logs ;;
    enable)    cmd_enable ;;
    disable)   cmd_disable ;;
    update)    cmd_update ;;
    ""|-h|--help|help) usage ;;
    *)
        echo "Unknown command: $1" >&2
        echo >&2
        usage >&2
        exit 1
        ;;
esac
