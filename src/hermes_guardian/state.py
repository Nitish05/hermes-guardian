from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(slots=True)
class GuardianState:
    mode: str = "home"
    phone_reachable: bool = False
    guardian_mode: bool = False
    alert_active: bool = False
    last_seen_phone_at: str | None = None
    last_person_detected_at: str | None = None
    last_owner_match_at: str | None = None
    last_intruder_event_at: str | None = None
    last_event: str | None = "initialized"
    missed_phone_count: int = 0
    returned_phone_count: int = 0
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "phone_reachable": self.phone_reachable,
            "guardian_mode": self.guardian_mode,
            "alert_active": self.alert_active,
            "last_seen_phone_at": self.last_seen_phone_at,
            "last_person_detected_at": self.last_person_detected_at,
            "last_owner_match_at": self.last_owner_match_at,
            "last_intruder_event_at": self.last_intruder_event_at,
            "last_event": self.last_event,
            "missed_phone_count": self.missed_phone_count,
            "returned_phone_count": self.returned_phone_count,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GuardianState":
        allowed = cls.__dataclass_fields__
        values = {key: data.get(key) for key in allowed if key in data}
        return cls(**values)


class StateStore:
    def __init__(self, state_file: Path, event_log: Path):
        self.state_file = state_file
        self.event_log = event_log

    def load(self) -> GuardianState:
        if not self.state_file.exists():
            return GuardianState()
        with self.state_file.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError(f"State file must contain a JSON object: {self.state_file}")
        return GuardianState.from_dict(data)

    def save(self, state: GuardianState) -> None:
        state.updated_at = now_iso()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.state_file.with_name(f".{self.state_file.name}.tmp")
        tmp_file.write_text(
            json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_file, self.state_file)

    def event(self, event_type: str, **payload: Any) -> None:
        self.event_log.parent.mkdir(parents=True, exist_ok=True)
        entry = {"time": now_iso(), "event": event_type, **payload}
        with self.event_log.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry, sort_keys=True) + "\n")
