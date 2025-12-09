from scripts.graph_utils import compute_heatmap_graph_width


def test_graph_width_minimum_applies():
    assert compute_heatmap_graph_width(0) == 200
    assert compute_heatmap_graph_width(-5) == 200


def test_graph_width_scales_with_letters():
    assert compute_heatmap_graph_width(1) == 200
    assert compute_heatmap_graph_width(2) == 200
    assert compute_heatmap_graph_width(5) == 200
    assert compute_heatmap_graph_width(6) == 240
    assert compute_heatmap_graph_width(10) == 400


def test_graph_width_custom_parameters():
    assert compute_heatmap_graph_width(3, min_width=100, per_letter=30) == 100
    assert compute_heatmap_graph_width(4, min_width=80, per_letter=50) == 200
