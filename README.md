# SarvSathi (Apna Saathi)

SarvSathi is a multilingual AI companion project with:
- a web app (Flask + vanilla JS),
- a standalone voice assistant mode,
- a local multi-agent pipeline.

Latest version is designed to run fully offline for core AI flow (STT -> LLM -> Action -> TTS), with optional wake-word detection and voice cloning.

## Latest Status (Current Work)

Current architecture in this repo:
- Agent 1: `ListenerAgent` (speech-to-text)
- Agent 2: `BrainAgent` (local LLM reasoning + intent detection)
- Agent 3: `ActionAgent` (OS actions like opening apps, volume, search)
- Agent 4: `VoiceAgent` (text-to-speech + optional voice cloning)
- `WakeAgent` (always-listening wake phrase: "SarvSathi")

Main backend entrypoint:
- `backend/server.py`

Standalone voice pipeline entrypoint:
- `sarvsathi.py`

Frontend:
- `frontend/templates/index.html`
- `frontend/static/app.js`
- `frontend/static/style.css`

## Models Used (All So Far + Latest)

### A) Latest / current model stack (offline-first)

1. STT (speech-to-text)
- Engine: Faster-Whisper
- Default model: `medium` (configurable via `WHISPER_MODEL`)
- Wake-word detector model: Faster-Whisper `tiny` on CPU inside `WakeAgent`

2. LLM (chat/brain)
- Runtime: Ollama
- Current default model in web backend: `qwen2.5:7b-instruct` (via `OLLAMA_MODEL`)
- Standalone script default: `mistral`
- Brain agent is compatible with other Ollama models too (for example Llama/Phi family if available locally)

3. TTS (speech synthesis)
- Primary: Coqui XTTS v2 (`tts_models/multilingual/multi-dataset/xtts_v2`)
- Fallbacks: `pyttsx3`, then Windows System.Speech fallback
- Voice cloning supported when profile voice audio is uploaded

### B) Earlier model stack used in previous versions (legacy)

This project previously used cloud APIs (as documented in older README/workflow):
- Gemini: `gemini-2.5-flash` (chat)
- Sarvam chat model: `sarvam-m`
- Sarvam TTS: `bulbul:v2`
- Sarvam STT: `saarika:v2.5`

The current codebase has moved to local/offline-first agents and Ollama/Whisper/XTTS pipeline.

## Features Implemented Till Now

- Persona-based conversation setup (name, relation, style, phrases, nickname)
- Text chat and voice chat UI
- Multilingual UI modes (`en`, `hi`, `hinglish`)
- Speech-to-text transcription endpoint
- Text-to-speech response endpoint
- Profile voice sample upload and normalization for cloning
- Wake-word trigger support ("SarvSathi")
- OS automation actions (open apps, web search, volume, restart/shutdown)
- Standalone always-on voice assistant loop (without browser)
- Health/status endpoint exposing active model settings

## API Endpoints (Current Backend)

- `GET /api/status`
  - Returns health and runtime config (`device`, whisper model, LLM model, wake enabled, clone ready)

- `GET /api/wake_status`
  - Returns whether wake word has been detected

- `POST /api/chat`
  - Input JSON: `system`, `messages`
  - Output: assistant `reply`, optional `action`

- `POST /api/tts`
  - Input JSON: `text`, `language_code`, optional `profile_voice_id`
  - Output: base64 WAV audio + clone metadata

- `POST /api/stt`
  - Input multipart: `audio`, optional `language_code`
  - Output: `transcript`

- `POST /api/transcribe_profile_audio`
  - Input multipart: `audio`, optional `language_code`
  - Stores profile voice sample and optionally transcribes it
  - Output includes `profile_voice_id`

- `POST /api/action`
  - Input JSON: `action`
  - Executes OS-level action and returns status

## Project Structure

```text
sarvsathi/
  backend/
    server.py
    requirements.txt
    agents/
      action_agent.py
      brain_agent.py
      listener_agent.py
      voice_agent.py
      wake_agent.py
    assets/
      profile_voices/
  frontend/
    templates/
      index.html
    static/
      app.js
      style.css
  sarvsathi.py
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
python -m venv .venv
.venv\Scripts\activate
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

1. Open PowerShell in the project folder (`sarvsathi`).
2. Run these commands exactly:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m pip install faster-whisper numpy sounddevice soundfile TTS pyttsx3 pydub
```

3. Install Ollama from official site if not installed.
4. Pull at least one model (example):

```powershell
ollama pull qwen2.5:7b-instruct
```

### Every time you want to run the web app

1. Open Terminal 1 (PowerShell) in project root:

```powershell
.venv\Scripts\Activate.ps1
ollama serve
```

Keep this terminal open.

2. Open Terminal 2 (PowerShell) in project root:

```powershell
.venv\Scripts\Activate.ps1
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
python sarvsathi.py
```

Flow:
- say wake phrase,
- speak command,
- get spoken response.

## Environment Variables

Optional runtime environment variables used by the current code:

- `SARVSATHI_DEVICE` (default: `cpu`)
- `WHISPER_MODEL` (default: `medium`)
- `OLLAMA_MODEL` (default web: `qwen2.5:7b-instruct`)
- `OLLAMA_URL` (default: `http://localhost:11434`)
- `SARVSATHI_WAKE` (`true`/`false`, default: `true`)
- `SARVSATHI_PROFILE_TRANSCRIBE` (`true`/`false`, default: `false`)
- `APP_HOST` (default: `127.0.0.1`)
- `APP_PORT` (default: `5000`)
- `FLASK_DEBUG` (`true`/`false`, default: `false`)

## Notes

- The app name appears as both "SarvSathi" and "Apna Saathi" in different parts of code/UI.
- Current backend is offline-first and does not require cloud API keys for core local pipeline.
- If Ollama is not running, chat quality/availability will degrade to fallback responses.

## License

See `LICENSE`.
