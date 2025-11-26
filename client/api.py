"""HTTP client utilities for talking to the Marvin broker."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

import requests


def default_session_id() -> str:
    return str(uuid.uuid4())


def send_text(
    *,
    broker_url: str,
    text: str,
    session_id: Optional[str] = None,
    voice_id: Optional[str] = None,
    text_only: bool = True,
    context: Optional[Dict[str, Any]] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Send a text payload to the broker and return the parsed JSON response."""

    payload = {
        "session_id": session_id or default_session_id(),
        "text": text,
        "voice_id": voice_id,
        "text_only": text_only,
        "context": context or {},
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(broker_url.rstrip("/") + "/ingest/audio", headers=headers, data=json.dumps(payload), timeout=timeout)
    response.raise_for_status()
    return response.json()


def call_local_lambda(text: str, session_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Invoke the broker lambda handler directly without HTTP."""

    from broker.handler import lambda_handler

    event = {
        "body": {
            "session_id": session_id or default_session_id(),
            "text": text,
            "context": context or {},
            "text_only": True,
        }
    }
    result = lambda_handler(event, None)
    if result.get("statusCode") != 200:
        raise RuntimeError(f"lambda error: {result}")
    return json.loads(result["body"])


__all__ = ["send_text", "call_local_lambda", "default_session_id"]
