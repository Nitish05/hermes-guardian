from pathlib import Path

import pytest

from hermes_guardian.config import GuardianConfig, write_default_config


def test_config_defaults_can_be_serialized():
    config = GuardianConfig()
    data = config.to_dict()
    assert data["camera"]["source"] == 0
    assert "state_file" in data["paths"]


def test_config_rejects_unknown_keys():
    with pytest.raises(ValueError):
        GuardianConfig.from_mapping({"phone": {"nope": True}})


def test_write_default_config_refuses_overwrite(tmp_path: Path):
    path = tmp_path / "config.yaml"
    write_default_config(path)
    with pytest.raises(FileExistsError):
        write_default_config(path)

