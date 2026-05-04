from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .config import FaceConfig


@dataclass(frozen=True, slots=True)
class FaceMatch:
    matched: bool
    distance: float | None
    faces_found: int


class OwnerRecognizer:
    def __init__(self, config: FaceConfig, encodings_file: Path):
        self.config = config
        self.encodings_file = encodings_file
        self._encodings: list[np.ndarray] | None = None

    def load(self) -> list[np.ndarray]:
        if self._encodings is not None:
            return self._encodings
        if not self.encodings_file.exists():
            raise FileNotFoundError(
                f"No owner encodings found. Run `guardian enroll` first: {self.encodings_file}"
            )
        data = np.load(self.encodings_file, allow_pickle=False)
        self._encodings = [encoding for encoding in data["encodings"]]
        return self._encodings

    def enroll(self, image_paths: list[Path]) -> int:
        import face_recognition

        encodings: list[np.ndarray] = []
        for image_path in image_paths:
            image = face_recognition.load_image_file(str(image_path))
            found = face_recognition.face_encodings(
                image,
                known_face_locations=None,
                num_jitters=1,
                model="small",
            )
            if not found:
                raise ValueError(f"No face found in enrollment image: {image_path}")
            encodings.append(found[0])

        self.encodings_file.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(self.encodings_file, encodings=np.asarray(encodings))
        self._encodings = encodings
        return len(encodings)

    def match_frame(self, frame_bgr: np.ndarray) -> FaceMatch:
        import face_recognition

        known = self.load()
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(
            rgb,
            number_of_times_to_upsample=self.config.upsample,
            model=self.config.detection_model,
        )
        if not locations:
            return FaceMatch(matched=False, distance=None, faces_found=0)

        encodings = face_recognition.face_encodings(rgb, known_face_locations=locations)
        best_distance: float | None = None
        for unknown in encodings:
            distances = face_recognition.face_distance(known, unknown)
            if len(distances) == 0:
                continue
            distance = float(np.min(distances))
            if best_distance is None or distance < best_distance:
                best_distance = distance
            if distance <= self.config.tolerance:
                return FaceMatch(matched=True, distance=distance, faces_found=len(locations))
        return FaceMatch(matched=False, distance=best_distance, faces_found=len(locations))

