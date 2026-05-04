from __future__ import annotations

import platform
import shlex
import subprocess
from dataclasses import dataclass

from .config import PhoneConfig, PresenceConfig


def ping_host(ip: str, *, count: int = 1, timeout_seconds: float = 1.0) -> bool:
    if not ip:
        raise ValueError("Phone IP is required.")

    system = platform.system().lower()
    if system == "windows":
        command = ["ping", "-n", str(count), "-w", str(int(timeout_seconds * 1000)), ip]
    else:
        command = ["ping", "-c", str(count), "-W", str(max(1, int(timeout_seconds))), ip]

    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


@dataclass(slots=True)
class PresenceTracker:
    config: PhoneConfig
    missed_count: int = 0
    returned_count: int = 0
    guardian_mode: bool = False

    def observe(self, reachable: bool) -> str | None:
        if reachable:
            self.missed_count = 0
            self.returned_count += 1
            if self.guardian_mode and self.returned_count >= self.config.return_ping_threshold:
                self.guardian_mode = False
                return "returned_home"
            return "phone_reachable"

        self.returned_count = 0
        self.missed_count += 1
        if not self.guardian_mode and self.missed_count >= self.config.missed_ping_threshold:
            self.guardian_mode = True
            return "entered_guardian"
        return "phone_unreachable"


@dataclass(frozen=True, slots=True)
class PresenceSignal:
    name: str
    home: bool
    weight: float
    detail: str = ""

    @property
    def score(self) -> float:
        return self.weight if self.home else 0.0


@dataclass(frozen=True, slots=True)
class PresenceResult:
    home: bool
    score: float
    threshold: float
    signals: tuple[PresenceSignal, ...]

    def to_event_payload(self) -> dict[str, object]:
        return {
            "presence_score": self.score,
            "presence_threshold": self.threshold,
            "presence_signals": [
                {
                    "name": signal.name,
                    "home": signal.home,
                    "weight": signal.weight,
                    "detail": signal.detail,
                }
                for signal in self.signals
            ],
        }


def evaluate_presence(phone: PhoneConfig, presence: PresenceConfig) -> PresenceResult:
    signals: list[PresenceSignal] = []
    if presence.router_command:
        signals.append(_check_router_command(presence))
    if presence.ping_enabled:
        ping_home = ping_host(
            phone.ip,
            count=phone.ping_count,
            timeout_seconds=phone.ping_timeout_seconds,
        )
        signals.append(PresenceSignal("ping", ping_home, presence.ping_weight, phone.ip))

    score = sum(signal.score for signal in signals)
    return PresenceResult(
        home=score >= presence.home_score_threshold,
        score=score,
        threshold=presence.home_score_threshold,
        signals=tuple(signals),
    )


def check_phone(config: PhoneConfig, presence: PresenceConfig | None = None) -> bool:
    if presence is None:
        return ping_host(
            config.ip,
            count=config.ping_count,
            timeout_seconds=config.ping_timeout_seconds,
        )
    return evaluate_presence(config, presence).home


def _check_router_command(config: PresenceConfig) -> PresenceSignal:
    command = shlex.split(config.router_command)
    if not command:
        return PresenceSignal("router_command", False, config.router_command_weight, "empty")

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=config.router_command_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return PresenceSignal("router_command", False, config.router_command_weight, "timeout")

    detail = (result.stdout or result.stderr).strip().splitlines()
    return PresenceSignal(
        "router_command",
        result.returncode == 0,
        config.router_command_weight,
        detail[0] if detail else f"exit={result.returncode}",
    )
