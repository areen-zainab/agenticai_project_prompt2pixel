import pytest
from unittest.mock import patch
from phase1_writers_room.graph.workflow import build_graph
from phase1_writers_room.graph.state import initial_state

@pytest.fixture
def mock_mcp():
    with patch("phase1_writers_room.agents.scriptwriter.discover_tool") as mock_disc_sw, \
         patch("phase1_writers_room.agents.scriptwriter.invoke_tool") as mock_inv_sw, \
         patch("phase1_writers_room.agents.character_designer.discover_tool") as mock_disc_char, \
         patch("phase1_writers_room.agents.character_designer.invoke_tool") as mock_inv_char, \
         patch("phase1_writers_room.agents.image_synthesizer.discover_tool") as mock_disc_img, \
         patch("phase1_writers_room.agents.image_synthesizer.invoke_tool") as mock_inv_img, \
         patch("shared.mcp_server.client.discover_tool") as mock_disc_mem, \
         patch("shared.mcp_server.client.invoke_tool") as mock_inv_mem:
        
        # Scriptwriter tool discovery + invocation
        mock_disc_sw.return_value = {"name": "generate_script_segment"}
        mock_inv_sw.return_value = {
            "scenes": [{
                "scene_id": 1,
                "location": "INT. TEST - DAY",
                "characters": ["TESTER"],
                "dialogue": [{"speaker": "TESTER", "line": "Test dialogue", "visual_cue": "Cues"}]
            }]
        }

        # Character designer uses MCP for profile generation + memory commits
        mock_disc_char.side_effect = lambda tool: {"name": tool}
        def _char_invoke(tool_name, tool_input, timeout=120):
            if tool_name == "generate_character_profile":
                return {
                    "name": tool_input.get("name", "TESTER"),
                    "personality_traits": ["curious", "brave", "witty"],
                    "appearance_description": "A test character used for integration testing.",
                    "reference_style": "cinematic realism",
                }
            if tool_name == "commit_memory":
                return {"status": "committed"}
            return {}
        mock_inv_char.side_effect = _char_invoke

        # Image synthesizer tool discovery + invocation
        mock_disc_img.return_value = {"name": "generate_character_image"}
        mock_inv_img.return_value = {"image_path": "test.png"}

        # Memory commit node uses MCP commit_memory
        mock_disc_mem.return_value = {"name": "commit_memory"}
        mock_inv_mem.return_value = {"status": "committed"}
        
        yield {
            "discover": mock_disc_sw,
            "invoke": mock_inv_sw,
            "invoke_char": mock_inv_char,
            "invoke_img": mock_inv_img,
            "invoke_mem": mock_inv_mem,
        }

def test_workflow_auto_mode(mock_mcp):
    # Skip HITL by mocking input or using non-interactive detection
    with patch("builtins.input", return_value="y"):
        graph = build_graph()
        state = initial_state(prompt="A test story")
        
        final_state = graph.invoke(state)
        
        assert final_state["status"] == "complete"
        assert len(final_state["script"]["scenes"]) == 1
        assert len(final_state["characters"]) > 0
