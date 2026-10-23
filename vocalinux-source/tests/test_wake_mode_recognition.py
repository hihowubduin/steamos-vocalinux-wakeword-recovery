from __future__ import annotations

import struct
import sys
import threading
import time
from unittest.mock import MagicMock, Mock, patch

from vocalinux.common_types import RecognitionState
from vocalinux.speech_recognition.recognition_manager import SpeechRecognitionManager


def _manager() -> SpeechRecognitionManager:
    with (
        patch.object(SpeechRecognitionManager, "_init_vosk"),
        patch.object(SpeechRecognitionManager, "_init_whisper"),
        patch.object(SpeechRecognitionManager, "_init_whispercpp"),
        patch(
            "vocalinux.speech_recognition.recognition_manager.load_silero_vad", return_value=None
        ),
    ):
        manager = SpeechRecognitionManager(
            engine="whisper_cpp",
            model_size="small",
            language="en-us",
            defer_download=True,
            playback_duck=MagicMock(),
        )
    manager._model_initialized = True
    manager.model = MagicMock()
    return manager


class _FakeCaptureSource:
    requires_pyaudio = False
    sample_rate = 16000
    channels = 1
    downmix_channel = None
    audio = None

    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.stream = object()
        self.closed = False

    def open(self, _audio=None):
        pass

    def read_chunk(self):
        time.sleep(0.065)
        return next(self.chunks)

    def close(self):
        self.closed = True


def _run_auto_stop(chunks, timeout):
    manager = _manager()
    source = _FakeCaptureSource(chunks)
    manager._new_capture_source = lambda: source
    manager.silence_timeout = 0.05
    manager._wake_no_speech_timeout = timeout
    manager._recognition_mode = "wake_word"
    manager.state = RecognitionState.LISTENING
    manager.should_record = True
    manager.audio_thread = MagicMock()
    manager.audio_thread.is_alive.return_value = False
    manager.recognition_thread = None
    idle = threading.Event()
    manager.register_state_callback(
        lambda state: idle.set() if state == RecognitionState.IDLE else None
    )
    manager._enqueue_audio_segment = Mock()

    real_numpy = getattr(sys, "_vocalinux_real_numpy", None)
    with patch("vocalinux.speech_recognition.recognition_manager.play_stop_sound"):
        if real_numpy is None:
            manager._record_audio()
        else:
            with patch.dict(sys.modules, {"numpy": real_numpy}):
                manager._record_audio()
        assert idle.wait(2)

    return manager, source


def test_capture_stops_and_flushes_after_silence_follows_speech():
    speech = struct.pack("<h", 2000) * 1024
    silence = bytes(2048)
    manager, source = _run_auto_stop([speech, silence], timeout=5.0)

    assert source.closed
    assert manager.state == RecognitionState.IDLE
    manager._enqueue_audio_segment.assert_called_once()


def test_no_speech_timeout_returns_without_enqueuing_audio():
    silence = bytes(2048)
    manager, source = _run_auto_stop([silence, silence], timeout=0.1)

    assert source.closed
    assert manager.state == RecognitionState.IDLE
    manager._enqueue_audio_segment.assert_not_called()


def test_wake_auto_stop_reason_waits_for_speech_and_uses_configured_pauses():
    manager = _manager()
    manager._recognition_mode = "wake_word"
    manager.silence_timeout = 1.2
    manager._wake_no_speech_timeout = 5.0

    assert manager._wake_auto_stop_reason(False, 1.5, 4.99) is None
    assert manager._wake_auto_stop_reason(False, 0.0, 5.0) == "no command speech"
    assert manager._wake_auto_stop_reason(True, 1.2, 8.0) is None
    assert manager._wake_auto_stop_reason(True, 1.21, 8.0) == "silence"

    manager._recognition_mode = "toggle"
    assert manager._wake_auto_stop_reason(True, 9.0, 9.0) is None


def test_automatic_wake_stop_runs_outside_the_capture_thread():
    manager = _manager()
    manager.state = RecognitionState.LISTENING
    manager.should_record = True
    finished = threading.Event()
    stop_threads = []

    def stop():
        stop_threads.append(threading.current_thread())
        manager.should_record = False
        finished.set()

    manager.stop_recognition = stop
    manager._request_wake_auto_stop("silence")
    assert finished.wait(2)
    assert not manager.should_record
    assert stop_threads[0] is not threading.current_thread()

    manager._request_wake_auto_stop("duplicate")
    assert len(stop_threads) == 1


def test_wake_start_transfers_open_capture_and_preroll_to_audio_thread():
    manager = _manager()
    manager._refresh_language_from_layout = MagicMock()
    manager._arm_playback_duck = MagicMock()
    source = MagicMock()
    initial_audio = [b"\x00\x00" * 1024]
    threads = []

    class FakeThread:
        def __init__(self, target, kwargs=None, daemon=False, name=None):
            self.target = target
            self.kwargs = kwargs or {}
            self.daemon = daemon
            self.name = name
            threads.append(self)

        def start(self):
            pass

        def is_alive(self):
            return False

    with (
        patch("vocalinux.speech_recognition.recognition_manager.threading.Thread", FakeThread),
        patch("vocalinux.speech_recognition.recognition_manager.play_start_sound") as start_sound,
    ):
        assert manager.start_recognition_from_wake(source, initial_audio, no_speech_timeout=5.0)

    assert manager.state == RecognitionState.LISTENING
    assert manager._recognition_mode == "wake_word"
    assert threads[0].target == manager._record_audio
    assert threads[0].kwargs == {
        "capture_source": source,
        "capture_is_open": True,
        "initial_audio": initial_audio,
    }
    start_sound.assert_not_called()
