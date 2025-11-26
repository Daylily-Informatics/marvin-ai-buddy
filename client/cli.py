"""Text-only Marvin console that talks to the broker."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

from .api import call_local_lambda, default_session_id, send_text


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Marvin text console")
    parser.add_argument("text", nargs="*", help="Text to send. If omitted, read from stdin.")
    parser.add_argument("--broker-url", dest="broker_url", default=os.getenv("BROKER_URL"), help="HTTP URL for the broker endpoint")
    parser.add_argument("--session-id", dest="session_id", default=os.getenv("MARVIN_SESSION_ID", default_session_id()), help="Conversation session id")
    parser.add_argument("--voice-id", dest="voice_id", default=None, help="Optional Polly voice preference")
    parser.add_argument("--no-text-only", dest="text_only", action="store_false", help="Request audio in responses")
    parser.add_argument("--context", dest="context", default=None, help="JSON object with context fields")
    return parser.parse_args(argv)


def load_context(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid context JSON: {exc}")


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    context = load_context(args.context)
    text = " ".join(args.text) if args.text else sys.stdin.read().strip()
    if not text:
        raise SystemExit("No input provided")

    if args.broker_url:
        response = send_text(
            broker_url=args.broker_url,
            text=text,
            session_id=args.session_id,
            voice_id=args.voice_id,
            text_only=args.text_only,
            context=context,
        )
    else:
        response = call_local_lambda(text=text, session_id=args.session_id, context=context)

    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
