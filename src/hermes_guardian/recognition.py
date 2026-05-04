from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .config import FaceConfig

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True, slots=True)
class FaceMatch:
    matched: bool
    distance: float | None
    faces_found: int


@dataclass(frozen=True, slots=True)
class GuidedEnrollmentResult:
    samples: int
    output_file: Path
    appended: bool


class OwnerRecognizer:
    def __init__(self, config: FaceConfig, encodings_file: Path):
        self.config = config
        self.encodings_file = encodings_file
        self._encodings: list[np.ndarray] | None = None

    def load(self) -> list[np.ndarray]:
        import numpy as np

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
            found = encode_faces(image, self.config)
            if not found:
                raise ValueError(f"No face found in enrollment image: {image_path}")
            encodings.append(found[0])

        self.save_encodings(encodings)
        return len(encodings)

    def guided_enroll(
        self,
        *,
        camera_source: int | str = 0,
        frame_width: int = 640,
        frame_height: int = 480,
        samples: int = 5,
        capture_interval_seconds: float = 1.2,
        append: bool = False,
        preview: bool = True,
    ) -> GuidedEnrollmentResult:
        import cv2

        if samples < 1:
            raise ValueError("samples must be at least 1.")

        cap = cv2.VideoCapture(camera_source)
        if frame_width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
        if frame_height:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)
        if not cap.isOpened():
            raise RuntimeError(f"Unable to open camera source: {camera_source}")

        prompts = enrollment_prompts(samples)
        captured: list[np.ndarray] = []
        last_capture_at = 0.0
        window_name = "Hermes Guardian enrollment"

        try:
            while len(captured) < samples:
                ok, frame = cap.read()
                if not ok or frame is None or frame.size == 0:
                    raise RuntimeError("Camera returned a blank frame during enrollment.")

                prompt = prompts[len(captured)]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                locations = detect_face_locations(rgb, self.config)
                status = _sample_status(len(locations))
                now = time.monotonic()

                if len(locations) == 1:
                    encodings = encode_faces(rgb, self.config, locations=locations)
                    if encodings and now - last_capture_at >= capture_interval_seconds:
                        captured.append(encodings[0])
                        last_capture_at = now
                        status = f"captured {len(captured)}/{samples}"
                        print(f"{status}: {prompt}", flush=True)

                if preview:
                    display = _annotate_enrollment_frame(
                        frame.copy(),
                        locations,
                        prompt=prompt,
                        status=status,
                        captured=len(captured),
                        samples=samples,
                    )
                    cv2.imshow(window_name, display)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord("q")):
                        raise KeyboardInterrupt
                else:
                    print(f"{len(captured)}/{samples} {prompt}: {status}", end="\r", flush=True)
                    time.sleep(0.05)
        finally:
            cap.release()
            if preview:
                try:
                    cv2.destroyWindow(window_name)
                except cv2.error:
                    cv2.destroyAllWindows()

        all_encodings = list(captured)
        if append and self.encodings_file.exists():
            all_encodings = self.load() + all_encodings
        self.save_encodings(all_encodings)
        return GuidedEnrollmentResult(
            samples=len(captured),
            output_file=self.encodings_file,
            appended=append,
        )

    def save_encodings(self, encodings: list[np.ndarray]) -> None:
        import numpy as np

        if not encodings:
            raise ValueError("At least one face encoding is required.")
        self.encodings_file.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(self.encodings_file, encodings=np.asarray(encodings))
        self._encodings = encodings

    def match_frame(self, frame_bgr: np.ndarray) -> FaceMatch:
        import cv2
        import face_recognition
        import numpy as np

        known = self.load()
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        locations = detect_face_locations(rgb, self.config)
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


def detect_face_locations(image_rgb: np.ndarray, config: FaceConfig) -> list[tuple[int, int, int, int]]:
    import face_recognition

    return face_recognition.face_locations(
        image_rgb,
        number_of_times_to_upsample=config.upsample,
        model=config.detection_model,
    )


def encode_faces(
    image_rgb: np.ndarray,
    config: FaceConfig,
    *,
    locations: list[tuple[int, int, int, int]] | None = None,
) -> list[np.ndarray]:
    import face_recognition

    return face_recognition.face_encodings(
        image_rgb,
        known_face_locations=locations,
        num_jitters=1,
        model="small",
    )


def enrollment_prompts(samples: int) -> list[str]:
    base = [
        "Look straight at the camera",
        "Turn your head slightly left",
        "Turn your head slightly right",
        "Tilt your chin slightly up",
        "Tilt your chin slightly down",
        "Move a little closer",
        "Move a little farther back",
    ]
    return [base[index % len(base)] for index in range(samples)]


def _sample_status(face_count: int) -> str:
    if face_count == 0:
        return "no face found"
    if face_count > 1:
        return "multiple faces found"
    return "hold still"


def _annotate_enrollment_frame(
    frame: np.ndarray,
    locations: list[tuple[int, int, int, int]],
    *,
    prompt: str,
    status: str,
    captured: int,
    samples: int,
) -> np.ndarray:
    import cv2

    for top, right, bottom, left in locations:
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 200, 80), 2)
    cv2.putText(frame, prompt, (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, status, (20, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (80, 220, 255), 2)
    cv2.putText(
        frame,
        f"{captured}/{samples} samples - q to cancel",
        (20, frame.shape[0] - 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
    )
    return frame
