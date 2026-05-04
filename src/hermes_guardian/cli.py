from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import GuardianConfig, write_default_config
from .state import StateStore


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"guardian: {exc}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="guardian")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=None, help="Path to config YAML.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_config = subparsers.add_parser("init-config", help="Write a default config file.")
    init_config.add_argument("--path", required=True, help="Where to write the config.")
    init_config.set_defaults(func=_init_config)

    status = subparsers.add_parser("status", parents=[common], help="Print current JSON state.")
    status.set_defaults(func=_status)

    check_presence = subparsers.add_parser(
        "check-presence", parents=[common], help="Ping the phone once and update state."
    )
    check_presence.set_defaults(func=_check_presence)

    clear_alert = subparsers.add_parser("clear-alert", parents=[common], help="Clear alert_active in state.")
    clear_alert.set_defaults(func=_clear_alert)

    enroll = subparsers.add_parser("enroll", parents=[common], help="Enroll owner face images.")
    enroll.add_argument("--image", action="append", required=True, help="Owner image path. Repeatable.")
    enroll.set_defaults(func=_enroll)

    test_camera = subparsers.add_parser(
        "test-camera", parents=[common], help="Open camera and write one test frame."
    )
    test_camera.add_argument("--output", default=None, help="Optional output JPG path.")
    test_camera.set_defaults(func=_test_camera)

    test_detect = subparsers.add_parser(
        "test-detect", parents=[common], help="Run one person-detection pass."
    )
    test_detect.set_defaults(func=_test_detect)

    watch_cmd = subparsers.add_parser("watch", parents=[common], help="Run the guardian loop.")
    watch_cmd.set_defaults(func=_watch)
    return parser


def _load(args) -> tuple[GuardianConfig, StateStore]:
    config = GuardianConfig.load(args.config)
    config.validate()
    config.ensure_dirs()
    return config, StateStore(config.paths.state_file, config.paths.event_log)


def _init_config(args) -> int:
    path = write_default_config(args.path)
    print(path)
    return 0


def _status(args) -> int:
    config = GuardianConfig.load(args.config)
    store = StateStore(config.paths.state_file, config.paths.event_log)
    print(json.dumps(store.load().to_dict(), indent=2, sort_keys=True))
    return 0


def _check_presence(args) -> int:
    from .guardian import update_presence_once

    config, store = _load(args)
    state = update_presence_once(config, store)
    print(json.dumps(state.to_dict(), indent=2, sort_keys=True))
    return 0 if state.phone_reachable else 2


def _clear_alert(args) -> int:
    config = GuardianConfig.load(args.config)
    store = StateStore(config.paths.state_file, config.paths.event_log)
    state = store.load()
    state.alert_active = False
    state.last_event = "alert_cleared"
    store.save(state)
    store.event("alert_cleared", mode=state.mode)
    print(json.dumps(state.to_dict(), indent=2, sort_keys=True))
    return 0


def _enroll(args) -> int:
    from .recognition import OwnerRecognizer

    config, _store = _load(args)
    images = [Path(image).expanduser() for image in args.image]
    missing = [str(image) for image in images if not image.exists()]
    if missing:
        raise FileNotFoundError(f"Enrollment images not found: {missing}")
    recognizer = OwnerRecognizer(config.face, config.paths.encodings_file)
    count = recognizer.enroll(images)
    print(f"enrolled {count} owner face encoding(s) at {config.paths.encodings_file}")
    return 0


def _test_camera(args) -> int:
    import cv2

    from .detection import Camera

    config, _store = _load(args)
    with Camera(config.camera) as camera:
        frame = camera.read()
    output = Path(args.output).expanduser() if args.output else config.paths.snapshot_dir / "camera-test.jpg"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), frame):
        raise RuntimeError(f"Failed to write test frame: {output}")
    print(output)
    return 0


def _test_detect(args) -> int:
    from .detection import Camera, PersonDetector

    config, _store = _load(args)
    with Camera(config.camera) as camera:
        frame = camera.read()
    detector = PersonDetector(config.detection)
    detections = detector.detect(frame)
    print(json.dumps([d.to_dict() for d in detections], indent=2, sort_keys=True))
    return 0


def _watch(args) -> int:
    from .guardian import watch

    config, store = _load(args)
    watch(config, store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
