from hermes_guardian.config import PhoneConfig
from hermes_guardian.presence import PresenceTracker


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

