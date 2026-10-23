"""Local wake-word detection and microphone ownership for wake-mode dictation."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional, Protocol

import numpy as np

from ..utils.wakeword_model_info import WakeWordModelPaths, ensure_wakeword_models

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16000
_FRAME_SAMPLES = 1280
_FRAME_BYTES = _FRAME_SAMPLES * 2
_CAPTURE_CHUNK_BYTES = 1024 * 2
_POST_TRIGGER_SECONDS = 0.5


class CaptureSource(Protocol):
    """Minimal audio-source interface shared by PortAudio and PipeWire."""

    audio: Any
    sample_rate: int

    def open(self, audio: Any = None) -> None: ...

    def read_chunk(self) -> bytes: ...

    def close(self) -> None: ...


class WakeWordDetector:
    """Run the local Hey Jarvis ONNX detector over mono 16 kHz PCM."""

    def __init__(
        self,
        model_paths: WakeWordModelPaths,
        threshold: float = 0.5,
        consecutive_frames: int = 2,
        model: Optional[Any] = None,
    ) -> None:
        if model is None:
            from openwakeword.model import Model

            model = Model(
                wakeword_models=[str(model_paths.wake_word)],
                inference_framework="onnx",
                embedding_model_path=str(model_paths.embedding),
                melspec_model_path=str(model_paths.melspectrogram),
            )
        self.model = model
        self.threshold = max(0.0, min(1.0, float(threshold)))
        self.consecutive_frames = max(1, int(consecutive_frames))
        self.model_name = Path(model_paths.wake_word).stem
        self._pending_audio = bytearray()
        self._matching_frames = 0

    def process_chunk(self, audio: bytes) -> bool:
        """Return True after the wake score clears threshold on consecutive frames."""
        self._pending_audio.extend(audio)
        while len(self._pending_audio) >= _FRAME_BYTES:
            frame = bytes(self._pending_audio[:_FRAME_BYTES])
            del self._pending_audio[:_FRAME_BYTES]
            scores = self.model.predict(np.frombuffer(frame, dtype=np.int16))
            score = scores.get(self.model_name)
            if score is None and len(scores) == 1:
                score = next(iter(scores.values()))
            if float(score or 0.0) >= self.threshold:
                self._matching_frames += 1
                if self._matching_frames >= self.consecutive_frames:
                    self._matching_frames = 0
                    return True
            else:
                self._matching_frames = 0
        return False

    def take_pending_audio(self) -> bytes:
        """Return the samples after the last complete KWS frame."""
        audio = bytes(self._pending_audio)
        self._pending_audio.clear()
        return audio

    def reset(self) -> None:
        """Clear rolling model features after a rejected or completed trigger."""
        self._pending_audio.clear()
        self._matching_frames = 0
        reset = getattr(self.model, "reset", None)
        if callable(reset):
            reset()


class WakeWordListener:
    """Own a capture source while idle and transfer it on a wake-word match."""

    def __init__(
        self,
        capture_source_factory: Callable[[], CaptureSource],
        on_wake: Callable[[CaptureSource, list[bytes]], bool],
        on_status: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        detector_factory: Optional[Callable[[WakeWordModelPaths], WakeWordDetector]] = None,
        threshold: float = 0.5,
        post_trigger_seconds: float = _POST_TRIGGER_SECONDS,
    ) -> None:
        self._capture_source_factory = capture_source_factory
        self._on_wake = on_wake
        self._on_status = on_status
        self._on_error = on_error
        self._detector_factory = detector_factory or (
            lambda paths: WakeWordDetector(paths, threshold=threshold)
        )
        self._post_trigger_bytes = max(1, int(post_trigger_seconds * _SAMPLE_RATE * 2))
        self._stop_event = threading.Event()
        self._source_lock = threading.Lock()
        self._source: Optional[CaptureSource] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        """Whether the listener worker is active."""
        thread = self._thread
        return thread is not None and thread.is_alive() and not self._stop_event.is_set()

    def start(self) -> bool:
        """Start the idle listener unless a previous worker is still shutting down."""
        thread = self._thread
        if thread is not None and thread.is_alive():
            return False
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="VocalinuxWakeWord",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self, timeout: float = 2.0) -> None:
        """Stop listening and close the active source to interrupt a blocked read."""
        self._stop_event.set()
        with self._source_lock:
            source = self._source
        if source is not None:
            try:
                source.close()
            except Exception:
                logger.debug("Could not close wake-word capture source", exc_info=True)
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    def _status(self, value: str) -> None:
        if self._on_status is not None:
            try:
                self._on_status(value)
            except Exception:
                logger.debug("Wake-word status callback failed", exc_info=True)

    def _capture_post_trigger(self, source: CaptureSource, pending: bytes) -> list[bytes]:
        audio = bytearray(pending)
        while len(audio) < self._post_trigger_bytes and not self._stop_event.is_set():
            audio.extend(source.read_chunk())

        if self._stop_event.is_set():
            return []

        chunks = []
        for offset in range(0, len(audio), _CAPTURE_CHUNK_BYTES):
            chunk = bytes(audio[offset : offset + _CAPTURE_CHUNK_BYTES])
            if len(chunk) < _CAPTURE_CHUNK_BYTES:
                chunk += bytes(_CAPTURE_CHUNK_BYTES - len(chunk))
            chunks.append(chunk)
        return chunks

    def _run(self) -> None:
        source: Optional[CaptureSource] = None
        failure: Optional[Exception] = None
        transferred = False
        try:
            self._status("loading")
            model_paths = ensure_wakeword_models()
            if self._stop_event.is_set():
                return
            detector = self._detector_factory(model_paths)
            if self._stop_event.is_set():
                return
            source = self._capture_source_factory()
            source.open()
            with self._source_lock:
                if self._stop_event.is_set():
                    return
                self._source = source
            self._status("listening")

            while not self._stop_event.is_set():
                chunk = source.read_chunk()
                if not chunk or not detector.process_chunk(chunk):
                    continue
                pending = detector.take_pending_audio()
                post_trigger = self._capture_post_trigger(source, pending)
                if self._stop_event.is_set():
                    break

                with self._source_lock:
                    if self._stop_event.is_set():
                        break
                    transferred = self._on_wake(source, post_trigger)
                    if transferred:
                        self._source = None
                        source = None
                        self._status("transferred")
                        return
                detector.reset()
        except Exception as error:
            failure = error
            if not self._stop_event.is_set():
                logger.exception("Wake-word listener failed")
                self._status("error")
                if self._on_error is not None:
                    try:
                        self._on_error(error)
                    except Exception:
                        logger.debug("Wake-word error callback failed", exc_info=True)
        finally:
            with self._source_lock:
                if self._source is source:
                    self._source = None
            if source is not None:
                try:
                    source.close()
                except Exception:
                    logger.debug("Could not close wake-word capture source", exc_info=True)
            if failure is None and not transferred:
                self._status("stopped")
