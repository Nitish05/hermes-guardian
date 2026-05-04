import sys

from hermes_guardian.config import PhoneConfig, PresenceConfig
from hermes_guardian.presence import PresenceTracker, evaluate_presence


def test_presence_requires_missed_ping_grace_window():
    tracker = PresenceTracker(PhoneConfig(missed_ping_threshold=3, return_ping_threshold=2))
    assert tracker.observe(False) == "phone_unreachable"
    assert not tracker.guardian_mode
    assert tracker.observe(False) == "phone_unreachable"
    assert not tracker.guardian_mode
    assert tracker.observe(False) == "entered_guardian"
    assert tracker.guardian_mode


def test_presence_requires_return_grace_window():
    tracker = PresenceTracker(
        PhoneConfig(missed_ping_threshold=1, return_ping_threshold=2),
        guardian_mode=True,
    )
    assert tracker.observe(True) == "phone_reachable"
    assert tracker.guardian_mode
    assert tracker.observe(True) == "returned_home"
    assert not tracker.guardian_mode


def test_router_command_can_make_presence_home_without_ping():
    presence = evaluate_presence(
        PhoneConfig(ip="127.0.0.1"),
        PresenceConfig(
            home_score_threshold=2.0,
            ping_enabled=False,
            router_command=f"{sys.executable} -c 'raise SystemExit(0)'",
            router_command_weight=2.0,
        ),
    )

    assert presence.home is True
    assert presence.score == 2.0
    assert presence.signals[0].name == "router_command"


def test_failed_router_command_does_not_meet_score():
    presence = evaluate_presence(
        PhoneConfig(ip="127.0.0.1"),
        PresenceConfig(
            home_score_threshold=2.0,
            ping_enabled=False,
            router_command=f"{sys.executable} -c 'raise SystemExit(1)'",
            router_command_weight=2.0,
        ),
    )

    assert presence.home is False
    assert presence.score == 0.0
