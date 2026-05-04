from hermes_guardian.config import GuardianConfig, PhoneConfig
from hermes_guardian.guardian import _apply_presence, _classify_person_presence
from hermes_guardian.presence import PresenceResult, PresenceSignal, PresenceTracker
from hermes_guardian.state import GuardianState


def _presence(home: bool) -> PresenceResult:
    return PresenceResult(
        home=home,
        score=1.0 if home else 0.0,
        threshold=1.0,
        signals=(PresenceSignal("test", home, 1.0),),
    )


def test_apply_presence_persists_away_counts_before_guardian():
    state = GuardianState()
    tracker = PresenceTracker(PhoneConfig(missed_ping_threshold=2))
    event = tracker.observe(False)

    _apply_presence(state, presence=_presence(False), tracker=tracker, event=event)

    assert state.mode == "away"
    assert state.guardian_mode is False
    assert state.missed_phone_count == 1


def test_apply_presence_enters_guardian_after_threshold():
    state = GuardianState(missed_phone_count=1)
    tracker = PresenceTracker(PhoneConfig(missed_ping_threshold=2), missed_count=1)
    event = tracker.observe(False)

    _apply_presence(state, presence=_presence(False), tracker=tracker, event=event)

    assert state.mode == "guardian"
    assert state.guardian_mode is True
    assert state.last_event == "entered_guardian"


def test_apply_presence_records_signal_scores():
    state = GuardianState()
    tracker = PresenceTracker(PhoneConfig())

    _apply_presence(state, presence=_presence(True), tracker=tracker, event="phone_reachable")

    assert state.presence_score == 1.0
    assert state.presence_threshold == 1.0
    assert state.presence_signals[0]["name"] == "test"


def test_phone_reachable_classifies_person_as_owner_without_face():
    state = GuardianState(phone_reachable=True)

    owner_seen, unknown_seen, distance = _classify_person_presence(
        config=GuardianConfig(),
        state=state,
        frame=None,
        detections=[object()],
        recognizer=None,
    )

    assert owner_seen is True
    assert unknown_seen is False
    assert distance is None


def test_phone_unreachable_classifies_person_as_unknown_without_face():
    state = GuardianState(phone_reachable=False)

    owner_seen, unknown_seen, distance = _classify_person_presence(
        config=GuardianConfig(),
        state=state,
        frame=None,
        detections=[object()],
        recognizer=None,
    )

    assert owner_seen is False
    assert unknown_seen is True
    assert distance is None
