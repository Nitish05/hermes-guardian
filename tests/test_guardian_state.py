from hermes_guardian.config import PhoneConfig
from hermes_guardian.guardian import _apply_presence
from hermes_guardian.presence import PresenceTracker
from hermes_guardian.state import GuardianState


def test_apply_presence_persists_away_counts_before_guardian():
    state = GuardianState()
    tracker = PresenceTracker(PhoneConfig(missed_ping_threshold=2))
    event = tracker.observe(False)

    _apply_presence(state, reachable=False, tracker=tracker, event=event)

    assert state.mode == "away"
    assert state.guardian_mode is False
    assert state.missed_phone_count == 1


def test_apply_presence_enters_guardian_after_threshold():
    state = GuardianState(missed_phone_count=1)
    tracker = PresenceTracker(PhoneConfig(missed_ping_threshold=2), missed_count=1)
    event = tracker.observe(False)

    _apply_presence(state, reachable=False, tracker=tracker, event=event)

    assert state.mode == "guardian"
    assert state.guardian_mode is True
    assert state.last_event == "entered_guardian"

