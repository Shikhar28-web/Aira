"""
Aira — Fully Offline AI Assistant
4-agent pipeline — no cloud APIs required.
Run: python server.py
Then open: http://127.0.0.1:5000
"""

import os
import sys
import json
import re
import uuid
import tempfile
import subprocess
from glob import glob

from flask import Flask, request, jsonify, render_template, send_from_directory, session
from flask_cors import CORS
from dotenv import load_dotenv
import requests

# ── Make sure the backend package is importable ───────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

_PROJECT_ROOT = os.path.abspath(os.path.join(_BACKEND_DIR, ".."))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
load_dotenv(os.path.join(_BACKEND_DIR, ".env"))

from agents.listener_agent import ListenerAgent
from agents.brain_agent    import BrainAgent, JARVIS_SYSTEM, hinglish_to_hindi
from agents.voice_agent    import VoiceAgent
from agents.wake_agent     import WakeAgent
from auth import auth_bp
from db import (
    init_db,
    save_message,
    get_chat_history,
    create_conversation,
    get_conversations,
    get_messages,
    get_companions,
    create_companion,
    get_companion_by_id,
    update_companion,
    delete_companion,
    get_messages_by_companion,
    get_companion_profile,
    upsert_companion_profile,
)

# ── Config from environment (all optional — sensible defaults) ────────────────
_DEVICE       = os.getenv("AIRA_DEVICE",  "cpu")
_WHISPER_MODEL = os.getenv("WHISPER_MODEL",    "medium")
_GROQ_MODEL    = os.getenv("GROQ_MODEL",       "llama-3.3-70b-versatile")
_GROQ_API_KEY  = os.getenv("GROQ_API_KEY",     "")
_GROQ_URL      = os.getenv("GROQ_URL",         "https://api.groq.com/openai/v1/chat/completions")
_WAKE_ENABLED  = os.getenv("AIRA_WAKE",   "true").lower() in {"1", "true", "yes"}
_PROFILE_TRANSCRIBE = os.getenv("AIRA_PROFILE_TRANSCRIBE", "false").lower() in {"1", "true", "yes"}

# ── Initialise agents (models are lazy-loaded on first use) ───────────────────
_listener = ListenerAgent(model_size=_WHISPER_MODEL, device=_DEVICE)
_brain    = BrainAgent(model=_GROQ_MODEL, groq_api_key=_GROQ_API_KEY)
_voice    = VoiceAgent(device=_DEVICE)
_wake     = WakeAgent() if _WAKE_ENABLED else None

# Warm up XTTS in background so clone readiness is available earlier.
_voice.preload_clone_model(blocking=False)

if _wake:
    _wake.start()

# ── Flask app ─────────────────────────────────────────────────────────────────
_FRONTEND_DIR = os.path.join(_BACKEND_DIR, "..", "frontend")
_PROFILE_VOICES_DIR = os.path.join(_BACKEND_DIR, "assets", "profile_voices")
os.makedirs(_PROFILE_VOICES_DIR, exist_ok=True)

_ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
_ELEVENLABS_DEFAULT_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
_ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()

app = Flask(
    __name__,
    template_folder=os.path.abspath(os.path.join(_FRONTEND_DIR, "templates")),
    static_folder=os.path.abspath(os.path.join(_FRONTEND_DIR, "static")),
)
app.config["SECRET_KEY"] = os.getenv("AIRA_SECRET_KEY", "aira-dev-secret")
app.register_blueprint(auth_bp)

CORS(app, resources={r"/api/*": {"origins": "*"}})


# ── Utils ─────────────────────────────────────────────────────────────────────

def _strip_think(text: str) -> str:
    """Remove <think>…</think> reasoning blocks from model output."""
    if "<think" not in text.lower():
        return text
    return re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip() or text


def _infer_relationship(companion_name: str) -> str:
    """Infer relationship label from companion name for better tone control."""
    low = (companion_name or "").strip().lower()
    if any(k in low for k in ["maa", "mummy", "mom", "mother"]):
        return "mother"
    if any(k in low for k in ["papa", "dad", "father"]):
        return "father"
    if any(k in low for k in ["didi", "behen", "sister"]):
        return "sister"
    if any(k in low for k in ["bhai", "brother", "bro"]):
        return "brother"
    if any(k in low for k in ["friend", "dost", "yaar"]):
        return "friend"
    return "loved one"


def _style_guideline(style: str) -> str:
    st = (style or "casual").strip().lower()
    if st == "formal":
        return "Use polite, respectful wording and clear sentence structure without slang."
    if st == "supportive":
        return "Sound gentle and emotionally present, validate feelings before giving advice."
    if st == "motivational":
        return "Be energizing and hopeful, with practical next steps and confidence-building tone."
    if st == "fun":
        return "Keep it playful and light while staying sensible, never childish or mocking."
    return "Use relaxed everyday wording like a close real person in conversation."


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE COMMUNICATION
# ─────────────────────────────────────────────────────────────────────────────
# 
# STEP 1: /api/chat
#   Input: user message (text)
#   Brain: Detects language, emotion, normalizes for LLM, generates response
#   Output: reply (UI display), emotion, action
#
# STEP 2: Frontend sends reply text to /api/tts
#   Input: text from reply (may be Roman Hinglish)
#   Server: _prepare_text_for_tts() converts Roman→Devanagari if needed
#   Voice: Receives normalized text, applies emotion prosody
#   Output: Base64 audio
#
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_tts_language_code(text: str, requested_lang: str) -> str:
    """
    Choose a better TTS language for mixed-script Hinglish text so cloned speech
    does not drift into a wrong language pronunciation.
    """
    req = (requested_lang or "hi-IN").strip()
    txt = (text or "").strip()
    if not txt:
        return req

    has_devanagari = bool(re.search(r"[\u0900-\u097F]", txt))
    ascii_letters = len(re.findall(r"[A-Za-z]", txt))

    if has_devanagari:
        return "hi-IN"

    # Roman-script Hindi/Hinglish is usually pronounced better with en pipeline in XTTS.
    if req == "hi-IN" and ascii_letters >= 4:
        return "en-IN"

    # For unsupported Indic language codes in XTTS, keep english for roman script input.
    if req in {"bn-IN", "ta-IN", "te-IN", "kn-IN", "ml-IN", "mr-IN", "gu-IN", "pa-IN"} and ascii_letters >= 4:
        return "en-IN"

    return req


def _prepare_text_for_tts(text: str, requested_lang: str) -> str:
    """
    Server-side TTS text normalization (last-mile conversio).
    
    This is a SAFETY NET for cases where frontend sends Roman Hinglish
    that needs Devanagari conversion for TTS. BrainAgent already handles
    Script conversions, but since frontend may send text directly, we
    keep this normalization as a backstop.
    
    NOTE: VoiceAgent._prepare_tts_text() handles PROSODY modulation
    (emotion-based speed, punctuation). This function handles SCRIPT
    conversion only.
    """
    txt = (text or "").strip()
    if not txt:
        return txt

    # Keep user-visible text script unchanged. Roman-to-Devanagari conversion
    # through ITRANS can produce unnatural tokens for casual Hinglish input.
    return txt


def _convert_profile_audio_to_wav(audio_bytes: bytes) -> bytes | None:
    """
    Convert arbitrary uploaded profile audio to mono WAV bytes.
    XTTS cloning is most reliable with WAV input.
    """
    in_path = None
    out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".input", delete=False) as f_in:
            f_in.write(audio_bytes)
            in_path = f_in.name
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_out:
            out_path = f_out.name

        # Preferred path: pydub (cleaner API).
        try:
            from pydub import AudioSegment  # noqa: PLC0415
            from pydub import effects  # noqa: PLC0415
            from pydub.silence import detect_nonsilent  # noqa: PLC0415

            seg = AudioSegment.from_file(in_path)
            # Trim long recordings to a compact, expressive chunk for better cloning.
            nonsilent = detect_nonsilent(seg, min_silence_len=250, silence_thresh=seg.dBFS - 16)
            if nonsilent:
                start = max(nonsilent[0][0] - 120, 0)
                end = min(nonsilent[-1][1] + 120, len(seg))
                seg = seg[start:end]

            # Keep 4s-18s window; too short/too long sample often hurts clone quality.
            if len(seg) > 18_000:
                seg = seg[:18_000]
            if len(seg) < 4_000:
                seg = seg + AudioSegment.silent(duration=(4_000 - len(seg)))

            seg = effects.normalize(seg)
            seg = seg.set_channels(1).set_frame_rate(24_000)
            seg.export(out_path, format="wav")
            with open(out_path, "rb") as fh:
                return fh.read()
        except Exception:
            pass

        # Fallback path: direct ffmpeg.
        subprocess.run(
            ["ffmpeg", "-y", "-i", in_path, "-t", "8", "-ar", "24000", "-ac", "1", out_path],
            check=True,
            capture_output=True,
        )
        with open(out_path, "rb") as fh:
            return fh.read()
    except Exception as exc:
        print(f"[PROFILE AUDIO WARN] WAV conversion failed: {exc}")
        return None
    finally:
        for p in [in_path, out_path]:
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass


def _profile_voice_metadata_path(profile_voice_id: str) -> str:
    return os.path.join(_PROFILE_VOICES_DIR, f"{profile_voice_id}.json")


def _write_profile_voice_metadata(profile_voice_id: str, metadata: dict[str, str]) -> None:
    meta_path = _profile_voice_metadata_path(profile_voice_id)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh)


def _create_elevenlabs_voice(sample_path: str, voice_name: str, description: str = "") -> str | None:
    if not _ELEVENLABS_API_KEY:
        return None
    if not os.path.exists(sample_path):
        return None

    try:
        with open(sample_path, "rb") as fh:
            files = [("files[]", (os.path.basename(sample_path), fh, "audio/wav"))]
            response = requests.post(
                f"{_ELEVENLABS_API_URL}/voices/add",
                headers={"xi-api-key": _ELEVENLABS_API_KEY},
                data={
                    "name": voice_name,
                    "description": description,
                    "remove_background_noise": "false",
                },
                files=files,
                timeout=60,
            )
        response.raise_for_status()
        payload = response.json() if response.content else {}
        voice_id = (payload.get("voice_id") or "").strip()
        return voice_id or None
    except Exception as exc:
        print(f"[ELEVENLABS VOICE WARN] clone creation failed: {exc}")
        return None


def _store_profile_voice_metadata(profile_voice_id: str, sample_path: str, voice_name: str, language_code: str, voice_type: str) -> dict[str, str]:
    backend = "xtts"
    metadata: dict[str, str] = {"backend": backend}

    voice_id = _create_elevenlabs_voice(
        sample_path=sample_path,
        voice_name=voice_name,
        description=f"Aira companion voice ({voice_type}, {language_code})",
    )
    if voice_id:
        metadata = {
            "backend": "elevenlabs",
            "voice_id": voice_id,
            "model_id": _ELEVENLABS_DEFAULT_MODEL,
        }

    _write_profile_voice_metadata(profile_voice_id, metadata)
    return metadata


def _sanitize_chat_messages(messages: list, max_messages: int = 12, max_chars: int = 420) -> list[dict]:
    """Keep only recent user/assistant turns with bounded content size."""
    if not isinstance(messages, list):
        return []

    out: list[dict] = []
    for msg in messages[-max_messages:]:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        out.append({"role": role, "content": content[:max_chars]})
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Serve Frontend
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/settings")
def settings_page():
    return render_template("settings.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


# ─────────────────────────────────────────────────────────────────────────────
# /api/status  — health check
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/status", methods=["GET"])
def status():
    active_model = (session.get("groq_model") or _GROQ_MODEL).strip()
    has_groq_key = bool((session.get("groq_api_key") or _GROQ_API_KEY).strip())
    return jsonify({
        "ok": True,
        "device":        _DEVICE,
        "whisper_model": _WHISPER_MODEL,
        "llm_model":     active_model,
        "groq_key_configured": has_groq_key,
        "wake_enabled":  _WAKE_ENABLED,
        "voice_clone_ready": _voice.is_clone_ready(),
        "voice_clone_backend": _voice.clone_backend(),
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
# /api/companion  — companion profile (one per user)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/companion", methods=["GET", "POST"])
def companion_profile():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "authentication required"}), 401

        if request.method == "GET":
            profile = get_companion_profile(user_id)
            return jsonify({"ok": True, "companion": profile})

        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        style = (data.get("style") or "casual").strip().lower()
        language = (data.get("language") or "hinglish").strip().lower()

        if not name:
            return jsonify({"ok": False, "error": "name is required"}), 400
        if style not in {"casual", "formal", "supportive", "motivational"}:
            return jsonify({"ok": False, "error": "invalid style"}), 400

        profile = upsert_companion_profile(
            user_id=user_id,
            name=name,
            style=style,
            language=language,
        )
        return jsonify({"ok": True, "companion": profile})
    except Exception as e:
        print(f"[COMPANION ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/companions", methods=["GET", "POST"])
def companions():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "authentication required"}), 401

        if request.method == "GET":
            rows = get_companions(user_id)
            return jsonify({"ok": True, "companions": [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "style": c.get("style"),
                    "language": c.get("language"),
                    "voice_type": c.get("voice_type") or "female",
                    "profile_voice_id": c.get("profile_voice_id"),
                }
                for c in rows
            ]})

        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        style = (data.get("style") or "casual").strip().lower()
        language = (data.get("language") or "hinglish").strip().lower()
        voice_type = (data.get("voice_type") or "female").strip().lower()
        profile_voice_id = (data.get("profile_voice_id") or "").strip() or None

        if not name:
            return jsonify({"ok": False, "error": "name is required"}), 400
        if style not in {"casual", "formal", "supportive", "motivational", "fun"}:
            return jsonify({"ok": False, "error": "invalid style"}), 400
        if voice_type not in {"female", "male"}:
            return jsonify({"ok": False, "error": "invalid voice_type"}), 400

        profile = create_companion(
            user_id=user_id,
            name=name,
            style=style,
            language=language,
            voice_type=voice_type,
            profile_voice_id=profile_voice_id,
        )
        return jsonify({
            "ok": True,
            "companion": {
                "id": profile.get("id"),
                "name": profile.get("name"),
                "style": profile.get("style"),
                "language": profile.get("language"),
                "voice_type": profile.get("voice_type") or "female",
                "profile_voice_id": profile.get("profile_voice_id"),
            },
        }), 201
    except Exception as e:
        print(f"[COMPANIONS ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/companions/<int:companion_id>", methods=["PUT", "DELETE"])
def companion_by_id(companion_id: int):
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "authentication required"}), 401

        existing = get_companion_by_id(user_id, companion_id)
        if not existing:
            return jsonify({"ok": False, "error": "companion not found"}), 404

        if request.method == "DELETE":
            ok = delete_companion(user_id, companion_id)
            return jsonify({"ok": bool(ok)})

        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        style = (data.get("style") or existing.get("style") or "casual").strip().lower()
        language = (data.get("language") or existing.get("language") or "hinglish").strip().lower()
        voice_type = (data.get("voice_type") or existing.get("voice_type") or "female").strip().lower()
        profile_voice_id = data.get("profile_voice_id", existing.get("profile_voice_id"))
        profile_voice_id = (profile_voice_id or "").strip() or None

        if not name:
            return jsonify({"ok": False, "error": "name is required"}), 400
        if style not in {"casual", "formal", "supportive", "motivational", "fun"}:
            return jsonify({"ok": False, "error": "invalid style"}), 400
        if voice_type not in {"female", "male"}:
            return jsonify({"ok": False, "error": "invalid voice_type"}), 400

        row = update_companion(
            user_id=user_id,
            companion_id=companion_id,
            name=name,
            style=style,
            language=language,
            voice_type=voice_type,
            profile_voice_id=profile_voice_id,
        )
        return jsonify({"ok": True, "companion": row})
    except Exception as e:
        print(f"[COMPANION BY ID ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/companions/<int:companion_id>/voice", methods=["POST"])
def companion_voice_upload(companion_id: int):
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "authentication required"}), 401

        existing = get_companion_by_id(user_id, companion_id)
        if not existing:
            return jsonify({"ok": False, "error": "companion not found"}), 404

        if "audio" not in request.files:
            return jsonify({"ok": False, "error": "No file"}), 400

        audio_file = request.files["audio"]
        lang = request.form.get("language_code", "hi-IN")
        audio_bytes = audio_file.read()

        normalized_wav = _convert_profile_audio_to_wav(audio_bytes)
        audio_to_store = normalized_wav or audio_bytes
        stored_ext = ".wav" if normalized_wav else ".bin"

        profile_voice_id = uuid.uuid4().hex
        save_path = os.path.join(_PROFILE_VOICES_DIR, f"{profile_voice_id}{stored_ext}")
        with open(save_path, "wb") as fh:
            fh.write(audio_to_store)

        _store_profile_voice_metadata(
            profile_voice_id=profile_voice_id,
            sample_path=save_path,
            voice_name=existing.get("name") or "Companion",
            language_code=lang,
            voice_type=existing.get("voice_type") or "female",
        )

        transcript = ""
        warning = None
        if _PROFILE_TRANSCRIBE:
            try:
                result = _listener.transcribe(audio_bytes, language_code=lang)
                transcript = result.get("user_text", "")
            except Exception as stt_exc:
                warning = f"profile transcription unavailable: {stt_exc}"
                print(f"[COMPANION VOICE STT WARN] {stt_exc}")
        else:
            warning = "profile transcription skipped (AIRA_PROFILE_TRANSCRIBE=false)"

        row = update_companion(
            user_id=user_id,
            companion_id=companion_id,
            name=existing.get("name") or "Companion",
            style=existing.get("style") or "casual",
            language=existing.get("language") or "hinglish",
            voice_type=existing.get("voice_type") or "female",
            profile_voice_id=profile_voice_id,
        )
        return jsonify({
            "ok": True,
            "companion": row,
            "transcript": transcript,
            "profile_voice_id": profile_voice_id,
            "warning": warning,
        })
    except Exception as e:
        print(f"[COMPANION VOICE ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# /api/conversations  — list and create chat threads
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/conversations", methods=["GET"])
def conversations_list():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "authentication required"}), 401
        rows = get_conversations(user_id)
        return jsonify({"ok": True, "conversations": [{"id": r["id"], "title": r["title"]} for r in rows]})
    except Exception as e:
        print(f"[CONVERSATIONS ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/conversations/new", methods=["POST"])
def conversations_new():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "authentication required"}), 401
        data = request.get_json(force=True) or {}
        title = (data.get("title") or "New Chat").strip() or "New Chat"
        conversation_id = create_conversation(user_id, title)
        return jsonify({"ok": True, "conversation_id": conversation_id, "title": title})
    except Exception as e:
        print(f"[CONVERSATION NEW ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/messages/<int:companion_id>", methods=["GET"])
def companion_messages(companion_id: int):
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "authentication required"}), 401

        if not any(c.get("id") == companion_id for c in get_companions(user_id)):
            return jsonify({"ok": False, "error": "invalid companion for user"}), 403

        messages = get_messages_by_companion(user_id, companion_id)
        return jsonify({"ok": True, "messages": messages})
    except Exception as e:
        print(f"[MESSAGES ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# /api/chat  — LLM (Ollama / Mistral, fully offline)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Chat endpoint — Main entry to the brain pipeline.
    
    REQUEST:
    {
        "messages": [
            {"role": "user", "content": "User message"},
            ...history...
        ],
        "system": "Custom system prompt (optional)"
    }
    
    PIPELINE (in BrainAgent.think()):
    1. Receive text
    2. Detect language (Hindi/Hinglish/English)
    3. Normalize for LLM (Rom→Deva if Hinglish)
    4. Detect emotion
    5. SAFETY CHECK (suicide prevention)
    6. Action detection + Deterministic paths
    7. LLM call (if no match)
    8. Response handling + Format preservation
    9. Return structured response
    
    RESPONSE:
    {
        "ok": true,
        "reply": "User-visible response text",
        "action": "system_command_or_null"
    }
    """
    try:
        data          = request.get_json(force=True) or {}
        system_prompt = data.get("system", JARVIS_SYSTEM)
        messages      = _sanitize_chat_messages(data.get("messages", []))

        # New simple payload support: { companion_id, message }
        direct_message = (data.get("message") or "").strip()

        # Fallback to legacy payload support using messages array.
        user_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                user_idx = i
                break

        if direct_message:
            user_text = direct_message
            history = []
        else:
            if user_idx < 0:
                return jsonify({"ok": False, "error": "No user message provided"}), 400
            user_text = messages[user_idx]["content"]
            history = messages[:user_idx]

        companion_id_raw = data.get("companion_id")
        try:
            companion_id = int(companion_id_raw) if companion_id_raw not in {None, "", "null"} else None
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid companion_id"}), 400
        user_id = session.get("user_id")

        if user_id and not companion_id:
            return jsonify({"ok": False, "error": "companion_id is required"}), 400

        selected_companion = None
        if user_id and companion_id:
            companions = get_companions(user_id)
            for c in companions:
                if c.get("id") == companion_id:
                    selected_companion = c
                    break
            if not selected_companion:
                return jsonify({"ok": False, "error": "invalid companion for user"}), 403

        # If selected companion exists, inject persona into system prompt.
        if selected_companion:
            companion_name = (selected_companion.get("name") or "Companion").strip()
            companion_style = (selected_companion.get("style") or "casual").strip().lower()
            preferred_language = (selected_companion.get("language") or "hinglish").strip().lower()
            relationship = _infer_relationship(companion_name)
            nickname = (session.get("username") or "dost").strip() or "dost"
            tone_rule = _style_guideline(companion_style)
            system_prompt = (
                f"{system_prompt}\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "COMPANION PERSONA\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"You are playing the role of: {companion_name} ({relationship} of the user).\n"
                f"Personality style: {companion_style}\n"
                f"Preferred language: {preferred_language}\n"
                f"Always address the user as: \"{nickname}\"\n\n"
                f"Tone guideline: {tone_rule}\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "ABSOLUTE GROUNDING RULES — NON-NEGOTIABLE:\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "RULE 1: You ONLY know what the user explicitly tells you in THIS conversation.\n"
                "RULE 2: NEVER invent, guess or fabricate ANY specific fact about:\n"
                "  - People's health, illness, medical events, doctor visits\n"
                "  - What someone said, did, ate, bought, felt or experienced\n"
                "  - Family situations or events the user has NOT described to you\n"
                "RULE 3: When you don't know something the user asks about:\n"
                "  → ASK them. Don't make up an answer.\n"
                "RULE 4: You can be warm, caring, and supportive WITHOUT inventing details.\n"
                "\n"
                "━━ FEW-SHOT EXAMPLES (follow this pattern exactly) ━━\n"
                "\n"
                "WRONG (hallucination — never do this):\n"
                "  User: 'q mummy ko kya hua?'\n"
                "  BAD reply: 'Usne toh sir ka dard hua tha, doctor ne injection di.' ← INVENTED!\n"
                "\n"
                "CORRECT (ask, don't invent):\n"
                "  User: 'q mummy ko kya hua?'\n"
                "  GOOD reply: 'Tune bataya nahi beta, kya hua usse? Sab theek toh hai?'\n"
                "\n"
                "WRONG (hallucination — never do this):\n"
                "  User: 'bhai kaise hai?'\n"
                "  BAD reply: 'Bhaiya bahut achha hai, kal cricket khela usne.' ← INVENTED!\n"
                "\n"
                "CORRECT (honest, grounded):\n"
                "  User: 'bhai kaise hai?'\n"
                "  GOOD reply: 'Usne tujhe kuch bataya? Main yahan tha nahi, tu hi bata.'\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )

        requested_groq_key = (data.get("groq_api_key") or "").strip()
        requested_groq_model = (data.get("groq_model") or "").strip()

        # Allow each user/browser session to provide their own Groq key/model.
        if requested_groq_key:
            session["groq_api_key"] = requested_groq_key
        if requested_groq_model:
            session["groq_model"] = requested_groq_model

        active_groq_key = (session.get("groq_api_key") or _GROQ_API_KEY).strip()
        active_groq_model = (session.get("groq_model") or _GROQ_MODEL).strip()

        brain = BrainAgent(
            model=active_groq_model,
            groq_api_key=active_groq_key,
            groq_url=_GROQ_URL,
        )

        # Call brain agent with structured pipeline
        result = brain.think(
            user_text=user_text,
            system_prompt=system_prompt,
            history=history,
            user_id=user_id,
            companion_id=companion_id,
        )

        reply = _strip_think(result.get("response", ""))
        emotion = result.get("emotion", "neutral")

        # Persist user + assistant turns when an authenticated user exists.
        if user_id:
            save_message(
                user_id=user_id,
                companion_id=companion_id,
                role="user",
                message=user_text,
                emotion=emotion,
            )
            save_message(
                user_id=user_id,
                companion_id=companion_id,
                role="assistant",
                message=reply,
                emotion=emotion,
            )

        # OS actions are disabled; always return null action.
        action = None

        return jsonify({"reply": reply, "ok": True, "action": action})

    except Exception as e:
        print(f"[CHAT ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# /api/history  — Last 20 chat messages for current user + companion
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/history", methods=["GET"])
def history():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "authentication required"}), 401

        companion_id_raw = request.args.get("companion_id")
        companion_id = int(companion_id_raw) if companion_id_raw not in {None, "", "null"} else None

        messages = get_chat_history(user_id=user_id, companion_id=companion_id)
        return jsonify({"ok": True, "messages": messages[-20:]})
    except ValueError:
        return jsonify({"ok": False, "error": "invalid companion_id"}), 400
    except Exception as e:
        print(f"[HISTORY ERROR] {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# /api/tts  — Text to Speech (ElevenLabs clone optional, XTTS fallback)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/tts", methods=["POST"])
def tts():
    """
    Text-to-speech synthesis endpoint.
    
    REQUEST:
    {
        "text": "Response text",
        "language_code": "hi-IN" (optional, default hi-IN),
        "emotion": "neutral" (optional: sadness, fear, anger, joy, neutral),
        "profile_voice_id": "custom_voice_id" (optional)
    }
    
    PROCESS:
    1. Normalize text script (Roman→Devanagari if needed)
    2. Resolve TTS language (for proper XTTS pronunciation)
    3. Synthesize with emotion-aware prosody
    4. Return Base64 audio
    
    RESPONSE:
    {
        "ok": true,
        "audio": "base64_wav",
        "voice_cloned": bool,
        "tts_language_used": "hi-IN"
    }
    """
    try:
        data = request.get_json(force=True) or {}
        text = (data.get("text", "") or "")[:500]  # Cap at 500 chars
        lang = data.get("language_code", "hi-IN")
        emotion = data.get("emotion", "neutral")
        speaker = (data.get("speaker") or "").strip()
        profile_voice_id = (data.get("profile_voice_id") or "").strip()

        # Normalize text (script conversion if needed)
        tts_text = _prepare_text_for_tts(text, lang)
        
        # Resolve best TTS language for pronunciation
        resolved_lang = _resolve_tts_language_code(tts_text, lang)
        
        # Load custom voice if provided
        speaker_wav = None
        if profile_voice_id:
            matches = glob(os.path.join(_PROFILE_VOICES_DIR, f"{profile_voice_id}.*"))
            preferred_audio_exts = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".webm", ".mp4", ".bin"}
            for match in matches:
                ext = os.path.splitext(match)[1].lower()
                if ext in preferred_audio_exts and ext != ".json":
                    speaker_wav = match
                    break
            if not speaker_wav:
                speaker_wav = next((match for match in matches if not match.lower().endswith(".json")), None)

        # Synthesize with emotion-aware prosody
        audio_b64, cloned = _voice.synthesize(
            tts_text,
            language_code=resolved_lang,
            speaker=speaker,
            speaker_wav=speaker_wav,
            emotion=emotion,
        )
        if not audio_b64:
            return jsonify({"ok": False, "error": "TTS returned no audio"}), 500

        return jsonify({
            "ok": True,
            "audio": audio_b64,
            "voice_cloned": bool(cloned),
            "profile_voice_loaded": bool(speaker_wav),
            "clone_ready": _voice.is_clone_ready(),
            "tts_language_used": resolved_lang,
            "audio_mime": _voice.last_audio_mime(),
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
        audio_bytes = audio_file.read()
        normalized_wav = _convert_profile_audio_to_wav(audio_bytes)
        audio_to_store = normalized_wav or audio_bytes
        stored_ext = ".wav" if normalized_wav else ".bin"

        profile_voice_id = uuid.uuid4().hex
        save_path = os.path.join(_PROFILE_VOICES_DIR, f"{profile_voice_id}{stored_ext}")
        with open(save_path, "wb") as fh:
            fh.write(audio_to_store)

        # Extract voice_type from form data (sent from frontend)
        form_voice_type = (request.form.get("voice_type") or "female").strip().lower()

        _store_profile_voice_metadata(
            profile_voice_id=profile_voice_id,
            sample_path=save_path,
            voice_name=f"Aira Voice {profile_voice_id[:6]}",
            language_code=lang,
            voice_type=form_voice_type,
        )

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
            warning = "profile transcription skipped (AIRA_PROFILE_TRANSCRIBE=false)"

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
# /api/action  — disabled (OS actions removed)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/action", methods=["POST"])
def action():
    return jsonify({
        "ok": False,
        "error": "OS action feature is disabled in this build",
    }), 403


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()

    host  = os.getenv("APP_HOST", "127.0.0.1")
    port  = int(os.getenv("APP_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}

    print("\n" + "=" * 60)
    print("  Aira \u2014 Fully Offline AI Assistant")
    print(f"  Device        : {_DEVICE}")
    print(f"  Whisper model : {_WHISPER_MODEL}")
    print(f"  LLM           : {_GROQ_MODEL}  @  {_GROQ_URL}")
    print(f"  Wake word     : {'enabled' if _WAKE_ENABLED else 'disabled'}")
    print("=" * 60)
    print(f"\n  Open in browser: http://{host}:{port}")
    print("  Press Ctrl+C to stop\n")

    app.run(debug=debug, port=port, host=host, use_reloader=False)
