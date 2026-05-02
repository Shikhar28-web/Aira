  # Aira (Aira)
Aira is a multilingual AI companion project with:
- a web app (Flask + vanilla JS),
- a standalone voice assistant mode,
- a local multi-agent pipeline.

Latest version is designed to run fully offline for core AI flow (STT -> LLM -> TTS), with optional wake-word detection and voice cloning.

## Latest Status (Current Work)

Current architecture in this repo:
- Agent 1: `ListenerAgent` (speech-to-text)
- Agent 2: `BrainAgent` (local LLM reasoning + intent detection)
- Agent 3: `VoiceAgent` (text-to-speech + optional voice cloning)
- `WakeAgent` (always-listening wake phrase: "Aira")
- SQLite data layer: `backend/db.py` (users, companions, chats)
  - Companion-based message history (messages linked by `companion_id`)
  - Conversation-thread helpers may still exist for backward compatibility
- Auth layer: `backend/auth.py` (register/login with bcrypt + Flask session)

Main backend entrypoint:
- `backend/server.py`

Standalone voice pipeline entrypoint:
- `aira.py`

Frontend:
- `frontend/templates/index.html`
- `frontend/static/app.js`
- `frontend/static/style.css`

## Models Used (All So Far + Latest)

## LLM Names (One Place)

Current (offline, Ollama):
- web default: `qwen2.5:7b-instruct` (in `backend/server.py`)
- standalone default: `mistral` (in `aira.py`)
- BrainAgent fallback order: `qwen2.5:7b-instruct` → `mistral` → `llama3.1:8b` → `phi3`

Used earlier (legacy cloud stack):
- `gemini-2.5-flash`
- `sarvam-m`

Also supported in BrainAgent with Ollama (if installed locally):
- `phi3`
- `llama3`

### A) Latest / current model stack (offline-first)

1. STT (speech-to-text)
- Engine: Faster-Whisper
- Default model: `medium` (configurable via `WHISPER_MODEL`)
- Wake-word detector model: Faster-Whisper `tiny` on CPU inside `WakeAgent`

2. LLM (chat/brain)
- Runtime: Ollama
- Current default model in web backend: `qwen2.5:7b-instruct` (via `OLLAMA_MODEL`)
- Standalone script default: `mistral`
- LLM responses are collected via streaming chunks in `BrainAgent` for lower perceived latency
- Short-term in-memory conversation history is used (recent turns only) to improve context continuity
- Brain agent is compatible with other Ollama models too (for example Llama/Phi family if available locally)

3. TTS (speech synthesis)
- Primary: ElevenLabs instant voice cloning when `ELEVENLABS_API_KEY` is set
- Fallback: Coqui XTTS v2 (`tts_models/multilingual/multi-dataset/xtts_v2`)
- Backup fallbacks: `pyttsx3`, then Windows System.Speech fallback
- Voice cloning still works offline through XTTS when the cloud API is unavailable

### B) Earlier model stack used in previous versions (legacy)

This project previously used cloud APIs (as documented in older README/workflow):
- Gemini: `gemini-2.5-flash` (chat)
- Sarvam chat model: `sarvam-m`
- Sarvam TTS: `bulbul:v2`
- Sarvam STT: `saarika:v2.5`

The current codebase has moved to local/offline-first agents and Ollama/Whisper/XTTS pipeline.

## Features Implemented Till Now

- Persona-based conversation setup (name, relation, style, phrases, nickname)
- Conditional onboarding from landing page:
  - Login is requested only when user clicks Get Started
  - New users (no companions) go through full persona setup
  - Returning users go directly to chat with saved companions in sidebar
- Add Companion now uses the same full persona setup flow
- Companion management in chat sidebar:
  - Edit companion name/style/language/voice type
  - Upload or replace companion voice sample
  - Delete companion directly from chat UI
- Text chat and voice chat UI
- Stop-audio control in chat header to halt current TTS playback
- Multilingual UI modes (`en`, `hi`, `hinglish`)
- Speech-to-text transcription endpoint
- Text-to-speech response endpoint
- Profile voice sample upload and normalization for cloning
- Wake-word trigger support ("Aira")
- Standalone always-on voice assistant loop (without browser)
- Health/status endpoint exposing active model settings

## API Endpoints (Current Backend)

- `GET /api/status`
  - Returns health and runtime config (`device`, whisper model, LLM model, wake enabled, clone ready)

- `GET /api/wake_status`
  - Returns whether wake word has been detected

- `POST /api/chat`
  - Input JSON: `system`, `message`, `companion_id`
  - Legacy payload with `messages` is still accepted for compatibility
  - Output: assistant `reply`
  - If authenticated session exists, user/assistant messages are stored in SQLite chats table
  - BrainAgent loads last chat turns from SQLite for authenticated users to keep context consistent across sessions
  - BrainAgent also checks last 3 stored emotions and adds simple supportive/light tone hints (rule-based)
  - If companion profile exists, chat system prompt is personalized (name/style/language)

- `GET /api/companions`
  - Requires authenticated session
  - Returns all companions for current user (used by chat sidebar)

- `POST /api/companions`
  - Requires authenticated session
  - Input JSON: `name`, `style`, `language`, optional `voice_type`, optional `profile_voice_id`
  - Creates a companion and returns its `id`

- `PUT /api/companions/<companion_id>`
  - Requires authenticated session
  - Input JSON: `name`, `style`, `language`, optional `voice_type`, optional `profile_voice_id`
  - Updates one companion

- `DELETE /api/companions/<companion_id>`
  - Requires authenticated session
  - Deletes one companion

- `POST /api/companions/<companion_id>/voice`
  - Requires authenticated session
  - Input multipart: `audio`, optional `language_code`
  - Stores companion voice sample and links `profile_voice_id`

- `GET /api/messages/<companion_id>`
  - Requires authenticated session
  - Returns all messages for that companion

- `GET /api/history`
  - Requires authenticated Flask session
  - Query param: optional `companion_id`
  - Output: last 20 messages for current user + companion

- `GET /api/me`
  - Returns current authenticated user session details

- `POST /api/logout` (also supports `GET`)
  - Clears session and logs user out

- `POST /api/register`
  - Input JSON: `username`, `password`
  - Output: JSON-only response + session set on success

- `POST /api/login`
  - Input JSON: `username`, `password`
  - Output: JSON-only response + session set on success

- `GET /api/companion`
  - Requires authenticated session
  - Returns current companion profile (`name`, `style`, `language`)

- `POST /api/companion`
  - Requires authenticated session
  - Input JSON: `name`, `style` (`casual|formal|supportive|motivational`), `language`
  - Creates/updates one companion profile per user

Frontend pages:
- `/login` for user login/register
- `/settings` for companion customization (name, style, preferred language)

Chat UI notes:
- Topbar includes Logout, language switcher, and dark/light toggle
- Logout button is text-only (no door icon)

- `POST /api/tts`
  - Input JSON: `text`, `language_code`, optional `emotion`, optional `speaker`, optional `profile_voice_id`
  - `speaker` supports gender hints (`male` / `female`) used by backend voice selection
  - Output: base64 WAV audio + clone metadata

- `POST /api/stt`
  - Input multipart: `audio`, optional `language_code`
  - Output: `transcript`

- `POST /api/transcribe_profile_audio`
  - Input multipart: `audio`, optional `language_code`
  - Stores profile voice sample and optionally transcribes it
  - Output includes `profile_voice_id`

- `POST /api/action`
  - OS action feature is disabled in this build and returns `403`

## Project Structure

```text
aira/
  backend/
    auth.py
    db.py
    server.py
    requirements.txt
    agents/
      brain_agent.py
      listener_agent.py
      voice_agent.py
      wake_agent.py
    assets/
      profile_voices/
  frontend/
    templates/
      index.html
      login.html
      settings.html
    static/
      app.js
      style.css
  aira.py
  requirements.txt
  README.md
  LICENSE
```

## Requirements

Minimum:
- Python 3.10+
- Ollama installed locally and running

Recommended for full voice experience:
- `ffmpeg` available in system PATH
- Microphone access
- GPU (optional but useful for faster Whisper/XTTS)

## Install

From project root:

```bash
python -m venv .venv310
.venv310\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

If you want full offline voice features, install the extra packages too:

```bash
python -m pip install faster-whisper numpy sounddevice soundfile TTS pyttsx3 pydub
```

Note:
- `backend/requirements.txt` currently contains base dependencies.
- For full offline voice pipeline, you may also need packages used by agents such as:
  - `faster-whisper`
  - `numpy`
  - `sounddevice`
  - `soundfile`
  - `TTS`
  - `pyttsx3`
  - `pydub`

## Complete Run Guide (Backend + Frontend) for Beginners

This project does not run frontend and backend as two separate servers.

- Backend server: Flask (`backend/server.py`)
- Frontend pages: automatically served by the same Flask backend

So, once backend is running, frontend is already running too.

### One-time setup (Windows, PowerShell)

1. Open PowerShell in the project folder (`aira`).
2. Run these commands exactly:

```powershell
python -m venv .venv310
.venv310\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m pip install faster-whisper numpy sounddevice soundfile TTS pyttsx3 pydub
```

3. Install Ollama from official site if not installed.
4. Pull at least one model (example):

```powershell
ollama pull qwen2.5:7b-instruct
ollama pull mistral
```

### Every time you want to run the web app

1. Open Terminal 1 (PowerShell) in project root:

```powershell
.venv310\Scripts\Activate.ps1
ollama serve
```

Keep this terminal open.

2. Open Terminal 2 (PowerShell) in project root:

```powershell
.venv310\Scripts\Activate.ps1
cd backend
python server.py
```

3. Open browser:

- http://127.0.0.1:5000

That URL is your full app (frontend + backend APIs).

### How to confirm everything is working

1. In browser, app UI should load at `/`.
2. Check backend health endpoint in browser:

- http://127.0.0.1:5000/api/status

3. Expected signs:

- `ok: true`
- `llm_model` shows your Ollama model
- `voice_clone_ready` becomes true after XTTS loads

### Stop the app

- In both terminals, press `Ctrl + C`.

### Common beginner mistakes

- If `ollama` command not found: install Ollama and restart terminal.
- If `python` command fails: install Python 3.10+ and reopen terminal.
- If mic not working: allow microphone permission in browser/OS.
- If chat replies are weak or fallback-like: ensure `ollama serve` is running and model is pulled.

## Run (Web App) Quick Version

```bash
cd backend
python server.py
```

Open:
- `http://127.0.0.1:5000`

## Run Frontend Only?

No separate frontend process is needed.

- Do not run `npm start` or `vite` for this project.
- Frontend files in `frontend/templates` and `frontend/static` are served by Flask automatically.

## Run (Standalone Voice Assistant)

From project root:

```bash
python aira.py
```

Flow:
- say wake phrase,
- speak command,
- get spoken response.

## Environment Variables

Optional runtime environment variables used by the current code:

- `AIRA_DEVICE` (default: `cpu`)
- `WHISPER_MODEL` (default: `medium`)
- `GROQ_API_KEY` (required for Groq factual/chat responses)
- `GROQ_MODEL` (default: `llama-3.1-8b-instant`)
- `GROQ_URL` (default: `https://api.groq.com/openai/v1/chat/completions`)
- `OLLAMA_MODEL` (default web: `qwen2.5:7b-instruct`)
- `OLLAMA_URL` (default: `http://localhost:11434`)
- `AIRA_WAKE` (`true`/`false`, default: `true`)
- `AIRA_PROFILE_TRANSCRIBE` (`true`/`false`, default: `false`)
- `AIRA_SECRET_KEY` (Flask session secret; set this in production)
- `APP_HOST` (default: `127.0.0.1`)
- `APP_PORT` (default: `5000`)
- `FLASK_DEBUG` (`true`/`false`, default: `false`)

### Groq key setup for each user

Every friend should use their own Groq key.

Option 1 (recommended): add `.env` in project root:

```env
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

Option 2: login and open `/settings`, then save Groq API key + model.
This stores key in that browser only and sends it securely to backend session.

## Performance Tuning (Low Lag)

Use these settings for faster and more stable local responses:

- Model (web default): `qwen2.5:7b-instruct`
- Optional faster/lighter model: `mistral` via `OLLAMA_MODEL=mistral`
- Ensure Ollama is running before backend start: `ollama serve`
- Keep prompt short and avoid very long chat histories
- Current BrainAgent generation options are tuned for responsiveness:
  - `temperature: 0.6`
  - `top_p: 0.9`
  - `num_predict: 220`
- BrainAgent uses streaming chunk collection and short-term conversation memory (recent turns only)
- Fallback order if preferred model is unavailable: `qwen2.5:7b-instruct` → `mistral` → `llama3.1:8b` → `phi3`

## Notes

- The app name appears as both "Aira" and "Aira" in different parts of code/UI.
- Current backend is offline-first and does not require cloud API keys for core local pipeline.
- If Ollama is not running, chat quality/availability will degrade to fallback responses.
- Database tables are initialized automatically on backend startup via `init_db()`.

## License

See `LICENSE`.
