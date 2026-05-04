# hermes-guardian

`hermes-guardian` is a Raspberry Pi friendly room guardian for Hermes-style local agents.
It watches your phone's LAN reachability to decide whether you are home, and only runs
continuous webcam person detection when you are away. If a person appears while you are
away and your phone is not reachable, it raises a local JSON flag.

This is not a security-grade alarm system. Wi-Fi sleep, poor lighting, face angle, masks,
camera placement, and spoofing can all affect the result.

## What Hermes Reads

By default the current state is written to:

```text
~/.local/state/hermes-guardian/state.json
```

Hermes should treat these fields as the integration contract:

```json
{
  "mode": "home",
  "phone_reachable": true,
  "guardian_mode": false,
  "alert_active": false,
  "last_event": "phone_reachable",
  "missed_phone_count": 0,
  "returned_phone_count": 1
}
```

Events are appended as JSON lines to:

```text
~/.local/state/hermes-guardian/events.jsonl
```

## Raspberry Pi Install

On Debian 13 / Raspberry Pi OS, prefer distro OpenCV packages. This avoids pip-building
OpenCV while Ultralytics installs the YOLO runtime.

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip python3-yaml python3-numpy python3-opencv v4l-utils

git clone <your-repo-url> hermes-guardian
cd hermes-guardian
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
pip install -e .
```

The default install uses Ultralytics YOLO26n for person detection. It does not require
`dlib` or `face-recognition`. The project relies on Debian's `python3-opencv` through the
`--system-site-packages` virtualenv; Ultralytics may still install its own transitive
Python dependencies.

If you are not on Debian/Raspberry Pi OS and want pip to install OpenCV, use:

```bash
pip install -e ".[opencv-pip]"
```

For local development, install test dependencies with `pip install -e ".[dev]"`.

## Person Detection Model

The default detector is the pretrained Ultralytics YOLO26 nano COCO model. The runtime
filters YOLO output with `classes=[0]`, so it only detects COCO `person`.

```yaml
detection:
  backend: "yolo"
  model: "yolo26n.pt"
  confidence: 0.45
  image_size: 320

camera:
  sample_fps: 1.0
```

Guardian mode only needs to notice that a person entered the room, not process every
camera frame. Keep `sample_fps` low on a Raspberry Pi 4.

The default identity rule is phone-presence based:

- person detected and phone reachable: treat as owner/home
- person detected and phone unreachable: raise `alert_active`

For better ARM performance, export YOLO26 nano to NCNN on the Pi:

```bash
yolo export model=yolo26n.pt format=ncnn
```

Then update the config:

```yaml
detection:
  backend: "yolo"
  model: "yolo26n_ncnn_model"
```

Keep `yolo26n.pt` for the simplest first setup. Avoid larger YOLO26 variants on a Pi 4
unless you have tested that the lower FPS is acceptable.

### HOG Fallback

If YOLO is too heavy for your Pi, fall back to OpenCV's built-in HOG people detector:

```yaml
detection:
  backend: "hog"
  confidence: 0.0
```

## Configure

Create a config:

```bash
guardian init-config --path ~/.config/hermes-guardian/config.yaml
```

Edit the phone IP. Reserve this IP in your router so it does not change:

```yaml
phone:
  ip: "192.168.1.50"
```

### iPhone Presence

iPhones often stop answering ping while asleep, so the preferred signal is the router/AP
Wi-Fi association table. Configure a command that asks your router whether the iPhone is
currently associated:

```yaml
presence:
  home_score_threshold: 2.0
  ping_enabled: false
  router_command: "/usr/local/bin/is-iphone-associated"
  router_command_weight: 2.0
  router_command_timeout_seconds: 5.0
```

The command contract is simple:

- exit `0`: phone is home / associated
- any nonzero exit: phone is away / not associated

This keeps router-specific logic outside Hermes Guardian. The command can query UniFi,
OpenWrt, your router SSH/API, or any local script that checks the AP association table.

If you want multi-signal scoring, enable both router and ping:

```yaml
presence:
  home_score_threshold: 2.0
  ping_enabled: true
  ping_weight: 0.5
  router_command: "/usr/local/bin/is-iphone-associated"
  router_command_weight: 2.0
```

With that setup, router association is the decisive signal and ping is just supporting
evidence. The state JSON records `presence_score`, `presence_threshold`, and
`presence_signals` so Hermes can explain why it decided home or away.

### Alert Notification

When guardian mode sees a person while you are away, it always sets `alert_active: true`
and appends an `unknown_person` event. To actively notify Hermes, configure a command:

```yaml
notify:
  command: "/usr/local/bin/hermes-guardian-notify"
  timeout_seconds: 10.0
```

The command runs once per alert cooldown and receives:

```text
GUARDIAN_EVENT=unknown_person
GUARDIAN_STATE_FILE=~/.local/state/hermes-guardian/state.json
GUARDIAN_EVENT_LOG=~/.local/state/hermes-guardian/events.jsonl
GUARDIAN_SNAPSHOT=/path/to/snapshot.jpg
```

Point `notify.command` at a Hermes CLI wrapper, webhook script, or any local notifier that
can alert you. The durable state flag remains the source of truth even if notification
delivery fails.

The default webcam is camera index `0`. Check cameras with:

```bash
v4l2-ctl --list-devices
guardian test-camera --config ~/.config/hermes-guardian/config.yaml
```

## Optional Face Enrollment

Face enrollment is no longer required for the default setup. Install it only if you want
biometric matching in addition to phone presence:

```bash
pip install -e ".[face]"
```

Then enable it:

```yaml
face:
  enabled: true
```

Guided webcam enrollment behaves like a simple Face ID setup: the preview shows prompts,
validates that exactly one face is visible, and automatically captures several samples
from different angles.

```bash
guardian enroll-guided --config ~/.config/hermes-guardian/config.yaml
```

Use `--samples` to change the number of captures, and `--no-preview` when running over
SSH without a display:

```bash
guardian enroll-guided --config ~/.config/hermes-guardian/config.yaml --samples 7
guardian enroll-guided --config ~/.config/hermes-guardian/config.yaml --no-preview
```

If you already have clear owner photos from the camera's likely angle and lighting, you can
still enroll from files:

```bash
guardian enroll --config ~/.config/hermes-guardian/config.yaml --image owner1.jpg --image owner2.jpg
```

## Run

One-shot checks:

```bash
guardian check-presence --config ~/.config/hermes-guardian/config.yaml
guardian clear-alert --config ~/.config/hermes-guardian/config.yaml
guardian status --config ~/.config/hermes-guardian/config.yaml
guardian test-detect --config ~/.config/hermes-guardian/config.yaml
```

Main loop:

```bash
guardian watch --config ~/.config/hermes-guardian/config.yaml
```

When your phone misses enough ping checks, the tool enters guardian mode and starts camera
sampling. Before the missed-ping threshold is reached, the state mode is `away` but
`guardian_mode` remains false. When the phone is reachable for the configured recovery
count, it returns home and stops continuous camera detection.

## Optional systemd Service

Copy and edit the template:

```bash
sudo cp packaging/hermes-guardian.service /etc/systemd/system/hermes-guardian.service
sudo systemctl daemon-reload
sudo systemctl enable --now hermes-guardian
```

Update `User`, `WorkingDirectory`, and `ExecStart` in the service file to match the Pi.

## Agent Skill

The bundled skill lives in:

```text
skills/hermes-guardian/SKILL.md
```

Install that skill into the Hermes/Codex skill directory on the Pi, or have Hermes read it
from this repo when working with the guardian tool.
