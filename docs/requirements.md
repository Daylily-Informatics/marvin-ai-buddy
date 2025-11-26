# Marvin Multimodal Assistant Requirements

## 1. High-Level System Requirements

### 1.1 Overall Architecture

**Local client (voice console + monitor)**

Runs on macOS (Python 3.11+). Handles:
- Microphone capture and streaming speech recognition.
- Audio playback of broker responses.
- Camera capture and basic perception (people + animals + faces).
- Local identity registry (people + animals).
- Communication with the broker over HTTPS.
- Interpreting structured commands embedded in the broker response.

**Conversation broker (AWS Lambda behind API Gateway)**

Single HTTP endpoint for all "brain" requests. Receives text plus optional context from client. Uses Amazon Bedrock to generate the Marvin response. Uses Amazon Polly to synthesize speech (optional per request). Stores and retrieves short-term conversation history in DynamoDB. Returns chat text, optional audio data, and a structured command for the client.

**Identity subsystem**

Maintains a registry of known people and animals across modalities (voice, face, animal visual signature). Primary store is local (file/database) on client; can optionally mirror to DynamoDB and/or S3. Supports enrollment and identification for each modality.

**Monitor / vision subsystem**

Runs locally beside the client. Watches a camera feed and detects presence of humans and animals. Associates detected entities with identity registry when possible. Sends monitor events to the broker when people/animals enter or leave the scene.

## 2. AWS Broker: API & Behavior

### 2.1 HTTP API Contract

**Endpoint**

- `POST /ingest/audio` (API Gateway → Lambda)

**Request headers**
- `Content-Type: application/json`
- `X-Client-Session: <opaque client session id>` (optional, just echoed back)

**Request body (JSON)**
- Required:
  - `session_id: string` – logical conversational session ID (shared by voice console and monitor).
  - `text: string` – user text or monitor event text, already transcribed.
- Optional:
  - `voice_id: string | null` – preferred Polly voice identifier. If omitted, broker uses a default.
  - `text_only: boolean` – if true, broker must not synthesize audio; it returns text and command only.
  - `context: object` – optional structured hints from the client; fields may include:
    - `speaker_id: string | null` – label of recognized speaker (from local identity).
    - `acoustic_event: string | null` – e.g. "dog_bark" or "door_knock".
    - `intro_already_sent: boolean` – hint that this session has already had Marvin’s intro; used to avoid re-introductions on monitor events.

**Response body (JSON)**

On success (HTTP 200):
- `text: string` – assistant’s reply text with any command line already stripped.
- `command: object` – structured command:
  - `name: string`
  - `args: object`
  - Valid `name` values (initial set):
    - `"noop"` – do nothing.
    - `"launch_monitor"` – client should start the camera monitor.
    - `"set_device"` – client should adjust microphone/camera/speaker device according to args.
- `audio: object | null`
  - When `text_only` is false:
    - `audio_base64: string` – audio data produced by Polly, base64-encoded.
  - When `text_only` is true or Polly is skipped:
    - `null` or an object with `audio_base64` omitted.

On client error (HTTP 4xx):
- JSON with at least:
  - `error: string`
  - `message: string`

On server error (HTTP 5xx):
- JSON with:
  - `error: string`
  - `message: string`
  - Optionally a truncated trace or correlation id.

### 2.2 Command Channel Semantics

The LLM is instructed to end each reply with a dedicated command line:

```
COMMAND: {"name": "noop", "args": {}}
```

Broker responsibilities:
- Find the last line starting with `COMMAND:`.
- Parse the JSON object that follows.
- Validate `name` against the allowed set; if invalid, treat as noop.
- Remove the `COMMAND:` line from the user-visible text.
- Always return a command object in the JSON response (default `{ "name": "noop", "args": {} }`).

### 2.3 LLM / Persona Behavior (Bedrock)

Broker constructs a system prompt passed to Bedrock that:
- Names the assistant “Marvin” and describes stable persona rules:
  - Hyper-intelligent, dry, sardonic tone.
  - Still honest and helpful.
  - Sarcasm dialed down or off for safety-critical topics (medical, legal, financial, self-harm).
- Explicitly describes:
  - That voice console and camera monitor share one conversation per `session_id`.
  - That the assistant should avoid re-introducing itself once it has already done so in a session.
  - That monitor events arrive as structured text (see below), and how to respond:
    - Short, context-aware greetings to named people/animals.
    - No repeated intros.
    - Avoid narrating “I see a person” every second.
  - The command channel format and allowed commands.
- LLM generation:
  - Uses Amazon Bedrock (model choice configurable via environment, e.g. Titan, Claude, etc.).
  - Must support a system message, a conversation history (prior user/assistant turns for the same session), and configurable parameters like temperature and max tokens.
- Special-casing “who am I”:
  - If the broker receives `context.speaker_id` and the user message clearly asks variants of “who am I,” “what’s my name,” or “who is speaking,” then the broker may short-circuit without calling the LLM and simply reply “You are {speaker_id}” (plus any light persona dressing), plus optional TTS.

### 2.4 Session Memory (DynamoDB)

Use Amazon DynamoDB for short-term conversational memory.

**Table (example)**
- Partition key: `session_id` (string)
- Attributes:
  - `session_id`
  - `turns: list` of `{ role: "user"|"assistant", "text": string }`
  - `ttl: numeric` timestamp for automatic expiration

**Broker behavior**
- On each request (if memory enabled via config):
  - Load existing history for `session_id`.
  - Use a bounded number of past turns (e.g., last N) when calling Bedrock.
  - After getting the assistant reply, append the new user and assistant turns and write back.
- Any DynamoDB failure must degrade gracefully:
  - Log, but still respond statelessly.

## 3. Local Identity Subsystem (Client-Side)

### 3.1 Purpose

Provide a unified abstraction to enroll identities (people and animals) using voice samples, face images, and animal visual signatures, and identify entities at runtime given voice embeddings, face embeddings, or animal signatures.

### 3.2 Storage & Sync

- Primary storage: a local file/database on the client (e.g., JSON or small embedded DB).
- Optional remote mirror:
  - DynamoDB item or table for the identity registry.
  - S3 object backup (e.g., `identity/registry.json` in a dedicated bucket).
- Mirror behavior:
  - On registry updates (enroll/remove), client may asynchronously write updated registry to DynamoDB and upload backup to S3.
  - Errors in remote mirroring must not prevent local operations.

### 3.3 Data Model

Identity entries must support at least:
- Common fields:
  - `name: string` – human-readable identifier (e.g., “Major,” “Bill the Donkey”).
  - `type: string` – e.g., "person", "dog", "cat", "donkey", etc.
- Optional modality fields:
  - `voice_embedding: list[number]` – vector for speaker identification.
  - `face_embedding: list[number]` – vector for facial identification.
  - `animal_signature: list[number]` – vector representing animal’s visual pattern.

Representation of the vectors (dimension, scale) is up to implementation; requirement is simply “consistent dimensionality and metric across stored and query vectors.”

### 3.4 Required Operations

The identity subsystem must provide:
- `list_entries() -> list[IdentityEntry]`
- `enroll_voice(name: str, voice_vector)` – add or update `voice_embedding` for the given name.
- `enroll_face(name: str, face_vector)` – add or update `face_embedding` for the given name.
- `enroll_animal(name: str, animal_type: str, signature_vector)` – add or update `animal_signature`.
- `identify_voice(voice_vector) -> (name | null, score)` – compare against stored `voice_embedding` and return best match + similarity score.
- `identify_face(face_vector) -> (name | null, score)` – compare against stored `face_embedding`.
- `identify_animal(animal_type: str, signature_vector) -> (name | null, score)` – compare against stored `animal_signature`.

Thresholds for “good enough” matches are implementation-configurable. Client logic will decide based on score whether to treat it as recognized or “unknown.”

## 4. Monitor / Vision Subsystem (Client-Side)

### 4.1 Purpose

Monitor a video feed, detect entities entering/leaving a region of interest, classify detected entities into people and animals, use identity subsystem to resolve names, and summarize/send monitor events as text messages to the broker.

### 4.2 Configuration

Monitor must be configurable with:
- Camera device selection (index or identifier).
- Region of interest (ROI) in normalized coordinates within the frame (`x1, y1, x2, y2`).
- Detection sensitivity thresholds (confidence, minimum bounding-box size relative to frame).
- Time-based thresholds:
  - Minimum number of consecutive frames with a detection before counting as “entry.”
  - Cooldown between announcing the same person/animal again.
- Optional association to a voice/broker session:
  - `broker_url`
  - `session_id`
  - `voice_id` and `text_only` behavior for monitor-triggered speech.

### 4.3 Runtime Behavior

The monitor loop must:
- Continuously grab frames from the configured camera.
- On each frame (or at a configurable frame rate), run object detection for humans and certain animals, and face detection/encoding if a person is present.
- For each detection:
  - Filter out small or low-confidence detections.
  - Track presence over time to avoid flicker.
- Identity resolution:
  - For each person detection, optionally extract face representation and query identity subsystem for best match.
  - For each animal detection, optionally compute some signature and query identity subsystem.
- Trigger “entry” events when a new person or animal appears and passes temporal filters (enough frames, not seen recently).
- Construct a monitor event message in natural language, which may include:
  - List of recognized people by name.
  - Count of unknown people.
  - List of recognized animals by name and species.
  - Count of unknown animals.
- Call the broker with that text and context:
  - `context.intro_already_sent = true` to avoid re-introductions in responses.
  - `text_only` false by default (so Marvin will speak).
- The monitor should share the same `session_id` as the voice console when appropriate, so that the LLM has shared context.

### 4.4 Face Probing for “Who Am I”

The monitor subsystem must expose a function (or service) to:
- Momentarily ask the user to face the camera.
- Capture one or more frames.
- Attempt to detect and encode one face.
- Query identity subsystem:
  - If matched, return the recognized name.
  - If not matched, return that an unknown face was detected and optionally keep the captured representation for future enrollment.

This is used by the console’s “who am I” voice command and for new registrations.

## 5. Local Audio & STT Subsystem (Client-Side)

### 5.1 Audio Playback

Requirements:
- Ability to play back audio buffers (decoded from broker’s `audio_base64`) through the selected output device.
- Support a shared audio player instance that can be used by voice console and monitor.

Behavior:
- Maintain a shared “mute during playback” or similar guard that indicates when Marvin is speaking and lets the STT subsystem avoid transcribing Marvin’s own speech as user input.
- Implementation details (PCM format, resampling, etc.) are left open; the key is blocking or clearly-defined async playback semantics and a shared state that other subsystems can read to know “Marvin is currently speaking.”

### 5.2 Speech Recognition

Requirements:
- Continuous microphone capture.
- Streaming transcription, producing partial (optional) and final transcripts (required).

Design should:
- Support wake words (e.g., “hey marvin”) by examining the text stream.
- Expose final transcripts as a stream to the main console logic.

Implementation flexibility:
- STT may be fully client-side using any model/library, or via streaming to Amazon Transcribe, with the client handling microphone capture and network streaming.
- Requirement is simply “time-ordered stream of final transcript strings.”

### 5.3 Echo Suppression

To prevent Marvin from responding to his own voice:
- Maintain a recent history of assistant responses (normalized text).
- When a new transcript arrives, if it matches a recent assistant response (within a time window), discard it as echo.
- Time window length and matching heuristic are configurable.

## 6. Voice Console CLI (Client-Side)

### 6.1 Core Loop

The console must:
- Initialize audio and (optionally) camera devices, with a persistent configuration store (e.g., settings file) so the user isn’t prompted every run.
- Start streaming STT from the microphone.
- For each final transcript:
  - Apply echo suppression.
  - Apply wake-word and command-window logic.
  - Either handle as a local command or forward to broker as a normal conversational message.

### 6.2 Wake Word & Command Window

Behavior:
- Recognize phrases like “hey marvin” at the start of a transcript.
- When triggered, open a short “command window” in which certain command phrases affect local state (exit, device changes, identity operations). Other phrases are forwarded to the broker as usual.

### 6.3 Local Voice Commands (Examples)

The console must understand at least:
- `marvin help` – speak short help text describing available commands.
- `marvin monitor` – start (or bring to front) the monitor process attached to the same session.
- `marvin reset` – clear local state and optionally cause a clean restart.
- `marvin who am i / who’s talking` – triggers combined voice+face identity probe and forwards to broker with `context.speaker_id` if known.

Device control:
- Phrases like “set/change/switch camera/microphone/speaker to <N>” to change selected device and persist it.

### 6.4 Identity via Voice

Console must be able to:
- Capture a voice sample over a short window.
- Produce a voice representation (embedding or equivalent).
- Enroll this representation into the identity registry associated with a given name (e.g., triggered by saying “call me Major” or a similar phrase).
- On each future utterance, optionally generate a voice representation, query identity registry for likely speaker, and pass `speaker_id` in context to the broker.

Underlying ML model/library is not specified—only the behavior.

### 6.5 Handling Broker Commands

When the broker response includes a command object:
- `noop` – ignore.
- `launch_monitor` – start monitor if not already running, using current camera & session.
- `set_device` – adjust and persist local device configuration according to args (e.g., new camera/mic/speaker index).

## 7. Non-Functional Requirements

**Performance**
- End-to-end latency (user finishes speaking → Marvin reply begins playing) should be low enough for interactive use (<2–3 s target).
- Monitor processing should not block audio path; they should be decoupled.

**Resilience**
- Any AWS call failures (Bedrock, Polly, DynamoDB, S3) should return a meaningful error and not crash the client.
- Local client should handle transient network failures gracefully (retry, or clearly tell the user what broke).

**Security**
- All broker calls over HTTPS.
- AWS credentials handled via standard mechanisms (IAM roles, profiles, or env vars); no hard-coded keys.
- Registry and local settings stored in user’s home directory with appropriate file permissions.

**Configurability**
- Broker URL, session ID, voice, and other settings should be configurable via CLI flags or configuration file.
- Ability to run in “text-only mode” (no TTS) for testing.

## 8. “Do this next”

- Copy this requirements doc into a new repo as `docs/requirements.md`.
- Scaffold minimal packages: `broker/`, `client/`, `identity/`, `monitor/`.
- Implement only:
  - Broker endpoint (text in, text out, no audio, no memory) on AWS.
  - Text-only CLI that sends typed input to broker and prints reply.
- Once that path is solid, extend incrementally:
  - Add Polly audio.
  - Add STT (streaming mic).
  - Add identity.
  - Add monitor.

This keeps architecture clean and lets you change local libs at will without rewriting the contract with AWS.
