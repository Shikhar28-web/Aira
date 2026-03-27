"""
AGENT 4 — VOICE AGENT
======================
RESPONSIBILITY: Text-to-Speech synthesis ONLY.
Converts text reply into spoken audio using Coqui XTTS v2.

INPUT:
    text            (str)          - Response text to synthesize
    emotion         (str)          - Emotion detected by BrainAgent
    language_code   (str)          - Language code (hi-IN, en-IN, etc)

PROCESSING:
    1. Normalize text for TTS (convert Roman→Devanagari if Hindi)
    2. Apply emotion-based prosody modulation (speed, tone)
    3. Synthesize audio using XTTS v2 (or fallback: pyttsx3)
    4. Return Base64-encoded WAV string

OUTPUT:
    tuple(base64_audio_string, cloned_bool)

IMPORTANT DATA FLOW RULES:
- Do NOT modify or shape the response_text semantically
- Prosody modulation (speed, punctuation) is acceptable
- Script conversion (Roman→Devanagari) is acceptable for TTS input
- Return format must be Base64-encoded WAV (unchanged from Sarvam)

Fallback strategy
-----------------
XTTS v2 natively supports: en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh-cn, ja, hu, ko, **hi**

For unsupported codes (bn-IN, ta-IN, te-IN, kn-IN, ml-IN, mr-IN, gu-IN, pa-IN),
fallback to Hindi ("hi") or pyttsx3 if XTTS v2 unavailable.
"""

import base64
import io
import os
import subprocess
import tempfile
import threading
import time
import wave
import re

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


def _normalize_gender_hint(speaker: str | None) -> str | None:
    """Infer gender hint from incoming speaker string."""
    low = (speaker or "").strip().lower()
    if not low:
        return None
    if low in {"male", "man", "boy"}:
        return "male"
    if low in {"female", "woman", "girl"}:
        return "female"

    male_markers = {"karun", "hitesh", "abhilash", "arya", "male", "man"}
    female_markers = {"anushka", "manisha", "vidya", "female", "woman"}
    if any(m in low for m in male_markers):
        return "male"
    if any(f in low for f in female_markers):
        return "female"
    return None


def _pick_voice_name_by_gender(voice_names: list[str], gender_hint: str | None) -> str | None:
    """Pick a deterministic voice candidate by gender hint from available names."""
    if not voice_names:
        return None
    if gender_hint not in {"male", "female"}:
        return voice_names[0]

    names = [n for n in voice_names if isinstance(n, str) and n.strip()]
    if not names:
        return None

    male_tokens = ("male", "man", "boy", "karun", "hitesh", "abhilash", "arya")
    female_tokens = ("female", "woman", "girl", "anushka", "manisha", "vidya", "sarah", "anna")
    tokens = male_tokens if gender_hint == "male" else female_tokens

    for name in names:
        low = name.lower()
        if any(tok in low for tok in tokens):
            return name

    # Fallback so male/female still sound different when names are unknown.
    names_sorted = sorted(names, key=lambda v: v.lower())
    return names_sorted[-1] if gender_hint == "male" else names_sorted[0]


def _patch_torch_load_for_xtts() -> None:
    """
    Coqui XTTS checkpoints currently expect torch.load with full object loading.
    PyTorch 2.6 changed default to weights_only=True, which breaks these loads.
    For trusted local XTTS models, force weights_only=False unless explicitly set.
    """
    try:
        import torch  # noqa: PLC0415
    except Exception:
        return

    if getattr(torch, "_sarvsathi_xtts_torchload_patched", False):
        return

    original_load = torch.load

    def _patched_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_load(*args, **kwargs)

    torch.load = _patched_load
    torch._sarvsathi_xtts_torchload_patched = True


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
        speaker: str | None = None,
        speaker_wav: str | None = None,
        emotion: str = "neutral",
    ) -> tuple[str | None, bool]:
        """
        Synthesise *text* and return a Base64-encoded WAV string, or ``None``
        on complete failure.

        PIPELINE:
        1. Normalize text for TTS (prosody modulation)
        2. Synthesize with XTTS v2 (or fallback to pyttsx3)
        3. Return Base64 audio

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

        # STEP 1: Normalize text for TTS (emotion-based prosody)
        pause_text, speed = self._prepare_tts_text(text, emotion, language_code=language_code)
        print(f"[TTS] Emotion={emotion}, Language={language_code}, Speed={speed:.2f}")
        print(f"[TTS] Text={pause_text[:60]}..." if len(pause_text) > 60 else f"[TTS] Text={pause_text}")
        gender_hint = _normalize_gender_hint(speaker)

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
                    pause_text,
                    language_code,
                    speaker_wav=speaker_wav,
                    gender_hint=gender_hint,
                    speed=speed,
                )
            except Exception as exc:
                print(f"[VoiceAgent] XTTS error: {exc}. Falling back to pyttsx3.")
                fallback = self._pyttsx3_synthesize(pause_text, gender_hint=gender_hint)
                if fallback:
                    return fallback, False
                return self._windows_system_speech_synthesize(pause_text), False

        # XTTS not loaded yet — respond instantly with pyttsx3
        # and start loading XTTS in the background
        should_try_xtts = self._xtts_ok is None
        if self._xtts_ok is False and (time.time() - self._last_xtts_attempt_ts) > 120:
            should_try_xtts = True

        if should_try_xtts:
            self._xtts_ok = False   # prevent duplicate background loads
            self._last_xtts_attempt_ts = time.time()
            threading.Thread(target=self._load_xtts_background, daemon=True).start()

        audio = self._pyttsx3_synthesize(pause_text, gender_hint=gender_hint)
        if audio:
            return audio, False
        return self._windows_system_speech_synthesize(pause_text), False

    @staticmethod
    def _prepare_tts_text(text: str, emotion: str, language_code: str = "hi-IN") -> tuple[str, float]:
        """
        PROSODY MODULATION FOR TTS ONLY
        ===============================
        This is the SINGLE place where text shaping for TTS happens.
        
        INPUT:
        - text (str)         : Response text from BrainAgent
        - emotion (str)      : Emotion detected by BrainAgent
        - language_code (str): Language (hi-IN, en-IN, etc)
        
        OUTPUT:
        - tuple(modified_text, speed_multiplier)
        
        MODIFICATIONS:
        - Emotion-based speed modulation (language-aware)
        - For non-Hindi: optional emotional prefix ("I understand, ...")
        - For Hindi: no English prefixes (keep natural)
        - Minimal whitespace normalization only
        
        DO NOT:
        - Change semantic meaning
        - Alter response content significantly
        - Force artificial punctuation patterns
        """
        # Default settings
        speed = 1.0
        pause_text = (text or "").strip()
        is_hindi = (language_code or "").startswith("hi")

        # Keep Hindi modulation subtle; strong shifts make cloned output unnatural.
        if emotion == "sadness":
            speed = 0.95 if is_hindi else 0.92
            if not is_hindi:
                pause_text = "I understand, " + pause_text
        elif emotion == "fear":
            speed = 0.96 if is_hindi else 0.94
            if not is_hindi:
                pause_text = "It is okay, " + pause_text
        elif emotion == "anger":
            speed = 0.98 if is_hindi else 0.97
        elif emotion == "joy":
            speed = 1.03 if is_hindi else 1.05
            if not is_hindi:
                pause_text = "That is nice, " + pause_text

        # Minimal cleanup only; avoid forced ellipsis that degrades prosody.
        pause_text = " ".join(pause_text.split())
        return pause_text, speed

    def _load_xtts_blocking(self) -> None:
        """Load XTTS synchronously; used for first voice-clone request."""
        with VoiceAgent._xtts_lock:
            if VoiceAgent._xtts_model is not None:
                self._xtts_ok = True
                return
            try:
                _patch_torch_load_for_xtts()
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
                _patch_torch_load_for_xtts()
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
        gender_hint: str | None = None,
        speed: float = 1.0,
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

        # If model exposes built-in speaker names, use gender hint when clone is not requested.
        if not (speaker_wav and os.path.exists(speaker_wav)):
            speaker_names: list[str] = []
            try:
                if isinstance(getattr(model, "speakers", None), (list, tuple)):
                    speaker_names = [str(v) for v in getattr(model, "speakers")]
                elif isinstance(getattr(model, "speakers", None), dict):
                    speaker_names = [str(v) for v in getattr(model, "speakers").keys()]

                if not speaker_names:
                    manager = getattr(getattr(getattr(model, "synthesizer", None), "tts_model", None), "speaker_manager", None)
                    if manager is not None:
                        speakers_obj = getattr(manager, "speakers", None)
                        if isinstance(speakers_obj, dict):
                            speaker_names = [str(v) for v in speakers_obj.keys()]
                        elif isinstance(speakers_obj, (list, tuple)):
                            speaker_names = [str(v) for v in speakers_obj]
            except Exception:
                speaker_names = []

            picked = _pick_voice_name_by_gender(speaker_names, gender_hint)
            if picked:
                kwargs.pop("speaker_wav", None)
                kwargs["speaker"] = picked

        try:
            wav: list | np.ndarray = model.tts(**kwargs, speed=speed)
        except TypeError:
            # Older TTS builds may not expose speed; fallback safely.
            wav = model.tts(**kwargs)
        except Exception:
            # If speaker-name synthesis fails on this model, safely fallback to reference WAV route.
            if "speaker" in kwargs:
                kwargs.pop("speaker", None)
                kwargs["speaker_wav"] = speaker_ref
                try:
                    wav = model.tts(**kwargs, speed=speed)
                except TypeError:
                    wav = model.tts(**kwargs)
            else:
                raise
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
    def _pyttsx3_synthesize(text: str, gender_hint: str | None = None) -> str | None:
        tmp: str | None = None
        try:
            import pyttsx3  # noqa: PLC0415

            engine = pyttsx3.init()
            engine.setProperty("rate",   205)
            engine.setProperty("volume", 0.90)

            # Best-effort gender voice selection in fallback engine.
            voices = engine.getProperty("voices") or []
            if voices and gender_hint in {"male", "female"}:
                chosen_id = None
                for v in voices:
                    blob = f"{getattr(v, 'name', '')} {getattr(v, 'id', '')}".lower()
                    if gender_hint == "male" and re.search(r"\bmale\b|\bman\b", blob):
                        chosen_id = getattr(v, "id", None)
                        break
                    if gender_hint == "female" and re.search(r"\bfemale\b|\bwoman\b", blob):
                        chosen_id = getattr(v, "id", None)
                        break
                if chosen_id:
                    engine.setProperty("voice", chosen_id)

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
