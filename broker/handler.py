"""AWS Lambda-style broker handler for Marvin requests.

This module keeps implementation light: it validates the API contract and
produces a deterministic assistant response. Bedrock and Polly integration are
abstracted behind helpers so the package is runnable without AWS credentials.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class BrokerCommand:
    """Structured command returned to the client."""

    name: str = "noop"
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrokerResponse:
    """Normalized broker response payload."""

    text: str
    command: BrokerCommand
    audio: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "text": self.text,
            "command": {
                "name": self.command.name,
                "args": self.command.args,
            },
            "audio": self.audio,
        }
        return payload


class CommandParsingError(Exception):
    """Raised when the COMMAND line exists but is not valid JSON."""


ALLOWED_COMMANDS = {"noop", "launch_monitor", "set_device"}


def extract_command(text: str) -> tuple[str, BrokerCommand]:
    """Extract a structured command from the assistant text.

    Looks for the last line that starts with ``COMMAND:``. If present, the JSON
    following the prefix is parsed and validated. The command line is removed
    from the returned text.
    """

    lines = text.splitlines()
    command: BrokerCommand = BrokerCommand()
    trimmed_lines = []

    for line in lines:
        if line.startswith("COMMAND:"):
            try:
                parsed = json.loads(line[len("COMMAND:") :].strip())
            except json.JSONDecodeError as exc:
                raise CommandParsingError("Invalid command JSON") from exc
            name = parsed.get("name", "noop")
            args = parsed.get("args", {}) if isinstance(parsed.get("args", {}), dict) else {}
            if name not in ALLOWED_COMMANDS:
                name = "noop"
                args = {}
            command = BrokerCommand(name=name, args=args)
        else:
            trimmed_lines.append(line)

    visible_text = "\n".join(trimmed_lines).strip()
    return visible_text, command


def build_system_prompt() -> str:
    persona = (
        "You are Marvin, a hyper-intelligent, sardonic assistant. Keep replies "
        "concise unless asked to elaborate."
    )
    channel = (
        "Always end responses with a COMMAND line in the format "
        "COMMAND: {\"name\":\"noop\",\"args\":{}}."
    )
    return f"{persona} {channel}"


def generate_assistant_reply(text: str, context: Optional[Dict[str, Any]] = None) -> str:
    """Simple stand-in for a Bedrock generation call.

    The response echoes the user with light persona dressing and appends a
    default command. If the text hints at starting the monitor or changing
    devices, we emit the appropriate structured command.
    """

    context = context or {}
    lower = text.lower()
    command_line = 'COMMAND: {"name": "noop", "args": {}}'

    if "monitor" in lower:
        command_line = 'COMMAND: {"name": "launch_monitor", "args": {}}'
    elif "microphone" in lower or "camera" in lower or "speaker" in lower:
        command_line = 'COMMAND: {"name": "set_device", "args": {"preferred": "auto"}}'

    speaker_hint = context.get("speaker_id")
    intro = f"You are {speaker_hint}. " if speaker_hint else ""
    return f"{intro}Marvin here. You said: {text}\n{command_line}"


def lambda_handler(event: Dict[str, Any], _context: Any = None) -> Dict[str, Any]:
    """Entry point compatible with API Gateway proxy integration."""

    body = event.get("body", event)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "invalid_request", "message": "Body must be JSON"}),
            }

    required_fields = {"session_id", "text"}
    if not required_fields.issubset(body):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "invalid_request", "message": "Missing required fields"}),
        }

    text = body["text"]
    context = body.get("context") or {}
    text_only = bool(body.get("text_only", False))

    assistant_raw = generate_assistant_reply(text, context=context)
    try:
        visible_text, command = extract_command(assistant_raw)
    except CommandParsingError as exc:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "command_parse_error", "message": str(exc)}),
        }

    response = BrokerResponse(text=visible_text, command=command, audio=None if text_only else {})
    return {"statusCode": 200, "body": json.dumps(response.to_dict())}


__all__ = [
    "BrokerResponse",
    "BrokerCommand",
    "lambda_handler",
    "extract_command",
    "generate_assistant_reply",
    "build_system_prompt",
]
