"""
AGENT 1 — LISTENER AGENT
Converts audio (microphone / uploaded file) to text using
Faster-Whisper running locally on GPU (or CPU fallback).

Output schema:
    {"user_text": "transcribed text"}
"""

import os
import io
import wave
import tempfile
import threading

import numpy as np

# ── Language code mapping  (Sarvam-style → Whisper ISO-639-1) ─────────────────
LANG_MAP: dict[str, str] = {
    "hi-IN": "hi",
    "en-IN": "en",
    "bn-IN": "bn",
    "ta-IN": "ta",
    "te-IN": "te",
    "kn-IN": "kn",
    "ml-IN": "ml",
    "mr-IN": "mr",
    "gu-IN": "gu",
    "pa-IN": "pa",
}

# Audio magic-byte → file extension mapping
_MAGIC: list[tuple[bytes, str]] = [
    (b"RIFF", ".wav"),
    (b"\x1aE\xdf\xa3", ".webm"),   # EBML/WebM/MKV
    (b"OggS", ".ogg"),
    (b"fLaC", ".flac"),
    (b"\xff\xfb", ".mp3"),
    (b"\xff\xf3", ".mp3"),
    (b"\xff\xf2", ".mp3"),
    (b"ID3",  ".mp3"),
    (b"M4A",  ".m4a"),
]


def _guess_suffix(audio_bytes: bytes) -> str:
    for magic, ext in _MAGIC:
        if audio_bytes[: len(magic)] == magic:
            return ext
    return ".webm"   # browsers typically send WebM/Opus


class ListenerAgent:
    """
    Wraps Faster-Whisper for speech-to-text transcription.

    Usage::

        agent = ListenerAgent(model_size="medium", device="cuda")
        result = agent.transcribe(audio_bytes, language_code="hi-IN")
        # result == {"user_text": "..."}
    """

    def __init__(
        self,
        model_size: str = "medium",
        device: str = "cuda",
        compute_type: str = "float16",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._lock = threading.Lock()

    # ── Model loader (lazy, thread-safe) ──────────────────────────────────────

    def _get_model(self):
        """Return the loaded WhisperModel, loading it on first call."""
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is not None:
                return self._model

            from faster_whisper import WhisperModel  # noqa: PLC0415

            # Try GPU first; fall back to CPU int8
            for dev, ctype in [
                (self.device, self.compute_type),
                ("cpu", "int8"),
            ]:
                try:
                    print(
                        f"[ListenerAgent] Loading Whisper '{self.model_size}' "
                        f"on {dev} ({ctype}) …"
                    )
                    self._model = WhisperModel(
                        self.model_size, device=dev, compute_type=ctype
                    )
                    print("[ListenerAgent] Model loaded successfully.")
                    return self._model
                except Exception as exc:
                    print(f"[ListenerAgent] {dev} load failed: {exc}")

            raise RuntimeError("[ListenerAgent] Could not load Whisper on any device.")

    # ── Public API ─────────────────────────────────────────────────────────────

    def transcribe(self, audio_bytes: bytes, language_code: str | None = None) -> dict:
        """
        Transcribe raw audio bytes to text.

        Args:
            audio_bytes:   Raw audio (WebM, WAV, MP3, OGG, FLAC …)
            language_code: Sarvam-style lang code like ``"hi-IN"`` or ``None``
                           for auto-detection.

        Returns:
            ``{"user_text": "<transcribed text>"}``
        """
        whisper_lang = LANG_MAP.get(language_code) if language_code else None
        model = self._get_model()

        suffix = _guess_suffix(audio_bytes)
        temp_path: str | None = None
        wav_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fh:
                fh.write(audio_bytes)
                temp_path = fh.name

            text = self._run_whisper(model, temp_path, whisper_lang)

            # If transcription returned nothing, try re-encoding to WAV first
            if not text:
                wav_path = temp_path + ".converted.wav"
                if self._convert_to_wav(temp_path, wav_path):
                    text = self._run_whisper(model, wav_path, whisper_lang)

            return {"user_text": text}

        finally:
            for p in [temp_path, wav_path]:
                if p and os.path.exists(p):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

    def transcribe_array(
        self, audio_np: np.ndarray, language_code: str | None = None
    ) -> dict:
        """
        Transcribe a float32 numpy array (values in [-1, 1]) directly.
        Used by the standalone aira.py script.
        """
        whisper_lang = LANG_MAP.get(language_code) if language_code else None
        model = self._get_model()
        text = self._run_whisper(model, audio_np, whisper_lang)
        return {"user_text": text}

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _run_whisper(model, audio_source, language: str | None) -> str:
        try:
            segments, _ = model.transcribe(
                audio_source,
                language=language,
                vad_filter=True,
                beam_size=5,
                vad_parameters={"min_silence_duration_ms": 300},
            )
            return " ".join(seg.text for seg in segments).strip()
        except Exception as exc:
            print(f"[ListenerAgent] Transcription error: {exc}")
            return ""

    @staticmethod
    def _convert_to_wav(src: str, dst: str) -> bool:
        """Convert audio file to 16 kHz mono WAV using pydub or ffmpeg."""
        # pydub (depends on ffmpeg internally but wraps it nicely)
        try:
            from pydub import AudioSegment  # noqa: PLC0415

            seg = AudioSegment.from_file(src)
            seg = seg.set_frame_rate(16_000).set_channels(1)
            seg.export(dst, format="wav")
            return True
        except Exception:
            pass

        # Direct ffmpeg subprocess
        try:
            import subprocess  # noqa: PLC0415

            subprocess.run(
                ["ffmpeg", "-y", "-i", src, "-ar", "16000", "-ac", "1", dst],
                check=True,
                capture_output=True,
            )
            return True
        except Exception as exc:
            print(f"[ListenerAgent] Audio conversion failed: {exc}")
            return False
