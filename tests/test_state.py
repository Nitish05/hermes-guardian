import json

from hermes_guardian.state import GuardianState, StateStore


def test_state_store_round_trip(tmp_path):
    store = StateStore(tmp_path / "state.json", tmp_path / "events.jsonl")
    state = GuardianState(mode="guardian", guardian_mode=True, alert_active=True)
    store.save(state)
    loaded = store.load()
    assert loaded.mode == "guardian"
    assert loaded.alert_active is True


def test_event_log_appends_json_lines(tmp_path):
    store = StateStore(tmp_path / "state.json", tmp_path / "events.jsonl")
    store.event("unknown_person", distance=0.7)
    line = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip()
    event = json.loads(line)
    assert event["event"] == "unknown_person"
    assert event["distance"] == 0.7

