---
name: hermes-guardian
description: Use this skill when working with the hermes-guardian Raspberry Pi room guardian tool, including installing it from Git, configuring phone-based home/away detection, running OpenCV person detection, optional face enrollment, running the guardian CLI, or interpreting its local JSON state and event log for Hermes-style agents.
---

# Hermes Guardian

Use `hermes-guardian` as a local CLI tool on the Raspberry Pi that owns the webcam. The tool decides home/away from the configured phone IP and only runs continuous person detection while away.

## Agent Workflow

1. Confirm the repo is installed on the Pi and the virtualenv is active.
2. Check configuration at `~/.config/hermes-guardian/config.yaml`.
3. Check current state with:

```bash
guardian status --config ~/.config/hermes-guardian/config.yaml
```

4. Treat `alert_active: true` in the state JSON as the flag that an unknown person was detected.
5. Read recent events from `~/.local/state/hermes-guardian/events.jsonl` when explaining what happened.

## Setup Commands

```bash
sudo apt install -y python3-venv python3-pip python3-yaml python3-numpy python3-opencv v4l-utils
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
pip install -e .
guardian init-config --path ~/.config/hermes-guardian/config.yaml
guardian test-camera --config ~/.config/hermes-guardian/config.yaml
guardian watch --config ~/.config/hermes-guardian/config.yaml
guardian clear-alert --config ~/.config/hermes-guardian/config.yaml
```

## State Contract

The state file defaults to `~/.local/state/hermes-guardian/state.json`.

Important fields:

- `mode`: `home`, `away`, or `guardian`.
- `phone_reachable`: whether the last phone ping succeeded.
- `guardian_mode`: whether continuous camera detection is active.
- `alert_active`: whether an unknown-person alert is currently active.
- `last_event`: latest state-changing event.
- `last_intruder_event_at`: last unknown-person detection time.
- `missed_phone_count` / `returned_phone_count`: grace-window counters.
- `presence_score`, `presence_threshold`, and `presence_signals`: why the tool decided home or away.

## Guidance

- Do not assume one missed ping means the user left; the tool uses a grace window.
- For iPhones, prefer router/AP association via `presence.router_command`; ping alone is unreliable during sleep.
- Router command contract: exit `0` means associated/home, nonzero means away.
- Use multi-signal scoring by giving router association a strong weight and ping a weak supporting weight.
- To actively notify Hermes, configure `notify.command`; the command receives `GUARDIAN_EVENT`, `GUARDIAN_STATE_FILE`, `GUARDIAN_EVENT_LOG`, and `GUARDIAN_SNAPSHOT`.
- Default person detection is OpenCV HOG, which avoids `torch`, `ultralytics`, `dlib`, and `face-recognition`.
- On Debian/Raspberry Pi OS, use `python3-opencv` and a `--system-site-packages` venv instead of pip-building OpenCV.
- Default identity is phone-presence based: person plus reachable phone means owner/home; person plus unreachable phone raises the alert flag.
- YOLO26 is optional: install `.[yolo]`, set `detection.backend: "yolo"`, and use `yolo26n.pt` or an NCNN export. The code filters YOLO to COCO `person` with `classes=[0]`.
- If `guardian watch` is not running, use `guardian check-presence` for a one-shot phone update.
- Use `guardian clear-alert` to acknowledge an alert; do not manually edit the JSON state.
- Face matching is optional: install `.[face]`, set `face.enabled: true`, then run `guardian enroll-guided`.
- If camera commands fail, check `v4l2-ctl --list-devices`, camera index, and Linux camera permissions.
