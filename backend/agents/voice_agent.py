"""
AGENT 4 — VOICE AGENT
======================
Converts the assistant's text reply into spoken audio using
Coqui XTTS v2 (GPU-accelerated, multilingual).

Falls back to pyttsx3 if the TTS library is not installed or a
synthesis error occurs.

Language support
----------------
XTTS v2 natively supports:
    en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh-cn, ja, hu, ko, **hi**

For unsupported Sarvam language codes (bn-IN, ta-IN, te-IN, kn-IN, ml-IN,
mr-IN, gu-IN, pa-IN) the voice agent falls back to Hindi ("hi") so XTTS v2
still works, or to pyttsx3 if XTTS v2 is unavailable.

Return value
------------
A Base64-encoded WAV string (same format the original Sarvam TTS returned),
so the browser frontend does not need any changes.
"""

import base64
import io
import os
import subprocess
import tempfile
import threading
import time
import wave

import numpy as np

# ── Language mapping  (Sarvam → XTTS v2 ISO) ─────────────────────────────────
_XTTS_LANG: dict[str, str] = {
    "hi-IN": "hi",
    "en-IN": "en",
    # Unsupported by XTTS v2 → fallback to Hindi
    "bn-IN": "hi",
    "ta-IN": "hi",
    "te-IN": "hi",
    "kn-IN": "hi",
    "ml-IN": "hi",
    "mr-IN": "hi",
    "gu-IN": "hi",
    "pa-IN": "hi",
}

_XTTS_SAMPLE_RATE = 24_000   # Hz (XTTS v2 native output rate)


class VoiceAgent:
    """
    Text-to-speech synthesis with GPU acceleration.

    Primary   : Coqui XTTS v2  (``pip install TTS``)
    Fallback  : pyttsx3         (bundled with most Python environments)

    XTTS v2 requires a short reference WAV for its voice clone mechanism.
    The agent auto-generates one using pyttsx3 on first run and caches it
    at  ``backend/assets/default_speaker.wav``.

    Usage::

        agent = VoiceAgent(device="cuda")
        b64_wav = agent.synthesize("Namaste!", language_code="hi-IN")
    """

    # Class-level model cache (shared across all instances)
    _xtts_model = None
    _xtts_lock  = threading.Lock()

    def __init__(self, device: str = "cuda") -> None:
        self.device = device
        self._xtts_ok: bool | None = None   # None = not yet probed
        self._last_xtts_attempt_ts: float = 0.0

        # Prepare assets directory
        self._assets_dir = os.path.join(
            os.path.dirname(__file__), "..", "assets"
        )
        os.makedirs(self._assets_dir, exist_ok=True)
        self._speaker_wav = os.path.join(self._assets_dir, "default_speaker.wav")

    # ── Public API ─────────────────────────────────────────────────────────

    def synthesize(
        self,
        text: str,
        language_code: str = "hi-IN",
        speaker: str | None = None,   # kept for API compatibility; unused
        speaker_wav: str | None = None,
    ) -> tuple[str | None, bool]:
        """
        Synthesise *text* and return a Base64-encoded WAV string, or ``None``
        on complete failure.

        Strategy
        --------
        * If XTTS v2 is already loaded → use it (best quality).
        * If XTTS v2 is still loading / not yet attempted → use pyttsx3
          immediately so the response is instant, then kick off XTTS loading
          in a background thread so future calls get the better model.
        * If XTTS v2 failed to load → always use pyttsx3.
        """
        text = text.strip()
        if not text:
            return None, False

        clone_requested = bool(speaker_wav and os.path.exists(speaker_wav))
        if clone_requested and VoiceAgent._xtts_model is None:
            # For clone requests, prefer a blocking XTTS load once so first
            # cloned reply is actually cloned instead of immediate fallback voice.
            self._load_xtts_blocking()

        # XTTS already loaded — use it
        if VoiceAgent._xtts_model is not None:
            try:
                return self._xtts_synthesize(
                    VoiceAgent._xtts_model,
                    text,
                    language_code,
                    speaker_wav=speaker_wav,
                )
            except Exception as exc:
                print(f"[VoiceAgent] XTTS error: {exc}. Falling back to pyttsx3.")
                fallback = self._pyttsx3_synthesize(text)
                if fallback:
                    return fallback, False
                return self._windows_system_speech_synthesize(text), False

        # XTTS not loaded yet — respond instantly with pyttsx3
        # and start loading XTTS in the background
        should_try_xtts = self._xtts_ok is None
        if self._xtts_ok is False and (time.time() - self._last_xtts_attempt_ts) > 120:
            should_try_xtts = True

        if should_try_xtts:
            self._xtts_ok = False   # prevent duplicate background loads
            self._last_xtts_attempt_ts = time.time()
            threading.Thread(target=self._load_xtts_background, daemon=True).start()

        audio = self._pyttsx3_synthesize(text)
        if audio:
            return audio, False
        return self._windows_system_speech_synthesize(text), False

    def _load_xtts_blocking(self) -> None:
        """Load XTTS synchronously; used for first voice-clone request."""
        with VoiceAgent._xtts_lock:
            if VoiceAgent._xtts_model is not None:
                self._xtts_ok = True
                return
            try:
                os.environ.setdefault("COQUI_TOS_AGREED", "1")
                from TTS.api import TTS  # noqa: PLC0415

                print("[VoiceAgent] Loading Coqui XTTS v2 for clone request …")
                m = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
                m.to(self.device)
                VoiceAgent._xtts_model = m
                self._xtts_ok = True
                print("[VoiceAgent] XTTS v2 loaded (blocking path).")
            except Exception as exc:
                print(f"[VoiceAgent] XTTS blocking load failed ({exc}).")
                self._xtts_ok = False

    def _load_xtts_background(self) -> None:
        """Load XTTS v2 in a background thread so the first TTS call isn't blocked."""
        with VoiceAgent._xtts_lock:
            if VoiceAgent._xtts_model is not None:
                self._xtts_ok = True
                return
            try:
                # Avoid interactive CPML prompt when running as a backend service.
                os.environ.setdefault("COQUI_TOS_AGREED", "1")
                from TTS.api import TTS  # noqa: PLC0415
                print("[VoiceAgent] Loading Coqui XTTS v2 in background …")
                m = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
                m.to(self.device)
                VoiceAgent._xtts_model = m
                self._xtts_ok = True
                print("[VoiceAgent] XTTS v2 loaded — future TTS calls will use it.")
            except Exception as exc:
                print(f"[VoiceAgent] XTTS v2 load failed ({exc}). Staying on pyttsx3.")
                self._xtts_ok = False

    def is_clone_ready(self) -> bool:
        """True when XTTS is loaded and clone synthesis is available."""
        return VoiceAgent._xtts_model is not None and self._xtts_ok is True

    # ── XTTS v2 ────────────────────────────────────────────────────────────

    # _get_xtts removed — loading is now handled by _load_xtts_background

    def _xtts_synthesize(
        self,
        model,
        text: str,
        language_code: str,
        speaker_wav: str | None = None,
    ) -> tuple[str | None, bool]:
        lang = _XTTS_LANG.get(language_code, "hi")

        speaker_ref = speaker_wav if speaker_wav and os.path.exists(speaker_wav) else self._speaker_wav

        # Ensure default reference speaker WAV exists
        if not os.path.exists(speaker_ref):
            if not self._generate_speaker_wav():
                raise RuntimeError("Cannot create default speaker WAV.")
            speaker_ref = self._speaker_wav

        kwargs = {
            "text": text,
            "speaker_wav": speaker_ref,
            "language": lang,
        }
        try:
            # Slightly faster speaking pace so cloned output feels less sluggish.
            wav: list | np.ndarray = model.tts(**kwargs, speed=1.28)
        except TypeError:
            # Older TTS builds may not expose speed; fallback safely.
            wav = model.tts(**kwargs)
        cloned = bool(speaker_wav and os.path.exists(speaker_wav))
        return _array_to_wav_b64(wav, _XTTS_SAMPLE_RATE), cloned

    def _generate_speaker_wav(self) -> bool:
        """
        Generate a short default-speaker WAV with pyttsx3.
        This reference audio is used by XTTS v2 to clone a neutral voice.
        """
        try:
            import pyttsx3  # noqa: PLC0415

            engine = pyttsx3.init()
            engine.setProperty("rate", 150)
            engine.save_to_file(
                "Hello, I am SarvSathi, your intelligent AI assistant.",
                self._speaker_wav,
            )
            engine.runAndWait()
            return os.path.exists(self._speaker_wav)
        except Exception as exc:
            print(f"[VoiceAgent] Speaker WAV generation failed: {exc}")
            return False

    # ── pyttsx3 fallback ────────────────────────────────────────────────────

    @staticmethod
    def _pyttsx3_synthesize(text: str) -> str | None:
        tmp: str | None = None
        try:
            import pyttsx3  # noqa: PLC0415

            engine = pyttsx3.init()
            engine.setProperty("rate",   205)
            engine.setProperty("volume", 0.90)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
                tmp = fh.name

            engine.save_to_file(text, tmp)
            engine.runAndWait()

            with open(tmp, "rb") as fh:
                return base64.b64encode(fh.read()).decode("utf-8")

        except Exception as exc:
            print(f"[VoiceAgent] pyttsx3 error: {exc}")
            return None
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    @staticmethod
    def _windows_system_speech_synthesize(text: str) -> str | None:
        """
        Windows-only fallback using .NET System.Speech via PowerShell.
        This keeps /api/tts functional when pyttsx3 is not installed.
        """
        if os.name != "nt":
            return None

        wav_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
                wav_path = fh.name

            ps_text = text.replace("'", "''")
            ps_wav = wav_path.replace("'", "''")
            script = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$s.Rate = 0; $s.Volume = 100; "
                f"$s.SetOutputToWaveFile('{ps_wav}'); "
                f"$s.Speak('{ps_text}'); "
                "$s.Dispose();"
            )

            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                check=True,
                capture_output=True,
                text=True,
            )

            if not os.path.exists(wav_path) or os.path.getsize(wav_path) == 0:
                return None

            with open(wav_path, "rb") as fh:
                return base64.b64encode(fh.read()).decode("utf-8")

        except Exception as exc:
            print(f"[VoiceAgent] Windows speech fallback failed: {exc}")
            return None
        finally:
            if wav_path and os.path.exists(wav_path):
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _array_to_wav_b64(audio, sample_rate: int) -> str:
    """Convert a float audio array (XTTS output) to a Base64 WAV string."""
    arr = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    pcm = (arr * 32_767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")
