"""Pinned openWakeWord assets for local Hey Jarvis detection."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import NamedTuple

import requests

from .model_checksums import ChecksumError, verify_model_file
from .paths import models_dir

logger = logging.getLogger(__name__)

OPENWAKEWORD_RELEASE = "v0.5.1"
WAKE_WORD_NAME = "hey_jarvis"
WAKE_WORD_FILES = {
    "hey_jarvis_v0.1.onnx": f"https://github.com/dscripka/openWakeWord/releases/download/{OPENWAKEWORD_RELEASE}/hey_jarvis_v0.1.onnx",
    "embedding_model.onnx": f"https://github.com/dscripka/openWakeWord/releases/download/{OPENWAKEWORD_RELEASE}/embedding_model.onnx",
    "melspectrogram.onnx": f"https://github.com/dscripka/openWakeWord/releases/download/{OPENWAKEWORD_RELEASE}/melspectrogram.onnx",
}


class WakeWordModelPaths(NamedTuple):
    """Verified paths for the wake-word classifier and shared ONNX frontend."""

    wake_word: Path
    embedding: Path
    melspectrogram: Path


def _download_model(url: str, destination: Path) -> None:
    """Download one pinned model to a temporary file, verify it, then install it."""
    temporary = destination.with_name(destination.name + ".part")
    try:
        with requests.get(url, stream=True, timeout=(10, 30)) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        verify_model_file(str(temporary), filename=destination.name)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def ensure_wakeword_models(directory: str | Path | None = None) -> WakeWordModelPaths:
    """Return checksum-verified local model paths, downloading missing assets."""
    model_directory = Path(directory) if directory is not None else Path(models_dir()) / "wakeword"
    model_directory.mkdir(parents=True, exist_ok=True)

    paths = {name: model_directory / name for name in WAKE_WORD_FILES}
    for filename, url in WAKE_WORD_FILES.items():
        destination = paths[filename]
        try:
            verify_model_file(str(destination))
        except FileNotFoundError:
            pass
        except ChecksumError as error:
            logger.warning("Replacing invalid wake-word model %s: %s", filename, error)
            destination.unlink(missing_ok=True)

        if not destination.exists():
            logger.info("Downloading wake-word model %s", filename)
            _download_model(url, destination)

    return WakeWordModelPaths(
        wake_word=paths["hey_jarvis_v0.1.onnx"],
        embedding=paths["embedding_model.onnx"],
        melspectrogram=paths["melspectrogram.onnx"],
    )
