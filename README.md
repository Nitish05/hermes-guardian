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

On the Raspberry Pi 4:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip cmake build-essential \
  libcamera-dev v4l-utils

git clone <your-repo-url> hermes-guardian
cd hermes-guardian
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -e .
```

The default install does not require `torch`, `ultralytics`, `dlib`, or
`face-recognition`.

For local development, install test dependencies with `pip install -e ".[dev]"`.

## Person Detection Model

The default detector is OpenCV's built-in pretrained HOG people detector:

```yaml
detection:
  backend: "hog"
  confidence: 0.0

camera:
  sample_fps: 1.0
```

This path is intentionally lightweight for Raspberry Pi 4. It uses only OpenCV and avoids
the long `torch` and `dlib` installs. Guardian mode only needs to notice that a person
entered the room, not process every camera frame.

The default identity rule is phone-presence based:

- person detected and phone reachable: treat as owner/home
- person detected and phone unreachable: raise `alert_active`

### Optional YOLO26 Upgrade

If you want better person detection and can tolerate the heavier install, install:

```bash
pip install -e ".[yolo]"
```

Then set:

```yaml
detection:
  backend: "yolo"
  model: "yolo26n.pt"
  confidence: 0.45
  image_size: 320
```

For better ARM performance, export YOLO26 nano to NCNN on the Pi:

```bash
yolo export model=yolo26n.pt format=ncnn
```

Then update the config:

```yaml
detection:
  model: "yolo26n_ncnn_model"
```

Keep `yolo26n.pt` for the simplest first setup. Avoid larger YOLO26 variants on a Pi 4
unless you have tested that the lower FPS is acceptable.

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
