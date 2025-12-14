# EVA Requirements

This document summarizes functional, configuration, and operational requirements inferred from the repository.

## Functional Requirements
- The assistant must construct a LangGraph workflow with initialization, sensing, conversation, action execution, and termination nodes, compiled and invoked at startup.
- On startup, EVA must load configured modules (agent, client, memory, toolbox) and set its initial status based on whether user IDs exist.
- The system must conduct a user setup sequence when no user IDs are present, capturing a photo ID and voice ID, registering the user, and updating the persona with user goals before entering normal conversation.
- During conversation, EVA must:
  - Receive sensory input from the client device, send completion notifications, and detect exit commands (e.g., “bye”, “exit”).
  - Use conversation history, sensory input, and optional action results to generate agent responses, store memory entries, and dispatch speech responses to the client.
  - Queue and execute requested actions via the toolbox, returning action results into the dialogue loop until completion or exit.
- EVA must gracefully terminate by speaking an exit message, logging shutdown, and deactivating the client after conversation count tracking.

## Configuration Requirements
- EVA must expose configurable options for device type, language, base URL, and model providers for chat, vision, speech-to-text, text-to-speech, and summarization, with defaults set for mobile, English, local Ollama URL, Bedrock chat, Groq vision, Whisper STT, ElevenLabs TTS, and ChatGPT summarization.
- Configuration should allow swapping supported providers (Bedrock, Groq, OpenAI, Mistral, Gemini, Ollama for chat; OpenAI, Groq, Ollama for vision; Whisper/Groq/Faster-Whisper for STT; Coqui/ElevenLabs/OpenAI for TTS; Groq/Ollama/OpenAI/Anthropic for summarization).

## System and Dependency Requirements
- Runtime requires Python 3.10 or higher; GPU with CUDA is recommended for local model performance.
- System packages needed include CMake, build-essential, ffmpeg, chromium, mpv, and libsndfile (with Homebrew equivalents on macOS). Apple Silicon users should preinstall Metal-optimized PyTorch wheels when using Faster-Whisper or PyTorch TTS.
- Python dependencies must be installed from `requirements.txt`, with additional installation of the WeSpeaker package from Git.

## Operational Requirements
- Developers must create a virtual environment, configure environment variables from `.env.example`, and ensure AWS credentials and region are set when using Bedrock (default chat model). Bedrock model/region overrides live in `app/utils/agent/models.py` if needed.
- EVA must be runnable via `python app/main.py` or through the provided Dockerfile steps (copy requirements, install dependencies, and execute `python /app/main.py`).

## Web Interface Requirements
- The React web interface requires Node.js (v14+) and an EVA backend running on port 8080. Users must install npm dependencies, run `npm run dev`, browse to `http://localhost:3000`, set EVA to mobile mode, and ensure the backend is reachable.

## Tooling Requirements
- Music generation requires a running Suno-API service at the configured base URL.
- Image generation requires a Midjourney account and private Discord server with credentials in the `.env` file.
- Tool enablement/disablement occurs via client settings and the `app/tools` registry; custom tools must follow LangChain tool templates placed under `app/tools/`.

## Personalization Requirements
- EVA’s persona is customizable through `app/utils/prompt/persona.md`, which should reflect user goals captured during setup.
- Users must place clear facial photos in `app/data/pid/` and speech samples (10s+) in `app/data/void/`, updating the `ids` table in `app/data/database/eva.db` to link names to files.
- Text-to-speech voices are configurable within the model-specific files under `app/utils/tts/` (ElevenLabs, OpenAI, Coqui).

## Exit and Shutdown Requirements
- EVA must recognize “exit” or “bye” commands to end sessions.
- On exit, EVA should send a spoken shutdown message, log the conversation count, and deactivate client resources.
