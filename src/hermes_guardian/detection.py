from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np

from .config import CameraConfig, DetectionConfig


@dataclass(frozen=True, slots=True)
class PersonDetection:
    xyxy: tuple[int, int, int, int]
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return {"xyxy": list(self.xyxy), "confidence": self.confidence}


class Camera:
    def __init__(self, config: CameraConfig):
        self.config = config
        self.capture = None

    def __enter__(self) -> "Camera":
        self.capture = cv2.VideoCapture(self.config.source)
        if self.config.frame_width:
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
        if self.config.frame_height:
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)
        if not self.capture.isOpened():
            raise RuntimeError(f"Unable to open camera source: {self.config.source}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.capture is not None:
            self.capture.release()

    def read(self) -> np.ndarray:
        if self.capture is None:
            raise RuntimeError("Camera is not open.")
        ok, frame = self.capture.read()
        if not ok or frame is None or frame.size == 0:
            raise RuntimeError("Camera returned a blank frame.")
        return frame


class PersonDetector:
    def __init__(self, config: DetectionConfig):
        from ultralytics import YOLO

        self.config = config
        self.model = YOLO(config.model)

    def detect(self, frame: np.ndarray) -> list[PersonDetection]:
        results = self.model.predict(
            source=frame,
            classes=[0],
            conf=self.config.confidence,
            imgsz=self.config.image_size,
            verbose=False,
        )
        detections: list[PersonDetection] = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            xyxy_values = _as_iterable(getattr(boxes, "xyxy", []))
            confidence_values = _as_iterable(getattr(boxes, "conf", []))
            for xyxy, confidence in zip(xyxy_values, confidence_values):
                coords = tuple(int(round(float(value))) for value in xyxy[:4])
                detections.append(PersonDetection(coords, float(confidence)))
        return detections


def crop_detection(frame: np.ndarray, detection: PersonDetection, padding: int = 12) -> np.ndarray:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = detection.xyxy
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(width, x2 + padding)
    y2 = min(height, y2 + padding)
    return frame[y1:y2, x1:x2]


def _as_iterable(value) -> Iterable:
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return value
