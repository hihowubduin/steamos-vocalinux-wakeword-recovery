Vocalinux SteamOS recovery bundle

After a SteamOS update removes the local app, double-click “Restore Vocalinux”
on the Desktop. It opens a terminal, checks the saved package and model hashes,
asks for your sudo password, reinstalls the app and helpers, preserves your
settings, restores Hey Jarvis assets/autostart, then starts Vocalinux.

The ready-to-install ARM64 package and wake-word models are stored locally, so
the app itself does not need to be rebuilt. If the package is missing, the
script downloads it from the public recovery release. Internet is needed only
if SteamOS removed system dependencies that pacman must reinstall.

Public source and releases:
https://github.com/hihowubduin/steamos-vocalinux-wakeword-recovery

If the Desktop shortcut disappears, double-click the executable
restore-vocalinux.desktop in this folder, or copy it to ~/Desktop.

Recovery script: restore-vocalinux.sh
Package: vocalinux-bin 0.18.4-2 (SteamOS aarch64)
