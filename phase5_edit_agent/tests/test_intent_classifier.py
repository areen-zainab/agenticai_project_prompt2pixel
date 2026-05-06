from phase5_edit_agent.agents.intent_classifier import classify_intent


queries_and_expected = [
    ("Change voice tone", "audio"),
    ("Make the scene darker", "video_frame"),
    ("Add background music", "audio"),
    ("Remove the subtitle", "video"),
    ("Change character design", "video_frame"),
    ("Speed up this scene", "video"),
    ("Regenerate the script", "script"),
    ("Make the narrator sound sad", "audio"),
    ("Add fade transitions between scenes", "video"),
    ("Rewrite scene 2 dialogue", "script"),
]


def test_intent_classification_accuracy():
    for query, expected_target in queries_and_expected:
        intent = classify_intent(query)
        assert intent.target == expected_target


def test_intent_fallback_parses_video_parameters(monkeypatch):
    from phase5_edit_agent.agents import intent_classifier as mod

    def _raise(*args, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(mod, "chat_json", _raise)
    intent = classify_intent("Remove subtitles and use wipe left transition")
    assert intent.target == "video"
    assert intent.parameters.get("add_subtitles") is False
    assert intent.parameters.get("transition_style") == "wipe_left"


def test_intent_uses_llm_schema_when_available(monkeypatch):
    from phase5_edit_agent.agents import intent_classifier as mod

    def _fake_chat_json(*args, **kwargs):
        return {
            "intent": "change_voice_tone",
            "target": "audio",
            "scope": "scene:2",
            "parameters": {"tone": "whispered"},
            "confidence": 0.97,
        }

    monkeypatch.setattr(mod, "chat_json", _fake_chat_json)
    intent = classify_intent("Make scene 2 voice whispered")
    assert intent.intent == "change_voice_tone"
    assert intent.target == "audio"
    assert intent.scope == "scene:2"
    assert intent.parameters["tone"] == "whispered"
    assert intent.confidence > 0.9
