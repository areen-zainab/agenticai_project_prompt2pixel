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
