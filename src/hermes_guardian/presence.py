from __future__ import annotations

import platform
import shlex
import subprocess
import asyncio
from dataclasses import dataclass
from typing import Optional

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
    if presence.ble_enabled:
        signals.append(check_ble_beacon(presence))
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


@dataclass(frozen=True, slots=True)
class IBeaconAdvertisement:
    uuid: str
    major: int
    minor: int
    tx_power: int
    rssi: int
    address: str


def parse_ibeacon_payload(payload: bytes, *, rssi: int = 0, address: str = "") -> IBeaconAdvertisement | None:
    if len(payload) < 23 or payload[0:2] != b"\x02\x15":
        return None

    uuid_hex = payload[2:18].hex()
    uuid = (
        f"{uuid_hex[0:8]}-{uuid_hex[8:12]}-{uuid_hex[12:16]}-"
        f"{uuid_hex[16:20]}-{uuid_hex[20:32]}"
    )
    return IBeaconAdvertisement(
        uuid=uuid.lower(),
        major=int.from_bytes(payload[18:20], byteorder="big"),
        minor=int.from_bytes(payload[20:22], byteorder="big"),
        tx_power=int.from_bytes(payload[22:23], byteorder="big", signed=True),
        rssi=rssi,
        address=address,
    )


def check_ble_beacon(config: PresenceConfig) -> PresenceSignal:
    try:
        beacon = asyncio.run(_scan_ble_beacon(config))
    except Exception as exc:
        return PresenceSignal("ble_beacon", False, config.ble_weight, f"error={exc}")

    if beacon is None:
        return PresenceSignal("ble_beacon", False, config.ble_weight, "not_seen")

    return PresenceSignal(
        "ble_beacon",
        True,
        config.ble_weight,
        f"address={beacon.address} rssi={beacon.rssi} tx_power={beacon.tx_power}",
    )


async def _scan_ble_beacon(config: PresenceConfig) -> Optional[IBeaconAdvertisement]:
    from bleak import BleakScanner

    target_uuid = config.ble_uuid.lower()
    found: IBeaconAdvertisement | None = None

    def on_advertisement(device, advertisement_data) -> None:
        nonlocal found
        payload = advertisement_data.manufacturer_data.get(config.ble_company_id)
        if payload is None:
            return

        beacon = parse_ibeacon_payload(
            payload,
            rssi=advertisement_data.rssi,
            address=device.address,
        )
        if beacon is None:
            return
        if beacon.uuid != target_uuid:
            return
        if beacon.major != config.ble_major or beacon.minor != config.ble_minor:
            return
        if config.ble_min_rssi is not None and beacon.rssi < config.ble_min_rssi:
            return

        found = beacon

    scanner = BleakScanner(on_advertisement)
    async with scanner:
        deadline = asyncio.get_running_loop().time() + config.ble_scan_seconds
        while found is None and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.1)

    return found


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
