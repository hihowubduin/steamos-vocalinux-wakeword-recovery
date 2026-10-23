# Third-party notices

This repository redistributes the following open-source components. Their source versions and, where applicable, source archives are included or linked below.

## Vocalinux

The modified Vocalinux application and local recovery integration are licensed under **AGPL-3.0-only**. The upstream license is [`LICENSE`](LICENSE); the corresponding modified source snapshot is [`vocalinux-source/`](vocalinux-source/).

Upstream: [VocaHQ/vocalinux](https://github.com/VocaHQ/vocalinux), base commit `62b0d157c416da28ef30fe5d97ef65b0556eea7f`.

## openWakeWord and Hey Jarvis models

The wake-word runtime is pinned to openWakeWord commit `368c03716d1e92591906a84949bc477f3a834455`; its project license is Apache-2.0, provided as [`recovery/third-party/LICENSE-openWakeWord-Apache-2.0`](recovery/third-party/LICENSE-openWakeWord-Apache-2.0). A source archive for that commit is [`recovery/third-party/openWakeWord-368c0371.tar.gz`](recovery/third-party/openWakeWord-368c0371.tar.gz).

The Hey Jarvis detector and shared feature models are unmodified assets from the openWakeWord `v0.5.1` release. The upstream model description and training-data notes are in [docs/models/hey_jarvis.md](https://github.com/dscripka/openWakeWord/blob/v0.5.1/docs/models/hey_jarvis.md).

## wl-clipboard

The bundled `wl-copy` and `wl-paste` utilities are from wl-clipboard `v2.3.0`, licensed under **GNU GPL version 3 or later**. The license is [`recovery/third-party/COPYING-wl-clipboard-GPL-3.0`](recovery/third-party/COPYING-wl-clipboard-GPL-3.0); the corresponding source archive is [`recovery/third-party/wl-clipboard-v2.3.0.tar.gz`](recovery/third-party/wl-clipboard-v2.3.0.tar.gz).

## Other bundled Python dependencies

Python dependency versions and artifact hashes used for the AppImage build are recorded in `vocalinux-source/uv.lock` and `vocalinux-source/requirements/`. Upstream project licenses and copyright notices remain in the bundled AppImage and their package metadata.
