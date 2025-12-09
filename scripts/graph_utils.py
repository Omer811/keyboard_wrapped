def compute_heatmap_graph_width(word_length: int, min_width: int = 200, per_letter: int = 40) -> int:
    """Compute the width for the word duration graph so each letter gets equal horizontal space."""
    if word_length <= 0:
        return min_width
    return max(min_width, word_length * per_letter)
