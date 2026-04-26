"""
Aira — Standalone Voice Assistant
=======================================
Pure voice pipeline (no browser needed):

    Say "Aira"  →  Speak your command  →  Hear the response

Run::

    python aira.py

Optional env vars (same as server.py):
    AIRA_DEVICE   cuda | cpu     (default: cuda)
    WHISPER_MODEL      medium         (default: medium)
    OLLAMA_MODEL       mistral        (default: mistral)

Press Ctrl+C to exit.
"""

from __future__ import annotations

import base64
import io
import os
import sys
import time

import numpy as np

# ── Path setup ────────────────────────────────────────────────────────────────

_ROOT_DIR    = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_ROOT_DIR, "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# ── Agent imports ─────────────────────────────────────────────────────────────

from agents.brain_agent   import BrainAgent, JARVIS_SYSTEM
from agents.listener_agent import ListenerAgent
from agents.voice_agent   import VoiceAgent
from agents.wake_agent    import WakeAgent

# ── Config ─────────────────────────────────────────────────────────────────────

_DEVICE       = os.getenv("AIRA_DEVICE", "cpu")
_WHISPER_MODEL = os.getenv("WHISPER_MODEL",   "medium")
_OLLAMA_MODEL  = os.getenv("OLLAMA_MODEL",    "mistral")
_SAMPLE_RATE   = 16_000

# ── Audio helpers ─────────────────────────────────────────────────────────────

def _record_until_silence(
    sample_rate: int,
    silence_sec: float = 1.5,
    energy_thresh: float = 0.015,
    max_sec: float = 12.0,
) -> np.ndarray | None:
    """
    Record from the microphone until silence is detected.

    Returns a float32 numpy array (values in [-1, 1]) or ``None`` if
    sounddevice is unavailable or no speech was captured.
    """
    try:
        import sounddevice as sd  # noqa: PLC0415
    except ImportError:
        print("[Record] 'sounddevice' not installed. pip install sounddevice")
        return None

    _CHUNK = 512             # ~32 ms at 16 kHz
    _SILENCE_CHUNKS = int(silence_sec * sample_rate / _CHUNK)
    _MAX_CHUNKS     = int(max_sec     * sample_rate / _CHUNK)

    chunks: list[np.ndarray] = []
    silence_count  = 0
    speech_started = False

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
        while True:
            block, _ = stream.read(_CHUNK)
            block = block.flatten()
            rms   = float(np.sqrt(np.mean(block ** 2)))

            if rms > energy_thresh:
                speech_started = True
                silence_count  = 0
                chunks.append(block)
            elif speech_started:
                chunks.append(block)
                silence_count += 1
                if silence_count >= _SILENCE_CHUNKS:
                    break

            if len(chunks) >= _MAX_CHUNKS:
                break

    if not chunks:
        return None
    return np.concatenate(chunks)


def _play_wav_b64(audio_b64: str) -> None:
    """Decode a Base64 audio string and play it via sounddevice."""
    try:
        import soundfile as sf  # noqa: PLC0415
        import sounddevice as sd  # noqa: PLC0415
    except ImportError:
        print("[Play] Install 'sounddevice' and 'soundfile' to hear responses.")
        return

    raw  = base64.b64decode(audio_b64)
    buf  = io.BytesIO(raw)

    try:
        data, sr = sf.read(buf)
    except Exception:
        buf.seek(0)
        try:
            from pydub import AudioSegment  # noqa: PLC0415
        except ImportError:
            print("[Play] Install 'pydub' and 'ffmpeg' to play MP3 voice output.")
            return

        segment = AudioSegment.from_file(buf)
        data = np.array(segment.get_array_of_samples())
        if segment.channels > 1:
            data = data.reshape((-1, segment.channels))
        if segment.sample_width == 1:
            data = data.astype(np.float32) / 128.0
        elif segment.sample_width == 2:
            data = data.astype(np.float32) / 32768.0
        else:
            data = data.astype(np.float32)
        sr = segment.frame_rate

    sd.play(data, samplerate=sr)
    sd.wait()


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 60)
    print("  Aira — Offline Voice Assistant (standalone)")
    print(f"  Device  : {_DEVICE}")
    print(f"  Whisper : {_WHISPER_MODEL}")
    print(f"  LLM     : {_OLLAMA_MODEL}")
    print("=" * 60)
    print("\n  Initialising agents …\n")

    listener     = ListenerAgent(model_size=_WHISPER_MODEL, device=_DEVICE)
    brain        = BrainAgent(model=_OLLAMA_MODEL)
    voice        = VoiceAgent(device=_DEVICE)
    wake         = WakeAgent()

    # Pre-warm the STT model so first response is fast
    print("  [Init] Pre-loading Whisper model …")
    listener._get_model()
    print("  [Init] Ready.\n")

    conversation: list[dict] = []   # rolling chat history

    print("  Say  'Aira'  to start a conversation.")
    print("  Press  Ctrl+C  to exit.\n")

    while True:
        try:
            # ── Phase 1: Wait for wake word ────────────────────────────────
            wake.detected.clear()
            wake.start()
            print("[Aira] Waiting for wake word …")
            wake.detected.wait()
            wake.stop()

            # ── Phase 2: Record the user's command ─────────────────────────
            print("[Aira] Wake word heard! Listening …")
            audio_np = _record_until_silence(_SAMPLE_RATE)

            if audio_np is None or len(audio_np) == 0:
                print("[Aira] No audio captured. Try again.\n")
                continue

            # ── Phase 3: Listener Agent (STT) ───────────────────────────────
            stt_result = listener.transcribe_array(audio_np)
            user_text  = stt_result.get("user_text", "").strip()

            if not user_text:
                print("[Aira] Couldn't understand. Please try again.\n")
                continue

            print(f"\n  [You]        {user_text}")

            # ── Phase 4: Brain Agent (LLM + intent) ─────────────────────────
            conversation.append({"role": "user", "content": user_text})

            brain_result = brain.think(
                user_text=user_text,
                system_prompt=JARVIS_SYSTEM,
                history=conversation[:-1],
            )
            reply  = brain_result.get("response", "")

            print(f"  [Aira]  {reply}\n")
            conversation.append({"role": "assistant", "content": reply})

            # Keep conversation history bounded
            if len(conversation) > 20:
                conversation = conversation[-20:]

            # ── Phase 6: Voice Agent (TTS) ───────────────────────────────────
            audio_b64, _ = voice.synthesize(text=reply, language_code="hi-IN")
            if audio_b64:
                _play_wav_b64(audio_b64)
            else:
                print("  [TTS] Audio synthesis failed (no audio output).")

        except KeyboardInterrupt:
            print("\n\n  [Aira] Shutting down. Alvida! 👋\n")
            break
        except Exception as exc:
            import traceback
            print(f"\n[Error] {exc}")
            traceback.print_exc()
            time.sleep(1)   # brief pause before retrying


if __name__ == "__main__":
    main()
