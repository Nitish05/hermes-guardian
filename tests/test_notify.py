import sys

from hermes_guardian.config import NotifyConfig
from hermes_guardian.notify import send_unknown_person_notification


def test_notify_returns_false_when_not_configured(tmp_path):
    result = send_unknown_person_notification(
        NotifyConfig(),
        state_file=tmp_path / "state.json",
        event_log=tmp_path / "events.jsonl",
        snapshot=None,
    )

    assert result.sent is False
    assert "not configured" in result.detail


def test_notify_command_receives_guardian_environment(tmp_path):
    marker = tmp_path / "marker.txt"
    script = (
        "import os, pathlib; "
        f"pathlib.Path({str(marker)!r}).write_text(os.environ['GUARDIAN_EVENT'] + '\\n' + os.environ['GUARDIAN_SNAPSHOT'])"
    )

    result = send_unknown_person_notification(
        NotifyConfig(command=f"{sys.executable} -c {script!r}"),
        state_file=tmp_path / "state.json",
        event_log=tmp_path / "events.jsonl",
        snapshot=tmp_path / "snapshot.jpg",
    )

    assert result.sent is True
    assert marker.read_text(encoding="utf-8").splitlines() == [
        "unknown_person",
        str(tmp_path / "snapshot.jpg"),
    ]
