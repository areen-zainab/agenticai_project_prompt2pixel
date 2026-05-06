import pytest

pytest.importorskip("langgraph")

from phase5_edit_agent.agents.edit_executor import execute_edit
from phase5_edit_agent.agents.intent_classifier import EditIntent


class _StubStateMgr:
    def __init__(self):
        self._v = 0

    def snapshot(self, state_json, description, asset_paths):
        self._v += 1
        return self._v

    def history(self):
        return [{"version": self._v, "description": "stub"}]


def test_execute_edit_audio_scene_scoped(monkeypatch):
    from phase5_edit_agent.agents import edit_executor as mod

    class _StubOutput:
        def model_dump(self):
            return {"scenes": [{"scene_id": 2, "raw_mp4_path": "scene_02.mp4"}]}

    class _StubOrchestrator:
        def run_phase2(self, scene_id=None):
            assert scene_id == 2
            return _StubOutput()

    monkeypatch.setattr(mod, "get_orchestrator", lambda: _StubOrchestrator())
    monkeypatch.setattr(mod, "_collect_current_assets", lambda: [])
    monkeypatch.setattr(mod, "_phase2_scene_path", lambda scene_id: None)

    intent = EditIntent(
        intent="update_audio",
        target="audio",
        scope="scene:2",
        parameters={"tone": "sad"},
        confidence=0.9,
    )
    result = execute_edit(intent, {"query": "make scene 2 sad"}, state_mgr=_StubStateMgr())
    assert result["selected_scene_id"] == 2
    assert result["before_version"] == 1
    assert result["after_version"] == 2


def test_execute_edit_video_composition_params(monkeypatch):
    from phase5_edit_agent.agents import edit_executor as mod

    monkeypatch.setattr(mod, "_collect_current_assets", lambda: [])
    monkeypatch.setattr(mod, "_phase2_scene_path", lambda scene_id: None)
    monkeypatch.setattr(
        mod,
        "_rerun_phase3",
        lambda intent, current_state: {
            "phase3_output": {"ok": True},
            "composition_changes": {
                "transition_style": intent.parameters.get("transition_style"),
                "add_subtitles": intent.parameters.get("add_subtitles"),
            },
        },
    )
    intent = EditIntent(
        intent="update_video_composition",
        target="video",
        scope="all",
        parameters={"transition_style": "cut", "add_subtitles": False},
        confidence=0.95,
    )
    result = execute_edit(intent, {"query": "cut + no subtitles"}, state_mgr=_StubStateMgr())
    assert result["preview_video_url"] == "/api/phase3/video"
