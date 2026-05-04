from __future__ import annotations

import signal
import time
from dataclasses import dataclass
from pathlib import Path

from .config import GuardianConfig
from .presence import PresenceResult, PresenceTracker, evaluate_presence
from .state import GuardianState, StateStore, now_iso


@dataclass(slots=True)
class RuntimeFlags:
    stop: bool = False


def update_presence_once(config: GuardianConfig, store: StateStore) -> GuardianState:
    state = store.load()
    tracker = PresenceTracker(
        config.phone,
        missed_count=state.missed_phone_count,
        returned_count=state.returned_phone_count,
        guardian_mode=state.guardian_mode,
    )
    presence = evaluate_presence(config.phone, config.presence)
    event = tracker.observe(presence.home)
    _apply_presence(state, presence, tracker, event)
    store.save(state)
    store.event(
        event or "presence_checked",
        phone_reachable=presence.home,
        mode=state.mode,
        **presence.to_event_payload(),
    )
    return state


def watch(config: GuardianConfig, store: StateStore) -> None:
    from .detection import Camera, PersonDetector

    config.validate()
    config.ensure_dirs()
    flags = RuntimeFlags()

    def _stop(signum, frame) -> None:
        flags.stop = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    loaded_state = store.load()
    tracker = PresenceTracker(
        config.phone,
        missed_count=loaded_state.missed_phone_count,
        returned_count=loaded_state.returned_phone_count,
        guardian_mode=loaded_state.guardian_mode,
    )
    detector: PersonDetector | None = None
    recognizer = None
    last_ping_at = 0.0
    last_alert_at = 0.0
    consecutive_unknown = 0
    frame_delay = 1.0 / config.camera.sample_fps
    camera = None

    try:
        while not flags.stop:
            now = time.monotonic()
            ping_interval = (
                config.phone.ping_interval_guardian_seconds
                if tracker.guardian_mode
                else config.phone.ping_interval_home_seconds
            )
            if now - last_ping_at >= ping_interval:
                presence = evaluate_presence(config.phone, config.presence)
                event = tracker.observe(presence.home)
                state = store.load()
                _apply_presence(state, presence, tracker, event)
                if event == "returned_home":
                    state.alert_active = False
                    consecutive_unknown = 0
                store.save(state)
                store.event(
                    event or "presence_checked",
                    phone_reachable=presence.home,
                    mode=state.mode,
                    **presence.to_event_payload(),
                )
                last_ping_at = now

            if not tracker.guardian_mode:
                if camera is not None:
                    camera.__exit__(None, None, None)
                    camera = None
                time.sleep(1.0)
                continue

            detector = detector or PersonDetector(config.detection)
            if camera is None:
                camera = Camera(config.camera)
                camera.__enter__()
            frame = camera.read()
            detections = detector.detect(frame)
            if not detections:
                consecutive_unknown = 0
                time.sleep(frame_delay)
                continue

            state = store.load()
            state.last_person_detected_at = now_iso()
            state.last_event = "person_detected"
            store.event("person_detected", count=len(detections), mode="guardian")

            if config.face.enabled and recognizer is None:
                from .recognition import OwnerRecognizer

                recognizer = OwnerRecognizer(config.face, config.paths.encodings_file)
            owner_seen, unknown_seen, best_distance = _classify_person_presence(
                config=config,
                state=state,
                frame=frame,
                detections=detections,
                recognizer=recognizer,
            )

            if owner_seen:
                consecutive_unknown = 0
                state.alert_active = False
                state.last_owner_match_at = now_iso()
                state.last_event = "owner_match"
                store.event("owner_match", distance=best_distance)
            elif unknown_seen:
                consecutive_unknown += 1
                if consecutive_unknown >= config.detection.consecutive_unknown_threshold:
                    cooldown_ok = now - last_alert_at >= config.detection.alert_cooldown_seconds
                    state.alert_active = True
                    state.last_intruder_event_at = now_iso()
                    state.last_event = "unknown_person"
                    if cooldown_ok:
                        last_alert_at = now
                        snapshot = _write_snapshot(config.paths.snapshot_dir, frame)
                        store.event(
                            "unknown_person",
                            distance=best_distance,
                            snapshot=str(snapshot) if snapshot else None,
                        )
                        _notify_unknown_person(config, store, snapshot)
            store.save(state)
            time.sleep(frame_delay)
    finally:
        if camera is not None:
            camera.__exit__(None, None, None)


def _classify_person_presence(
    *,
    config: GuardianConfig,
    state: GuardianState,
    frame,
    detections,
    recognizer,
) -> tuple[bool, bool, float | None]:
    if state.phone_reachable and not config.face.enabled:
        return True, False, None
    if not config.face.enabled:
        return False, True, None

    from .detection import crop_detection

    if recognizer is None:
        raise RuntimeError("Face recognizer is required when face.enabled is true.")
    owner_seen = False
    unknown_seen = False
    best_distance = None
    for detection in detections:
        crop = crop_detection(frame, detection)
        match = recognizer.match_frame(crop)
        if match.matched:
            owner_seen = True
            best_distance = match.distance
            break
        unknown_seen = True
        best_distance = match.distance if match.distance is not None else best_distance
    return owner_seen, unknown_seen, best_distance


def _apply_presence(
    state: GuardianState,
    presence: PresenceResult,
    tracker: PresenceTracker,
    event: str | None,
) -> None:
    state.phone_reachable = presence.home
    state.guardian_mode = tracker.guardian_mode
    state.mode = "guardian" if tracker.guardian_mode else ("home" if presence.home else "away")
    state.last_event = event
    state.missed_phone_count = tracker.missed_count
    state.returned_phone_count = tracker.returned_count
    state.presence_score = presence.score
    state.presence_threshold = presence.threshold
    state.presence_signals = presence.to_event_payload()["presence_signals"]
    if presence.home:
        state.last_seen_phone_at = now_iso()


def _write_snapshot(snapshot_dir: Path, frame) -> Path | None:
    import cv2

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"unknown-{now_iso().replace(':', '-')}.jpg"
    ok = cv2.imwrite(str(path), frame)
    return path if ok else None


def _notify_unknown_person(config: GuardianConfig, store: StateStore, snapshot: Path | None) -> None:
    from .notify import send_unknown_person_notification

    result = send_unknown_person_notification(
        config.notify,
        state_file=config.paths.state_file,
        event_log=config.paths.event_log,
        snapshot=snapshot,
    )
    store.event("notify_unknown_person", sent=result.sent, detail=result.detail)
