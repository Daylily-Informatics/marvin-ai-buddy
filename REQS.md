# Marvin AI Buddy — Requirements

> **Document purpose**: This file enumerates functional and non‑functional requirements inferred from the repository’s public artifacts (notably the top‑level README and root structure).  
> **Scope note**: In this environment, GitHub file views for non‑README content did not reliably load; requirements below are therefore derived primarily from the README and repository root manifest. Validate/extend by reviewing the implementation under `app/`, `components/`, and `react-eva/` once you have local access.

---

## 1. Product definition

### 1.1 Goal
Provide a **multimodal voice assistant** that can:
- hold natural, proactive conversations,
- ingest audio + live camera context,
- use external tools (web search, YouTube search, screenshot/analysis, image/music generation),
- personalize responses per user via voice/face identification,
- run locally (optionally GPU‑accelerated) and/or through hosted model providers.

### 1.2 Intended interfaces
- **Backend**: Python application with **FastAPI** endpoints and **WebSocket** support.
- **Frontend**: a **React web interface** (development server) that captures microphone + camera and interacts with the backend.

---

## 2. System context and architecture requirements

### 2.1 High‑level architecture
The system MUST consist of the following conceptual components:

1. **Client/UI**
   - Web UI (React) running locally for development.
   - Captures microphone and camera input (with browser permissions).
   - Provides “push‑to‑talk” interaction (spacebar‑held recording pattern described in README).

2. **Backend service**
   - Runs the assistant orchestration loop.
   - Exposes HTTP endpoints (FastAPI) and a WebSocket channel for remote control / interaction.
   - Coordinates STT → LLM → tool calls → TTS.

3. **Model & tool adapters**
   - LLM providers: cloud and/or local (via Ollama).
   - STT providers: cloud and/or local.
   - TTS providers: cloud and/or local.
   - Vision model for image understanding.
   - Tool modules for web search, YouTube search, screenshot/analysis, etc.

4. **Local data store**
   - Persistent storage for IDs (voice/photo), and assistant memory/logs.

### 2.2 Operating modes
The system MUST support at least:
- **DEVICE mode**: `"desktop"` or `"mobile"` (used to drive client behavior and backend assumptions).
- **LANGUAGE mode**: specific language suffix (e.g., `"en"`, `"es"`, `"zh"`) and a `"multilingual"` mode.

---

## 3. Functional requirements

### 3.1 Conversation loop
**FR-1** The system MUST accept user speech, transcribe it (STT), and produce a coherent assistant response via a configured chat model (LLM).

**FR-2** The system MUST synthesize speech output (TTS) for the assistant response.

**FR-3** The assistant MUST be able to include *visual context* (from the always‑on camera feed in the web UI mode) in its reasoning and responses.

**FR-4** The assistant MUST be able to operate in multiple languages, including a “multilingual” mode where it replies in the same language spoken by the user.

**FR-5** The assistant MUST support background / asynchronous actions during conversation (tool calls that can proceed while speaking / interacting).

**FR-6** The assistant MUST support termination via spoken command(s) such as “exit” or “bye”.

### 3.2 Web interface behavior (React UI)
**FR-7** The web interface MUST:
- initialize via a “Start” action,
- request camera and microphone permissions from the browser,
- maintain a continuously running camera feed that is passed as context to the backend,
- implement push‑to‑talk speech capture via a keyboard mechanism (spacebar hold/release).

**FR-8** The web interface MUST run as a development server and be accessible locally in a browser.

**FR-9** The backend MUST be reachable by the web UI and run on the expected local port (described as `8080`).

### 3.3 Remote control / WebSocket
**FR-10** The backend MUST provide a WebSocket connection mode for improved interaction/remote control.

### 3.4 Dynamic tool system
**FR-11** The assistant MUST support a tool system that includes (at minimum) the following tool categories:
- Web search (DuckDuckGo/Tavily per README),
- YouTube video search,
- Screenshot capture and analysis,
- Image generation (via Discord Midjourney integration),
- Music generation (via Suno API integration),
- Compatibility with LangChain/LangGraph tools.

**FR-12** The project MUST allow adding tools by:
- editing a built‑in tools list (e.g., `app/tools/init.py` as referenced),
- adding new tool modules under a tools directory (e.g., `app/tools/`).

**FR-13** The project MUST allow disabling tools by configuration in the relevant tool module(s).

### 3.5 Personalization (identity + persona)
**FR-14** The system MUST support user identification via:
- **photo IDs** stored as image files,
- **voice IDs** stored as recorded speech audio files.

**FR-15** The system MUST provide a mechanism to map user names to photo/voice ID filenames via a persistent datastore (README references an SQLite DB `eva.db` and an `ids` table).

**FR-16** The assistant MUST be persona‑driven and allow customizing the persona prompt via a prompt file (README references `app/utils/prompt/persona.md`).

### 3.6 Memory
**FR-17** The system SHOULD maintain conversation logs (“memory log”) and SHOULD support a semantic memory scan feature (noted as testing).

---

## 4. Configuration requirements

### 4.1 Primary configuration location
**CR-1** The system MUST be configurable via a Python config module referenced as `app/config/config.py`.

### 4.2 Configuration keys (minimum set)
The configuration MUST include keys equivalent to:

- `DEVICE`: `"desktop"` or `"mobile"`.
- `LANGUAGE`: language suffix or `"multilingual"`.
- `BASE_URL`: base URL for local model servers (e.g., Ollama).
- `CHAT_MODEL`: selected chat/LLM provider (README mentions Bedrock, Groq, OpenAI, Mistral, Gemini, Ollama, etc).
- `VISION_MODEL`: selected vision model provider.
- `STT_MODEL`: selected speech‑to‑text provider.
- `TTS_MODEL`: selected text‑to‑speech provider.
- `SUMMARIZE_MODEL`: selected summarization provider.

### 4.3 Secrets and credentials
**CR-3** The system MUST support a `.env` file created from `.env.example` to provide API keys and tool credentials.

**CR-4** If AWS Bedrock is used as the default chat model:
- AWS credentials MUST be available via environment variables and/or `~/.aws/credentials`.
- `AWS_REGION` MUST be set to a Bedrock‑enabled region.
- The implementation MUST allow overriding Bedrock model and region (README references `app/utils/agent/models.py`).

**CR-5** Tool integrations MUST be configurable via `.env` and/or config:
- Midjourney tool requires Discord account + private server/channel information.
- Music generation requires a Suno API service reachable at the configured base URL.

---

## 5. External dependency requirements

### 5.1 Supported LLM providers
**DR-1** The system MUST support selecting among multiple LLM backends. README explicitly mentions:
- AWS Bedrock (Claude 3.5 family),
- Groq-hosted LLMs,
- OpenAI ChatGPT (4o family),
- Google Gemini (1.5 Pro),
- Mistral Large,
- Anthropic (direct),
- Ollama local models.

### 5.2 Supported STT providers
**DR-2** The system MUST support:
- OpenAI Whisper (hosted),
- Groq speech (hosted),
- Faster‑Whisper (local).

### 5.3 Supported TTS providers
**DR-3** The system MUST support:
- ElevenLabs,
- OpenAI TTS,
- Coqui TTS (local).

### 5.4 Tool backends
**DR-4** The system MUST support:
- DuckDuckGo and/or Tavily web search backends,
- YouTube search backend,
- Chromium‑based screenshot capture tooling,
- Suno API backend (running as a Dockerized service),
- Discord automation for Midjourney‑based image generation.

---

## 6. Data & persistence requirements

### 6.1 Required directories / files
**DS-1** The repository MUST include data locations (or create them at runtime) for:
- photo IDs (README references `app/data/pid/`),
- voice IDs (README references `app/data/void/`),
- a local database path (README references `app/data/database/eva.db`).

### 6.2 Database schema expectations
**DS-2** The local database MUST contain a table mapping user identity to stored media IDs (README references an `ids` table).

### 6.3 Privacy boundaries
**DS-3** Sensitive identity media (voice/photo IDs) MUST be treated as private user data and MUST NOT be committed to VCS in real deployments.

---

## 7. Platform, runtime, and build requirements

### 7.1 Backend runtime requirements
**PR-1** Python **3.10+** is required.

**PR-2** A CUDA‑compatible GPU SHOULD be available if running large models locally (optional if using hosted providers).

### 7.2 OS-level dependencies (desktop runtime)
**PR-3** On Linux, the system SHOULD be installable with system packages including:
- `cmake`, build toolchain (`build-essential`),
- `ffmpeg`,
- `chromium`,
- `mpv`,
- (and any audio libraries required by Python audio stacks).

**PR-4** On macOS, the system SHOULD be installable via Homebrew packages including:
- `cmake`,
- `ffmpeg`,
- `mpv`,
- `portaudio`,
- `libsndfile`.

**PR-5** On Apple Silicon, if using Faster‑Whisper or PyTorch-based TTS stacks, the setup MUST support installing appropriate PyTorch wheels prior to other requirements.

### 7.3 Frontend runtime requirements
**PR-6** Node.js **v14 or later** is required for the React web interface.

### 7.4 Network/ports
**PR-7** The backend MUST be able to listen on a local port suitable for web UI integration (README references `8080`).

**PR-8** The React dev server MUST serve the UI locally (README references `http://localhost:3000`).

---

## 8. Packaging & deployment requirements

### 8.1 Local execution
**DP-1** The system MUST be runnable via a single Python entrypoint (README references `python app/main.py`).

### 8.2 Docker support
**DP-2** The system SHOULD be runnable via Docker.

**DP-3** A Docker build MUST install required system dependencies (e.g., build tools, `libsndfile1`, `ffmpeg`, `chromium`) and Python dependencies (from `requirements.txt` plus `wespeaker` from Git).

---

## 9. Quality attributes and non-functional requirements

### 9.1 Performance
**NFR-1** The system SHOULD support low-latency transcription and response suitable for interactive voice conversation.

**NFR-2** The system SHOULD allow choosing providers/models to balance cost, latency, and quality (hosted vs local options).

### 9.2 Reliability
**NFR-3** The system SHOULD degrade gracefully when:
- a provider credential is missing,
- a provider rate limit is hit (e.g., Groq usage limits),
- local GPU acceleration is unavailable.

### 9.3 Security
**NFR-4** Secrets (API keys, Discord credentials, AWS credentials) MUST NOT be hardcoded; they MUST be provided via `.env` and/or environment configuration.

**NFR-5** The web UI MUST request explicit browser permission for camera and microphone access.

### 9.4 Maintainability
**NFR-6** Tools MUST be modular and addable via a single-file implementation pattern (as described in README).

**NFR-7** Prompts/persona MUST be editable without code changes (prompt file approach).

---

## 10. Documentation requirements

**DOC-1** The repository MUST include an onboarding path describing:
- how to install system dependencies,
- how to install Python dependencies,
- how to configure `.env`,
- how to run the backend,
- how to run the web UI,
- how to configure `DEVICE`/mobile mode.

**DOC-2** Any references to upstream project names/URLs in documentation SHOULD be updated to match this repository’s actual name and clone URL (README currently references cloning `Genesis1231/EVA`).

---

## 11. Licensing requirements

**LIC-1** The project MUST remain compatible with the MIT license included at the repository root.

---

## 12. Acceptance checklist (practical)

A build/run is considered acceptable when all of the following are true:

- [ ] `python app/main.py` starts the backend without crashing (after installing requirements and configuring `.env`).
- [ ] Backend exposes an HTTP interface and a WebSocket interface.
- [ ] React UI starts via `npm run dev` and loads at `http://localhost:3000`.
- [ ] UI can request mic/camera permissions and stream interaction to backend.
- [ ] At least one end-to-end voice turn works: speech → transcript → response → TTS playback.
- [ ] Switching config models/providers (chat/vision/stt/tts) works without code changes.
- [ ] Tool calls can be enabled/disabled and do not break baseline conversation.

