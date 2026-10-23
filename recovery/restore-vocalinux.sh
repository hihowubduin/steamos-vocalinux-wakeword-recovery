#!/usr/bin/env bash
set -Eeuo pipefail

RECOVERY="$(cd -- "$(dirname -- "$(readlink -f -- "$0")")" && pwd)"
PACKAGE="$RECOVERY/vocalinux-bin-0.18.4-2-aarch64.pkg.tar.zst"
CONFIG="$HOME/.config/frametop/vocalinux/config.json"
AUTOSTART="$HOME/.config/frametop/autostart/vocalinux.desktop"
LOCK="$HOME/.local/share/vocalinux/instance.lock"
LOG="$HOME/.local/share/vocalinux/logs/restore.log"

fail() {
    printf '\nRestore failed: %s\n' "$*" >&2
    exit 1
}

[ "$(uname -m)" = aarch64 ] || fail "This recovery bundle is for SteamOS ARM64."
command -v pacman >/dev/null || fail "pacman is unavailable."
command -v steamos-readonly >/dev/null || fail "This recovery script expects SteamOS."
[ -f "$RECOVERY/SHA256SUMS" ] || fail "The recovery checksum manifest is missing."

if [ ! -f "$PACKAGE" ]; then
    command -v curl >/dev/null || fail "curl is required to download the saved package."
    printf '%s\n' 'Downloading the saved ARM64 package from the public GitHub release...'
    curl --fail --silent --show-error --location --retry 3 "https://github.com/hihowubduin/steamos-vocalinux-wakeword-recovery/releases/download/v0.18.4-2/vocalinux-bin-0.18.4-2-aarch64.pkg.tar.zst" --output "$PACKAGE.part" || fail "The recovery package download failed."
    mv "$PACKAGE.part" "$PACKAGE"
fi

printf '%s\n' 'Checking the local, checksum-pinned recovery bundle...'
(
    cd "$RECOVERY"
    sha256sum --check --status SHA256SUMS || fail "A recovery file failed checksum verification."
)

printf '%s\n' 'Requesting administrator access...'
sudo -v
sudo steamos-readonly disable

printf '%s\n' 'Installing required SteamOS runtime dependencies...'
sudo pacman -S --needed --noconfirm fuse2 hicolor-icon-theme xdotool wayland
printf '%s\n' 'Installing optional clipboard, IBus, and sound helpers...'
if ! sudo pacman -S --needed --noconfirm xclip xsel ibus espeak-ng pcaudiolib libsonic; then
    printf '%s\n' 'Some optional helpers are unavailable; continuing with the bundled app and Wayland clipboard tools.'
fi

printf '%s\n' 'Installing the saved Vocalinux package...'
sudo pacman -U --noconfirm "$PACKAGE"
sudo install -Dm755 "$RECOVERY/vocalinux-wrapper.sh" /usr/local/bin/vocalinux
sudo install -Dm755 "$RECOVERY/wl-copy" /usr/local/bin/wl-copy
sudo install -Dm755 "$RECOVERY/wl-paste" /usr/local/bin/wl-paste

printf '%s\n' 'Restoring wake-word assets and Frametop autostart...'
install -d -m755 "$HOME/.local/share/vocalinux/models/wakeword"
for asset in hey_jarvis_v0.1.onnx embedding_model.onnx melspectrogram.onnx; do
    install -m644 "$RECOVERY/models/wakeword/$asset" \
        "$HOME/.local/share/vocalinux/models/wakeword/$asset"
done
install -Dm644 "$RECOVERY/autostart-vocalinux.desktop" "$AUTOSTART"

python3 - "$CONFIG" <<'PY'
import json
import os
import sys
import tempfile

path = sys.argv[1]
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
except FileNotFoundError:
    config = {}

wake = config.setdefault("wake_word", {})
if not isinstance(wake, dict):
    wake = config["wake_word"] = {}
wake.setdefault("enabled", True)
wake.setdefault("model", "hey_jarvis")
wake.setdefault("threshold", 0.5)
wake.setdefault("no_speech_timeout", 5.0)

fd, temporary = tempfile.mkstemp(prefix="config.json.", dir=os.path.dirname(path))
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=4)
        handle.write("\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY

printf '%s\n' 'Checking the installed package and restored files...'
pacman -Q vocalinux-bin
pacman -Qkk vocalinux-bin
/usr/local/bin/vocalinux --version
(
    cd "$HOME/.local/share/vocalinux/models/wakeword"
    grep -E '^([0-9a-f]{64})  models/wakeword/(hey_jarvis_v0\.1|embedding_model|melspectrogram)\.onnx$' \
        "$RECOVERY/SHA256SUMS" | sed 's#models/wakeword/##' | sha256sum --check --status \
        || fail "A restored wake-word model failed checksum verification."
)
grep -F 'Exec=/usr/local/bin/vocalinux --start-minimized' "$AUTOSTART" >/dev/null \
    || fail "Frametop autostart does not point to the restored wrapper."
python3 - "$RECOVERY/restore-vocalinux.desktop.in" "$RECOVERY" "$HOME" <<'PY'
import os
import sys

source, recovery, home = sys.argv[1:]
with open(source, encoding="utf-8") as handle:
    template = handle.read()
recovery_exec = recovery.replace("\\", "\\\\").replace('"', '\\"')
launcher = template.replace("@RECOVERY@", recovery_exec)
outputs = (
    os.path.join(recovery, "restore-vocalinux.desktop"),
    os.path.join(home, "Desktop", "Restore Vocalinux.desktop"),
    os.path.join(home, ".local", "share", "applications", "restore-vocalinux.desktop"),
)
for path in outputs:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(launcher)
    os.chmod(path, 0o755)
PY
gio set "$HOME/Desktop/Restore Vocalinux.desktop" metadata::trusted true 2>/dev/null || true

if [ -r "$LOCK" ]; then
    old_pid="$(sed -n '1p' "$LOCK")"
    if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null \
        && tr '\0' ' ' <"/proc/$old_pid/cmdline" 2>/dev/null | grep -q 'vocalinux.main'; then
        printf 'Stopping the existing Vocalinux process (PID %s)...\n' "$old_pid"
        kill -TERM "$old_pid"
        for _ in $(seq 1 15); do
            kill -0 "$old_pid" 2>/dev/null || break
            sleep 1
        done
        kill -0 "$old_pid" 2>/dev/null && fail "The existing Vocalinux process did not stop."
    fi
fi

install -d -m755 "$(dirname "$LOG")"
printf '%s\n' 'Starting Vocalinux with the preserved local wake-word settings...'
setsid -f /usr/local/bin/vocalinux --start-minimized >>"$LOG" 2>&1
for _ in $(seq 1 15); do
    if [ -r "$LOCK" ]; then
        new_pid="$(sed -n '1p' "$LOCK")"
        if [[ "$new_pid" =~ ^[0-9]+$ ]] && kill -0 "$new_pid" 2>/dev/null; then
            printf 'Vocalinux is running (PID %s). Wake-word mode: ' "$new_pid"
            python3 -c 'import json,sys; print("enabled" if json.load(open(sys.argv[1])).get("wake_word", {}).get("enabled", True) else "disabled")' "$CONFIG"
            printf 'Log: %s\n' "$LOG"
            if [ -t 0 ]; then
                read -r -p 'Recovery complete. Press Enter to close this window. '
            fi
            exit 0
        fi
    fi
    sleep 1
done

tail -n 40 "$LOG" >&2 || true
fail "Vocalinux did not acquire its instance lock; see $LOG."
