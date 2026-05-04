---
name: hermes-guardian
description: Use this skill when working with the hermes-guardian Raspberry Pi room guardian tool, including installing it from Git, configuring phone-based home/away detection, enrolling owner face photos, running the guardian CLI, or interpreting its local JSON state and event log for Hermes-style agents.
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
guardian enroll-guided --config ~/.config/hermes-guardian/config.yaml
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
- Default person detection is `yolo26n.pt` at `image_size: 320` and `sample_fps: 1.0` for Raspberry Pi 4 comfort.
- If detection is too slow, export YOLO26 nano with `yolo export model=yolo26n.pt format=ncnn` and set `detection.model` to `yolo26n_ncnn_model`.
- If `guardian watch` is not running, use `guardian check-presence` for a one-shot phone update.
- Use `guardian clear-alert` to acknowledge an alert; do not manually edit the JSON state.
- Prefer `guardian enroll-guided` for initial setup. Use `--no-preview` over SSH without a display.
- If face matching is unreliable, rerun guided enrollment with more samples from the webcam angle and lighting.
- If camera commands fail, check `v4l2-ctl --list-devices`, camera index, and Linux camera permissions.
