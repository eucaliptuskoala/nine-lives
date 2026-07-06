"""
Property-based tests for `services/extract_colors.py` — the pure
`_palette_from_labels` helper (pytest + hypothesis).

This targets the dependency-light color-palette math ONLY. It does NOT import
ultralytics / sklearn / cv2, so it runs with no heavy ML deps and no network.

Property 2 — Color Palette Well-Formedness:
    For any KMeans centroids (RGB ints 0-255) and positive per-cluster pixel
    counts, `_palette_from_labels` produces, for every cluster:
      * a hex string matching ^#[0-9A-F]{6}$ (uppercase RRGGBB), and
      * a ratio in [0.0, 1.0],
    and the ratios sum to ~1.0.

**Validates: Requirements 3.2**
"""

import re

from hypothesis import given, strategies as st

from services.extract_colors import _palette_from_labels

HEX_RE = re.compile(r"^#[0-9A-F]{6}$")

# RGB channel values (ints in the 0-255 range) and positive pixel counts.
channel_st = st.integers(min_value=0, max_value=255)
centroid_st = st.tuples(channel_st, channel_st, channel_st)
count_st = st.integers(min_value=1, max_value=1_000_000)


@given(
    data=st.lists(
        st.tuples(centroid_st, count_st),
        min_size=1,
        max_size=8,
    )
)
def test_property_2_palette_well_formed(data):
    """Every hex is #RRGGBB uppercase, every ratio in [0,1], ratios sum to ~1."""
    centroids = [c for c, _ in data]
    counts = [n for _, n in data]

    palette = _palette_from_labels(centroids, counts)

    assert len(palette) == len(data)

    for entry in palette:
        assert HEX_RE.match(entry["hex"]), f"bad hex: {entry['hex']}"
        assert 0.0 <= entry["ratio"] <= 1.0

    total_ratio = sum(entry["ratio"] for entry in palette)
    assert abs(total_ratio - 1.0) < 1e-9


@given(
    centroid=st.tuples(
        st.floats(min_value=0, max_value=255),
        st.floats(min_value=0, max_value=255),
        st.floats(min_value=0, max_value=255),
    ),
    count=count_st,
)
def test_property_2_float_centroids_are_clamped_and_rounded(centroid, count):
    """Float centroids (as KMeans emits) still produce a valid #RRGGBB hex."""
    palette = _palette_from_labels([centroid], [count])
    assert HEX_RE.match(palette[0]["hex"])
    # Single cluster ⇒ ratio is exactly 1.0.
    assert palette[0]["ratio"] == 1.0


def test_property_2_out_of_range_channels_clamped():
    """Channels above 255 / below 0 are clamped into the valid byte range."""
    palette = _palette_from_labels([(300.0, -20.0, 127.4)], [10])
    assert palette[0]["hex"] == "#FF007F"  # 300→255, -20→0, 127.4→127
