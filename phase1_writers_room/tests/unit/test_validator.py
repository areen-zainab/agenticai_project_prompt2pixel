import pytest
from phase1_writers_room.agents.validator import _check_scene_headings, _check_dialogue, _check_action_lines, _parse_script

def test_check_scene_headings_valid():
    text = "INT. KITCHEN - DAY\nSomething happens."
    assert _check_scene_headings(text) == []

def test_check_scene_headings_invalid():
    text = "KITCHEN - DAY\nSomething happens."
    errors = _check_scene_headings(text)
    assert len(errors) > 0
    assert "No scene headings found" in errors[0]

def test_check_dialogue_valid():
    text = "JOE\nHello there."
    assert _check_dialogue(text) == []

def test_check_dialogue_invalid():
    text = "Hello there."
    errors = _check_dialogue(text)
    assert len(errors) > 0
    assert "No dialogue labels detected" in errors[0]

def test_parse_script():
    text = """INT. KITCHEN - DAY
JOE
Hello there.
(Joe smiles)
How are you?
"""
    script = _parse_script(text)
    assert len(script["scenes"]) == 1
    scene = script["scenes"][0]
    assert scene["location"] == "INT. KITCHEN - DAY"
    assert "JOE" in scene["characters"]
    assert len(scene["dialogue"]) == 1
    assert scene["dialogue"][0]["speaker"] == "JOE"
    assert "Hello there. How are you?" in scene["dialogue"][0]["line"]
    assert "Joe smiles" in scene["dialogue"][0]["visual_cue"]
