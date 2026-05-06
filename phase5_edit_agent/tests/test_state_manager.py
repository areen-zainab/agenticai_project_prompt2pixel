from phase5_edit_agent.state_manager import StateManager


def test_state_manager_get_version_roundtrip():
    manager = StateManager()
    version = manager.snapshot(
        state_json={"k": "v"},
        description="unit-test-snapshot",
        asset_paths=[],
    )
    record = manager.get_version(version)
    assert record.version == version
    assert record.description == "unit-test-snapshot"
    assert record.state_json["k"] == "v"
