"""Monitor subsystem stub for wiring events to the broker."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests


@dataclass
class MonitorConfig:
    broker_url: str
    session_id: str
    voice_id: Optional[str] = None
    text_only: bool = False


@dataclass
class MonitorEvent:
    people: List[str]
    animals: List[str]
    unknown_people: int = 0
    unknown_animals: int = 0

    def to_text(self) -> str:
        parts = []
        if self.people:
            parts.append("People present: " + ", ".join(self.people))
        if self.animals:
            parts.append("Animals present: " + ", ".join(self.animals))
        if self.unknown_people:
            parts.append(f"Unknown people: {self.unknown_people}")
        if self.unknown_animals:
            parts.append(f"Unknown animals: {self.unknown_animals}")
        return "; ".join(parts) if parts else "No detections"


def send_monitor_event(config: MonitorConfig, event: MonitorEvent) -> Dict[str, object]:
    """Send a synthesized monitor event to the broker."""

    payload = {
        "session_id": config.session_id,
        "text": event.to_text(),
        "text_only": config.text_only,
        "voice_id": config.voice_id,
        "context": {"intro_already_sent": True},
    }
    response = requests.post(
        config.broker_url.rstrip("/") + "/ingest/audio",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


__all__ = ["MonitorConfig", "MonitorEvent", "send_monitor_event"]
