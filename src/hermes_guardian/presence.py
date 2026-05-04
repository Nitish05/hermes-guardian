from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass

from .config import PhoneConfig


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


def check_phone(config: PhoneConfig) -> bool:
    return ping_host(
        config.ip,
        count=config.ping_count,
        timeout_seconds=config.ping_timeout_seconds,
    )

