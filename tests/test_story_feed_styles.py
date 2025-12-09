from pathlib import Path


def test_story_grid_has_horizontal_scroll():
    css = Path("ui/styles.css").read_text()
    assert "story-grid" in css
    assert "overflow-x: auto" in css
    assert "flex-wrap: nowrap" in css
    assert "scroll-snap-type: x mandatory" in css
    assert "align-items: flex-start" in css
    assert "gap: 2rem" in css
    assert "scroll-padding-inline" in css
    assert "padding: 1.25rem 0 1rem" in css


def test_story_cards_are_tall():
    css = Path("ui/styles.css").read_text()
    assert "min-height: 360px" in css
    assert "padding: 1.6rem" in css


def test_story_card_width_is_configurable():
    css = Path("ui/styles.css").read_text()
    assert "--story-card-width" in css
    assert "min-width: var(--story-card-width" in css
