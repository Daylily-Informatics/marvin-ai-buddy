"""Lightweight identity registry supporting enrollment and identification."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class IdentityEntry:
    name: str
    type: str
    voice_embedding: Optional[List[float]] = None
    face_embedding: Optional[List[float]] = None
    animal_signature: Optional[List[float]] = None


@dataclass
class IdentityRegistry:
    storage_path: Path = field(default_factory=lambda: Path.home() / ".marvin" / "identity.json")
    entries: Dict[str, IdentityEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text())
            for item in data.get("entries", []):
                entry = IdentityEntry(**item)
                self.entries[entry.name] = entry

    def save(self) -> None:
        payload = {"entries": [asdict(entry) for entry in self.entries.values()]}
        self.storage_path.write_text(json.dumps(payload, indent=2))

    def list_entries(self) -> List[IdentityEntry]:
        return list(self.entries.values())

    def enroll_voice(self, name: str, voice_vector: List[float], entity_type: str = "person") -> IdentityEntry:
        entry = self.entries.get(name) or IdentityEntry(name=name, type=entity_type)
        entry.voice_embedding = voice_vector
        self.entries[name] = entry
        self.save()
        return entry

    def enroll_face(self, name: str, face_vector: List[float], entity_type: str = "person") -> IdentityEntry:
        entry = self.entries.get(name) or IdentityEntry(name=name, type=entity_type)
        entry.face_embedding = face_vector
        self.entries[name] = entry
        self.save()
        return entry

    def enroll_animal(self, name: str, animal_type: str, signature_vector: List[float]) -> IdentityEntry:
        entry = self.entries.get(name) or IdentityEntry(name=name, type=animal_type)
        entry.animal_signature = signature_vector
        self.entries[name] = entry
        self.save()
        return entry

    def identify_voice(self, voice_vector: List[float]) -> Tuple[Optional[str], float]:
        return self._identify(voice_vector, "voice_embedding")

    def identify_face(self, face_vector: List[float]) -> Tuple[Optional[str], float]:
        return self._identify(face_vector, "face_embedding")

    def identify_animal(self, animal_type: str, signature_vector: List[float]) -> Tuple[Optional[str], float]:
        return self._identify(signature_vector, "animal_signature", type_filter=animal_type)

    def _identify(self, query: List[float], field_name: str, type_filter: Optional[str] = None) -> Tuple[Optional[str], float]:
        best_score = -1.0
        best_name: Optional[str] = None
        for entry in self.entries.values():
            if type_filter and entry.type != type_filter:
                continue
            embedding = getattr(entry, field_name)
            if not embedding:
                continue
            score = cosine_similarity(query, embedding)
            if score > best_score:
                best_score = score
                best_name = entry.name
        return best_name, best_score


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return -1.0
    return dot / (norm_a * norm_b)


__all__ = ["IdentityRegistry", "IdentityEntry", "cosine_similarity"]
