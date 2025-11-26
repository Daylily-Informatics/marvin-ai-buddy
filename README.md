# Marvin AI Buddy

Marvin AI Buddy is a reference scaffold for a multimodal assistant made up of a lightweight AWS-hosted broker and a local client/monitor stack. The codebase is intentionally minimal so you can iterate on the persona, command contract, and local capabilities (voice, identity, camera) without committing to heavyweight dependencies.

## Repository layout

- `broker/` – AWS Lambda-style handler that validates the API contract, extracts the structured `COMMAND:` line, and returns a normalized payload. It currently uses a deterministic echo response instead of a real LLM.
- `client/` – Text-only console that sends messages to the broker over HTTP or calls the Lambda handler directly for local testing.
- `identity/` – Local identity registry that can enroll and identify people or animals using simple embedding vectors, persisted under `~/.marvin/identity.json`.
- `monitor/` – Monitor subsystem stub that turns presence detections into textual events and forwards them to the broker.
- `docs/requirements.md` – High-level product requirements that guided this scaffold.
- `pyproject.toml` – Project metadata and Python runtime requirements.

## Prerequisites

- **Python**: 3.11 or newer (matches `requires-python` in `pyproject.toml`).
- **Pip**: recent version that supports PEP 621 projects.
- **Optional**: AWS credentials if you plan to deploy the broker to Lambda or experiment with Bedrock/Polly integrations.
- **Network access**: required when calling a remote broker over HTTPS.

## Installation

1. Clone the repository and enter it:
   ```bash
   git clone <repo-url>
   cd marvin-ai-buddy
   ```
2. Create and activate a virtual environment (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install the package and its runtime dependencies:
   ```bash
   pip install -e .
   ```

## Running the broker locally (no AWS)

The broker is implemented as a Lambda-style handler. For quick local iteration, you can bypass HTTP entirely and invoke it through the client’s helper:

```bash
# Send one message and print the normalized response
python -m client.cli "hello from local"
```

This path calls `broker.handler.lambda_handler` in-process and is useful when you do not have an API Gateway endpoint configured.

## Running the text console against a remote broker

If you have deployed the broker behind an HTTPS endpoint (e.g., API Gateway → Lambda), point the console at it:

```bash
export BROKER_URL="https://<api-gateway-host>"  # base URL without trailing /ingest/audio
python -m client.cli "start the monitor" --session-id my-session --voice-id Joey
```

You can also pass a JSON context object (e.g., detected speaker) and request audio playback by clearing `--no-text-only`:

```bash
python -m client.cli "who am I" \
  --broker-url "$BROKER_URL" \
  --context '{"speaker_id": "Major"}' \
  --no-text-only
```

## Sending monitor events

The monitor subsystem converts detections into text and sends them to the broker. Configure it with the same session ID so the broker can thread the conversation:

```python
from monitor.core import MonitorConfig, MonitorEvent, send_monitor_event

config = MonitorConfig(broker_url=BROKER_URL, session_id="my-session")
event = MonitorEvent(people=["Major"], animals=["cat"], unknown_people=1)
response = send_monitor_event(config, event)
print(response)
```

## Using the identity registry

The `IdentityRegistry` stores embeddings on disk to keep enrollment persistent across runs:

```python
from identity.registry import IdentityRegistry

registry = IdentityRegistry()
registry.enroll_voice("Major", [0.1, 0.2, 0.3])
name, score = registry.identify_voice([0.1, 0.2, 0.29])
print(name, score)
```

Data is written to `~/.marvin/identity.json`, which the registry will create if it does not exist.

## Configuration hints

- **Session IDs**: Provide a stable `--session-id` when running the client and monitor together so the broker can stitch responses.
- **Voice ID**: Pass `--voice-id` to prefer a Polly voice when your broker implementation supports audio.
- **Text-only mode**: The console defaults to `text_only=True` to avoid audio payloads; use `--no-text-only` to request audio.

## Next steps

The scaffold is designed to evolve toward the full requirements in `docs/requirements.md`. Recommended enhancements include integrating a real LLM via Amazon Bedrock, wiring up Amazon Polly for speech synthesis, and adding camera/STT pipelines to replace the stubs with production-ready components.
