"""Phase 2 graph compiles without importing Phase 1 workflow."""

from phase2_studio_floor.graph.workflow import build_scene_graph


def test_build_scene_graph_compiles():
    g = build_scene_graph()
    assert g is not None
