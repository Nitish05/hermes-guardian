import builtins

import pytest

from hermes_guardian.config import DetectionConfig
from hermes_guardian.detection import PersonDetector


def test_yolo_backend_explains_missing_ultralytics(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "ultralytics":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match=r"pip install -e \."):
        PersonDetector(DetectionConfig(backend="yolo", confidence=0.45))
