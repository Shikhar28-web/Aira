"""
SarvSathi — Fully Offline AI Assistant
=======================================
4-agent pipeline — no cloud APIs required.
Run: python server.py
Then open: http://127.0.0.1:5000
"""

import os
import sys
import re
import threading
import uuid
from glob import glob

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

# ── Make sure the backend package is importable ───────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from agents.listener_agent import ListenerAgent
from agents.brain_agent    import BrainAgent, JARVIS_SYSTEM
from agents.action_agent   import ActionAgent
from agents.voice_agent    import VoiceAgent
from agents.wake_agent     import WakeAgent

# ── Config from environment (all optional — sensible defaults) ────────────────
_DEVICE       = os.getenv("SARVSATHI_DEVICE",  "cpu")
_WHISPER_MODEL = os.getenv("WHISPER_MODEL",    "medium")
_OLLAMA_MODEL  = os.getenv("OLLAMA_MODEL",     "mistral")
_OLLAMA_URL    = os.getenv("OLLAMA_URL",       "http://localhost:11434")
_WAKE_ENABLED  = os.getenv("SARVSATHI_WAKE",   "true").lower() in {"1", "true", "yes"}
_PROFILE_TRANSCRIBE = os.getenv("SARVSATHI_PROFILE_TRANSCRIBE", "false").lower() in {"1", "true", "yes"}

# ── Initialise agents (models are lazy-loaded on first use) ───────────────────
_listener = ListenerAgent(model_size=_WHISPER_MODEL, device=_DEVICE)
_brain    = BrainAgent(model=_OLLAMA_MODEL, ollama_url=_OLLAMA_URL)
_action   = ActionAgent()
_voice    = VoiceAgent(device=_DEVICE)
_wake     = WakeAgent() if _WAKE_ENABLED else None

if _wake:
    _wake.start()

# Warm-load XTTS in background so voice cloning becomes available sooner.
threading.Thread(target=_voice._load_xtts_background, daemon=True).start()

# ── Flask app ─────────────────────────────────────────────────────────────────
_FRONTEND_DIR = os.path.join(_BACKEND_DIR, "..", "frontend")
_PROFILE_VOICES_DIR = os.path.join(_BACKEND_DIR, "assets", "profile_voices")
os.makedirs(_PROFILE_VOICES_DIR, exist_ok=True)

app = Flask(
    __name__,
    template_folder=os.path.abspath(os.path.join(_FRONTEND_DIR, "templates")),
    static_folder=os.path.abspath(os.path.join(_FRONTEND_DIR, "static")),
)

CORS(app, resources={r"/api/*": {"origins": "*"}})


# ── Utils ─────────────────────────────────────────────────────────────────────

def _strip_think(text: str) -> str:
    """Remove <think>…</think> reasoning blocks from model output."""
    if "<think" not in text.lower():
        return text
    return re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip() or text


# ─────────────────────────────────────────────────────────────────────────────
# Serve Frontend
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


# ─────────────────────────────────────────────────────────────────────────────
# /api/status  — health check
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({
        "ok": True,
        "device":        _DEVICE,
        "whisper_model": _WHISPER_MODEL,
        "llm_model":     _OLLAMA_MODEL,
        "wake_enabled":  _WAKE_ENABLED,
    })


# ─────────────────────────────────────────────────────────────────────────────
# /api/wake_status  — did the wake-word fire?
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/wake_status", methods=["GET"])
def wake_status():
    if _wake and _wake.detected.is_set():
        _wake.detected.clear()
        return jsonify({"detected": True})
    return jsonify({"detected": False})


# ─────────────────────────────────────────────────────────────────────────────
# /api/chat  — LLM (Ollama / Mistral, fully offline)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data          = request.get_json(force=True) or {}
        system_prompt = data.get("system", JARVIS_SYSTEM)
        messages      = data.get("messages", [])

        result = _brain.think(
            user_text=messages[-1]["content"] if messages else "",
            system_prompt=system_prompt,
            history=messages[:-1],
        )

        reply = _strip_think(result.get("response", ""))

        # Fire OS action in a background thread (non-blocking)
        action = result.get("action")
        if action:
            threading.Thread(
                target=_action.execute, args=(action,), daemon=True
            ).start()

        return jsonify({"reply": reply, "ok": True, "action": action})

    except Exception as e:
        print(f"[CHAT ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# /api/tts  — Text to Speech (Coqui XTTS v2, fully offline)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/tts", methods=["POST"])
def tts():
    try:
        data = request.get_json(force=True) or {}
        text = (data.get("text", "") or "")[:500]
        lang = data.get("language_code", "hi-IN")
        profile_voice_id = (data.get("profile_voice_id") or "").strip()

        speaker_wav = None
        if profile_voice_id:
            matches = glob(os.path.join(_PROFILE_VOICES_DIR, f"{profile_voice_id}.*"))
            if matches:
                speaker_wav = matches[0]

        audio_b64, cloned = _voice.synthesize(
            text,
            language_code=lang,
            speaker_wav=speaker_wav,
        )
        if not audio_b64:
            return jsonify({"ok": False, "error": "TTS returned no audio"}), 500

        return jsonify({
            "ok": True,
            "audio": audio_b64,
            "voice_cloned": bool(cloned),
            "profile_voice_loaded": bool(speaker_wav),
        })

    except Exception as e:
        print(f"[TTS ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# /api/stt  — Speech to Text (Faster-Whisper, fully offline)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/stt", methods=["POST"])
def stt():
    try:
        if "audio" not in request.files:
            return jsonify({"ok": False, "error": "No audio file provided"}), 400

        audio_file  = request.files["audio"]
        lang        = request.form.get("language_code", "hi-IN")
        audio_bytes = audio_file.read()

        result     = _listener.transcribe(audio_bytes, language_code=lang)
        transcript = result.get("user_text", "")
        return jsonify({"ok": True, "transcript": transcript})

    except Exception as e:
        print(f"[STT ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# /api/transcribe_profile_audio  — same as /api/stt (kept for UI compatibility)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/transcribe_profile_audio", methods=["POST"])
def transcribe_profile_audio():
    try:
        if "audio" not in request.files:
            return jsonify({"ok": False, "error": "No file"}), 400

        audio_file  = request.files["audio"]
        lang        = request.form.get("language_code", "hi-IN")
        original_name = (audio_file.filename or "profile.wav").strip()
        _, ext = os.path.splitext(original_name)
        ext = (ext or ".wav").lower()
        if len(ext) > 10 or not re.fullmatch(r"\.[a-z0-9]+", ext):
            ext = ".wav"

        audio_bytes = audio_file.read()

        profile_voice_id = uuid.uuid4().hex
        save_path = os.path.join(_PROFILE_VOICES_DIR, f"{profile_voice_id}{ext}")
        with open(save_path, "wb") as fh:
            fh.write(audio_bytes)

        transcript = ""
        warning = None
        if _PROFILE_TRANSCRIBE:
            try:
                result = _listener.transcribe(audio_bytes, language_code=lang)
                transcript = result.get("user_text", "")
            except Exception as stt_exc:
                # Voice cloning should still work even if STT dependencies are unavailable.
                warning = f"profile transcription unavailable: {stt_exc}"
                print(f"[PROFILE STT WARN] {stt_exc}")
        else:
            warning = "profile transcription skipped (SARVSATHI_PROFILE_TRANSCRIBE=false)"

        return jsonify({
            "ok": True,
            "transcript": transcript,
            "profile_voice_id": profile_voice_id,
            "warning": warning,
        })

    except Exception as e:
        print(f"[PROFILE STT ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# /api/action  — run an OS action directly
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/action", methods=["POST"])
def action():
    try:
        data        = request.get_json(force=True) or {}
        action_name = data.get("action", "")
        if not action_name:
            return jsonify({"ok": False, "error": "action field required"}), 400

        result = _action.execute(action_name)
        return jsonify(result)

    except Exception as e:
        print(f"[ACTION ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    host  = os.getenv("APP_HOST", "127.0.0.1")
    port  = int(os.getenv("APP_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}

    print("\n" + "=" * 60)
    print("  SarvSathi \u2014 Fully Offline AI Assistant")
    print(f"  Device        : {_DEVICE}")
    print(f"  Whisper model : {_WHISPER_MODEL}")
    print(f"  LLM           : {_OLLAMA_MODEL}  @  {_OLLAMA_URL}")
    print(f"  Wake word     : {'enabled' if _WAKE_ENABLED else 'disabled'}")
    print("=" * 60)
    print(f"\n  Open in browser: http://{host}:{port}")
    print("  Press Ctrl+C to stop\n")

    app.run(debug=debug, port=port, host=host, use_reloader=False)
