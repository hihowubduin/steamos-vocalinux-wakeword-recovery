# SteamOS Vocalinux Wake-Word Recovery

A checksum-pinned, ARM64 recovery package for restoring the local **Vocalinux 0.18.4-2** build after a SteamOS update. It enables local “Hey Jarvis” wake detection, preserves the configured CPU workaround, and includes the Frametop startup entry and Wayland clipboard helpers.

## Quick recovery

1. Clone this repository into a persistent location in your home directory, for example:
   ```sh
   git clone https://github.com/hihowubduin/steamos-vocalinux-wakeword-recovery.git \
     "$HOME/repos/steamos-vocalinux-wakeword-recovery"
   ```
2. Run `recovery/restore-vocalinux.sh` once from a terminal. It downloads the package from the matching GitHub Release if it is not already beside the script, verifies all checksums, asks for sudo authorization, installs the package and required SteamOS dependencies, and creates Desktop/application-menu shortcuts.
3. After a later SteamOS update, click **Restore Vocalinux** on the Desktop or find it in the application menu. Enter your sudo password in the Konsole window.

The app package and wake-word models are pinned in this repository/release. Internet is needed only if pacman has to reinstall system dependencies removed by SteamOS. The script makes the root filesystem writable as required by SteamOS package installation.

## Recovery bundle

- `recovery/restore-vocalinux.sh` — idempotent installer; verifies checksums, restores the app, CPU wrapper, clipboard tools, wake-word models, settings defaults, and Frametop autostart; then starts Vocalinux.
- `recovery/restore-vocalinux.desktop.in` — portable launcher template rendered for the current home directory by the restore script.
- `recovery/SHA256SUMS` — hashes for the app package, models, helper binaries, scripts, and third-party source archives.
- `recovery/models/wakeword/` — the Hey Jarvis detector and its feature models.
- `recovery/third-party/` — source archives and license texts for the wake-word runtime and `wl-clipboard` helper.
- **GitHub Release asset:** `vocalinux-bin-0.18.4-2-aarch64.pkg.tar.zst` (ARM64 package; intentionally a release asset rather than a Git-tracked file).

## Source and provenance

`vocalinux-source/` is the complete modified Vocalinux source tree, based on upstream commit [`62b0d157c416da28ef30fe5d97ef65b0556eea7f`](https://github.com/VocaHQ/vocalinux/commit/62b0d157c416da28ef30fe5d97ef65b0556eea7f). It includes the wake-mode implementation, dependency lock/export, tests, and build instructions. The AppImage package is built from this source on ARM64 and distributed under Vocalinux’s AGPL-3.0-only license; see [`LICENSE`](LICENSE) and the source tree.

Wake-word assets are from [openWakeWord](https://github.com/dscripka/openWakeWord), pinned to commit `368c03716d1e92591906a84949bc477f3a834455`; the Hey Jarvis and feature model assets are from release `v0.5.1`. `wl-copy` and `wl-paste` are from [wl-clipboard](https://github.com/bugaevc/wl-clipboard), tag `v2.3.0`. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and the accompanying license/source files.

## Scope and privacy

This is a community recovery bundle for SteamOS ARM64/Frametop. It is not affiliated with Valve or VocaHQ. Idle wake-word detection runs locally; no user configuration, credentials, or personal model data are included. The selected speech engine handles audio only after the wake phrase is detected.
