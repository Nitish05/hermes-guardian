from pathlib import Path

import pytest

from hermes_guardian.config import GuardianConfig, write_default_config


def test_config_defaults_can_be_serialized():
    config = GuardianConfig()
    data = config.to_dict()
    assert data["camera"]["source"] == 0
    assert data["camera"]["sample_fps"] == 1.0
    assert data["detection"]["backend"] == "yolo"
    assert data["detection"]["model"] == "yolo26n.pt"
    assert data["detection"]["confidence"] == 0.45
    assert data["face"]["enabled"] is False
    assert "state_file" in data["paths"]


def test_config_validates_backend_specific_confidence():
    GuardianConfig.from_mapping({"detection": {"backend": "hog", "confidence": 0.0}}).validate(
        require_phone=False
    )

    with pytest.raises(ValueError):
        GuardianConfig.from_mapping({"detection": {"backend": "yolo", "confidence": 0.0}}).validate(
            require_phone=False
        )


def test_router_only_presence_does_not_require_phone_ip():
    GuardianConfig.from_mapping(
        {
            "presence": {
                "ping_enabled": False,
                "router_command": "true",
            }
        }
    ).validate()


def test_presence_requires_at_least_one_signal():
    with pytest.raises(ValueError):
        GuardianConfig.from_mapping({"presence": {"ping_enabled": False}}).validate()


def test_config_rejects_unknown_keys():
    with pytest.raises(ValueError):
        GuardianConfig.from_mapping({"phone": {"nope": True}})


def test_write_default_config_refuses_overwrite(tmp_path: Path):
    path = tmp_path / "config.yaml"
    write_default_config(path)
    with pytest.raises(FileExistsError):
        write_default_config(path)
