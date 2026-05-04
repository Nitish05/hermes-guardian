from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _expand(path: str | Path) -> Path:
    return Path(path).expanduser()


@dataclass(slots=True)
class PhoneConfig:
    ip: str = ""
    ping_count: int = 1
    ping_timeout_seconds: float = 1.0
    ping_interval_home_seconds: float = 180.0
    ping_interval_guardian_seconds: float = 30.0
    missed_ping_threshold: int = 3
    return_ping_threshold: int = 2


@dataclass(slots=True)
class CameraConfig:
    source: int | str = 0
    frame_width: int = 640
    frame_height: int = 480
    sample_fps: float = 1.0


@dataclass(slots=True)
class DetectionConfig:
    model: str = "yolo26n.pt"
    confidence: float = 0.45
    image_size: int = 320
    consecutive_unknown_threshold: int = 2
    alert_cooldown_seconds: float = 60.0


@dataclass(slots=True)
class FaceConfig:
    tolerance: float = 0.6
    detection_model: str = "hog"
    upsample: int = 0


@dataclass(slots=True)
class PathConfig:
    state_file: Path = field(
        default_factory=lambda: _expand("~/.local/state/hermes-guardian/state.json")
    )
    event_log: Path = field(
        default_factory=lambda: _expand("~/.local/state/hermes-guardian/events.jsonl")
    )
    data_dir: Path = field(
        default_factory=lambda: _expand("~/.local/share/hermes-guardian")
    )
    snapshot_dir: Path = field(
        default_factory=lambda: _expand("~/.local/state/hermes-guardian/snapshots")
    )

    @property
    def encodings_file(self) -> Path:
        return self.data_dir / "owner_encodings.npz"


@dataclass(slots=True)
class GuardianConfig:
    phone: PhoneConfig = field(default_factory=PhoneConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    face: FaceConfig = field(default_factory=FaceConfig)
    paths: PathConfig = field(default_factory=PathConfig)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "GuardianConfig":
        config = cls()
        if path is None:
            default_path = _expand("~/.config/hermes-guardian/config.yaml")
            if not default_path.exists():
                return config
            path = default_path

        config_path = _expand(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError("Config file must contain a YAML mapping.")
        return cls.from_mapping(data)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "GuardianConfig":
        return cls(
            phone=_merge_dataclass(PhoneConfig, data.get("phone", {})),
            camera=_merge_dataclass(CameraConfig, data.get("camera", {})),
            detection=_merge_dataclass(DetectionConfig, data.get("detection", {})),
            face=_merge_dataclass(FaceConfig, data.get("face", {})),
            paths=_path_config_from_mapping(data.get("paths", {})),
        )

    def validate(self, *, require_phone: bool = True) -> None:
        if require_phone and not self.phone.ip:
            raise ValueError("phone.ip must be set in the config.")
        if self.phone.missed_ping_threshold < 1:
            raise ValueError("phone.missed_ping_threshold must be at least 1.")
        if self.phone.return_ping_threshold < 1:
            raise ValueError("phone.return_ping_threshold must be at least 1.")
        if self.camera.sample_fps <= 0:
            raise ValueError("camera.sample_fps must be greater than 0.")
        if not 0 < self.detection.confidence <= 1:
            raise ValueError("detection.confidence must be between 0 and 1.")
        if not 0 < self.face.tolerance < 1:
            raise ValueError("face.tolerance must be between 0 and 1.")

    def ensure_dirs(self) -> None:
        self.paths.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.paths.event_log.parent.mkdir(parents=True, exist_ok=True)
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.paths.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phone": asdict(self.phone),
            "camera": asdict(self.camera),
            "detection": asdict(self.detection),
            "face": asdict(self.face),
            "paths": {
                "state_file": str(self.paths.state_file),
                "event_log": str(self.paths.event_log),
                "data_dir": str(self.paths.data_dir),
                "snapshot_dir": str(self.paths.snapshot_dir),
            },
        }


def _merge_dataclass(cls: type, values: Any):
    if values is None:
        values = {}
    if not isinstance(values, dict):
        raise ValueError(f"{cls.__name__} config must be a mapping.")
    allowed = cls.__dataclass_fields__
    unknown = set(values) - set(allowed)
    if unknown:
        raise ValueError(f"Unknown {cls.__name__} config keys: {sorted(unknown)}")
    return cls(**values)


def _path_config_from_mapping(values: Any) -> PathConfig:
    if values is None:
        values = {}
    if not isinstance(values, dict):
        raise ValueError("PathConfig config must be a mapping.")
    allowed = PathConfig.__dataclass_fields__
    unknown = set(values) - set(allowed)
    if unknown:
        raise ValueError(f"Unknown PathConfig config keys: {sorted(unknown)}")
    paths = {key: _expand(value) for key, value in values.items()}
    return PathConfig(**paths)


def write_default_config(path: str | Path) -> Path:
    config_path = _expand(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        raise FileExistsError(f"Config already exists: {config_path}")
    config_path.write_text(yaml.safe_dump(GuardianConfig().to_dict(), sort_keys=False), encoding="utf-8")
    return config_path
