from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import Mock, patch

from vocalinux.speech_recognition.wake_word import WakeWordDetector, WakeWordListener
from vocalinux.utils.wakeword_model_info import WakeWordModelPaths


class _ScoreModel:
    def __init__(self, scores):
        self.scores = iter(scores)
        self.reset_count = 0

    def predict(self, _audio):
        return {"hey_jarvis_v0.1": next(self.scores)}

    def reset(self):
        self.reset_count += 1


def _model_paths() -> WakeWordModelPaths:
    return WakeWordModelPaths(
        Path("hey_jarvis_v0.1.onnx"),
        Path("embedding_model.onnx"),
        Path("melspectrogram.onnx"),
    )


class _CaptureSource:
    def __init__(self, blocking: bool = False):
        self.opened = threading.Event()
        self.closed = threading.Event()
        self.blocking = blocking

    def open(self, _audio=None):
        self.opened.set()

    def read_chunk(self):
        if self.blocking:
            self.closed.wait(0.01)
        if self.closed.is_set():
            raise OSError("closed")
        return bytes(2048)

    def close(self):
        self.closed.set()


def test_detector_requires_consecutive_scores_and_preserves_post_frame_audio():
    model = _ScoreModel([0.7, 0.4, 0.7, 0.8])
    detector = WakeWordDetector(_model_paths(), threshold=0.5, model=model)
    frame = bytes(1280 * 2)
    trailing = b"\x01\x02\x03\x04"

    assert detector.process_chunk(frame * 4 + trailing)
    assert detector.take_pending_audio() == trailing


def test_detector_resets_model_state_and_partial_input():
    model = _ScoreModel([0.9])
    detector = WakeWordDetector(_model_paths(), model=model)
    assert not detector.process_chunk(b"\x00" * 1024)

    detector.reset()

    assert detector.take_pending_audio() == b""
    assert model.reset_count == 1


def test_listener_transfers_open_source_and_only_post_trigger_audio():
    source = _CaptureSource()
    transferred = threading.Event()
    captured = {}
    detector = Mock()
    detector.process_chunk.side_effect = [True]
    detector.take_pending_audio.return_value = b"\x01" * 32

    def on_wake(capture_source, initial_audio):
        captured["source"] = capture_source
        captured["initial_audio"] = initial_audio
        transferred.set()
        return True

    with patch(
        "vocalinux.speech_recognition.wake_word.ensure_wakeword_models",
        return_value=_model_paths(),
    ):
        listener = WakeWordListener(
            capture_source_factory=lambda: source,
            on_wake=on_wake,
            detector_factory=lambda _paths: detector,
        )
        assert listener.start()
        assert transferred.wait(2)
        listener._thread.join(timeout=2)

    assert captured["source"] is source
    assert captured["initial_audio"]
    assert all(len(chunk) == 2048 for chunk in captured["initial_audio"])
    assert not source.closed.is_set()
    source.close()


def test_listener_stop_closes_idle_capture_source_without_transcription():
    source = _CaptureSource(blocking=True)
    detector = Mock()
    detector.process_chunk.return_value = False
    on_wake = Mock(return_value=False)

    with patch(
        "vocalinux.speech_recognition.wake_word.ensure_wakeword_models",
        return_value=_model_paths(),
    ):
        listener = WakeWordListener(
            capture_source_factory=lambda: source,
            on_wake=on_wake,
            detector_factory=lambda _paths: detector,
        )
        assert listener.start()
        assert source.opened.wait(2)
        listener.stop()

    assert source.closed.is_set()
    on_wake.assert_not_called()


def test_listener_verifies_and_downloads_models_atomically(tmp_path):
    payload = b"pinned model bytes"
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = [payload]
    response.raise_for_status.return_value = None

    files = {
        "hey_jarvis_v0.1.onnx": "https://example.invalid/hey.onnx",
        "embedding_model.onnx": "https://example.invalid/embedding.onnx",
        "melspectrogram.onnx": "https://example.invalid/mel.onnx",
    }

    def verify_if_present(path, filename=None):
        if not Path(path).exists():
            raise FileNotFoundError(path)

    with (
        patch("vocalinux.utils.wakeword_model_info.WAKE_WORD_FILES", files),
        patch("vocalinux.utils.wakeword_model_info.requests.get", return_value=response),
        patch(
            "vocalinux.utils.wakeword_model_info.verify_model_file",
            side_effect=verify_if_present,
        ) as verify,
    ):
        from vocalinux.utils.wakeword_model_info import ensure_wakeword_models

        paths = ensure_wakeword_models(tmp_path)

    assert paths.wake_word.read_bytes() == payload
    assert paths.embedding.read_bytes() == payload
    assert paths.melspectrogram.read_bytes() == payload
    assert verify.call_count == 6
