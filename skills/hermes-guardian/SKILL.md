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

## Guidance

- Do not assume one missed ping means the user left; the tool uses a grace window.
- Default person detection is OpenCV HOG, which avoids `torch`, `ultralytics`, `dlib`, and `face-recognition`.
- Default identity is phone-presence based: person plus reachable phone means owner/home; person plus unreachable phone raises the alert flag.
- YOLO26 is optional: install `.[yolo]`, set `detection.backend: "yolo"`, and use `yolo26n.pt` or an NCNN export.
- If `guardian watch` is not running, use `guardian check-presence` for a one-shot phone update.
- Use `guardian clear-alert` to acknowledge an alert; do not manually edit the JSON state.
- Face matching is optional: install `.[face]`, set `face.enabled: true`, then run `guardian enroll-guided`.
- If camera commands fail, check `v4l2-ctl --list-devices`, camera index, and Linux camera permissions.
