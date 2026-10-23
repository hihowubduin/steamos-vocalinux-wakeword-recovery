#!/bin/sh
# Vocalinux launcher wrapper (local fix; not part of the pacman package).
#
# Problem: whisper.cpp's Vulkan backend miscompiles on this machine's Turnip
# driver (Mesa 26.3, Adreno 750). ggml reports:
#   MESA: error: Compute shader ((null)) which has workgroup barrier cannot be
#   used because it's impossible to have enough concurrent waves.
# The miscompiled compute pass returns a run of "!" characters instead of text.
# Vocalinux filters that as a non-speech token, so every dictation ends with
# "whisper.cpp returned empty transcription" and no text is ever typed.
#
# Fix: GGML_VK_VISIBLE_DEVICES=-1 hides the Vulkan device from ggml.
# Vocalinux's own documented fallback then sees "no usable ggml GPU device"
# and loads whisper.cpp with use_gpu=False, which transcribes correctly on
# the CPU (~1.5 s of inference per 3 s of audio here).
#
# Set VOCALINUX_ENABLE_VULKAN=1 to try the GPU path again -- worth doing once
# the upstream Turnip/whisper.cpp workgroup-barrier bug is fixed.

if [ "${VOCALINUX_ENABLE_VULKAN:-0}" != "1" ]; then
    GGML_VK_VISIBLE_DEVICES=-1
    export GGML_VK_VISIBLE_DEVICES
fi

# Resolve the real binary through the pacman-owned symlink so a package
# upgrade (which changes the version in the path) keeps working.
real=$(readlink -f /usr/bin/vocalinux 2>/dev/null)
if [ -z "$real" ] || [ ! -x "$real" ]; then
    echo "vocalinux: cannot resolve /usr/bin/vocalinux" >&2
    exit 1
fi

exec "$real" "$@"
