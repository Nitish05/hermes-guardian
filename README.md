# hermes-guardian

`hermes-guardian` is a Raspberry Pi friendly room guardian for Hermes-style local agents.
It watches your phone's LAN reachability to decide whether you are home, and only runs
continuous webcam person detection when you are away. If a person appears while you are
away, it compares visible faces against enrolled owner photos and raises a local JSON flag
when the person is unknown.

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
  libopenblas-dev liblapack-dev libjpeg-dev libatlas-base-dev \
  libcamera-dev v4l-utils

git clone <your-repo-url> hermes-guardian
cd hermes-guardian
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -e ".[dev]"
```

If `face-recognition`/`dlib` is slow to install on the Pi, install a prebuilt wheel that
matches your OS/Python version or build it once and reuse the wheel.

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

## Enroll Your Face

For first-time setup, use guided webcam enrollment. It behaves like a simple Face ID
setup: the preview shows prompts, validates that exactly one face is visible, and
automatically captures several samples from different angles.

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
