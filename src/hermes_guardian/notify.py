from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import NotifyConfig


@dataclass(frozen=True, slots=True)
class NotifyResult:
    sent: bool
    detail: str


def send_unknown_person_notification(
    config: NotifyConfig,
    *,
    state_file: Path,
    event_log: Path,
    snapshot: Path | None,
) -> NotifyResult:
    if not config.command:
        return NotifyResult(False, "notify.command not configured")

    command = shlex.split(config.command)
    if not command:
        return NotifyResult(False, "notify.command is empty")

    env = os.environ.copy()
    env.update(
        {
            "GUARDIAN_EVENT": "unknown_person",
            "GUARDIAN_STATE_FILE": str(state_file),
            "GUARDIAN_EVENT_LOG": str(event_log),
            "GUARDIAN_SNAPSHOT": str(snapshot or ""),
        }
    )
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=config.timeout_seconds,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return NotifyResult(False, "timeout")

    output = (result.stdout or result.stderr).strip().splitlines()
    detail = output[0] if output else f"exit={result.returncode}"
    return NotifyResult(result.returncode == 0, detail)
