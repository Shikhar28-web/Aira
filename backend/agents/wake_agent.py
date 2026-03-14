"""
WAKE AGENT
==========
Listens continuously in the background for the wake word **"SarvSathi"**
and sets a threading.Event when the phrase is detected.

Detection strategy
------------------
1. Read microphone in 100 ms chunks via ``sounddevice``.
2. Accumulate a 2-second sliding window.
3. When the RMS energy exceeds a threshold (speech detected), run
   Faster-Whisper *tiny* (CPU) on the buffered audio.
4. If "sarvsathi" (or a common misspelling) appears in the transcript,
   fire ``WakeAgent.detected``.

This requires no API keys, no internet, and no custom wake-word model.

Usage::

    agent = WakeAgent()
    agent.start()          # background thread
    agent.detected.wait()  # block until wake word heard
    agent.detected.clear() # reset for next detection
    agent.stop()
"""

import threading
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

# Words we accept as the wake word (covers ASR misspellings)
_WAKE_VARIANTS = frozenset(
    [
        "sarvsathi",
        "sarv sathi",
        "sarvsati",
        "sarv saathi",
        "sarvs athi",
        "sarvsaathi",
        "sarvssathi",
        "sarb sathi",   # common "v→b" ASR substitution
    ]
)

_SAMPLE_RATE    = 16_000   # Hz
_CHUNK_MS       = 100      # chunk duration (ms)
_CHUNK_FRAMES   = int(_SAMPLE_RATE * _CHUNK_MS / 1_000)
_WINDOW_SEC     = 2.0      # sliding detection window (s)
_WINDOW_FRAMES  = int(_SAMPLE_RATE * _WINDOW_SEC)
_ENERGY_THRESH  = 0.015    # RMS threshold to attempt transcription


class WakeAgent:
    """
    Background wake-word detector.

    Attributes:
        detected (threading.Event):  Set when wake word is heard.
                                     Caller must call ``.clear()`` after handling.
    """

    def __init__(
        self,
        wake_word: str = "sarvsathi",
        energy_threshold: float = _ENERGY_THRESH,
    ) -> None:
        self.wake_word       = wake_word.lower()
        self.energy_threshold = energy_threshold
        self.detected        = threading.Event()

        self._active  = False
        self._thread: threading.Thread | None = None
        self._model   = None   # lazy-loaded WhisperModel("tiny", "cpu")

    # ── Model ────────────────────────────────────────────────────────────────

    def _get_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel  # noqa: PLC0415

            print("[WakeAgent] Loading Whisper tiny (CPU) for wake-word …")
            self._model = WhisperModel("tiny", device="cpu", compute_type="int8")
            print("[WakeAgent] Wake model ready.")
        except Exception as exc:
            print(f"[WakeAgent] Could not load model: {exc}")
        return self._model

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start background listening (idempotent)."""
        if self._thread and self._thread.is_alive():
            return
        self._active = True
        self.detected.clear()
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="WakeAgent"
        )
        self._thread.start()
        print(f"[WakeAgent] Listening for '{self.wake_word}' …")

    def stop(self) -> None:
        """Stop background listening."""
        self._active = False

    # ── Internal loop ─────────────────────────────────────────────────────────

    def _listen_loop(self) -> None:
        try:
            import sounddevice as sd  # noqa: PLC0415
        except ImportError:
            print(
                "[WakeAgent] 'sounddevice' not installed – "
                "wake-word detection disabled.  pip install sounddevice"
            )
            return

        buffer = np.zeros(0, dtype=np.float32)

        try:
            with sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=_CHUNK_FRAMES,
            ) as stream:
                while self._active:
                    chunk, _ = stream.read(_CHUNK_FRAMES)
                    buffer = np.append(buffer, chunk.flatten())

                    # Keep only the last _WINDOW_FRAMES samples
                    if len(buffer) > _WINDOW_FRAMES:
                        buffer = buffer[-_WINDOW_FRAMES:]

                    # Only attempt transcription when energy is high enough
                    rms = float(np.sqrt(np.mean(buffer ** 2)))
                    if rms < self.energy_threshold:
                        continue

                    if self._contains_wake_word(buffer.copy()):
                        print("[WakeAgent] ✔ Wake word detected!")
                        self.detected.set()
                        buffer = np.zeros(0, dtype=np.float32)

        except Exception as exc:
            print(f"[WakeAgent] Stream error: {exc}")

    def _contains_wake_word(self, audio: np.ndarray) -> bool:
        model = self._get_model()
        if model is None:
            return False
        try:
            segments, _ = model.transcribe(
                audio,
                beam_size=1,
                language=None,   # auto-detect
                vad_filter=True,
            )
            transcript = " ".join(s.text for s in segments).lower().strip()
            if not transcript:
                return False
            # Check every accepted variant
            return any(v in transcript for v in _WAKE_VARIANTS)
        except Exception as exc:
            print(f"[WakeAgent] Transcription error: {exc}")
            return False
