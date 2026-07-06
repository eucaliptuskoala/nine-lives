"""
Property-based tests for image file validation.

**Property 1: Image File Validation**
**Validates: Requirements 1.1, 27.1**

For any file selected for upload, the system SHALL accept the file if and only
if the file extension is `.jpg`, `.jpeg`, `.png`, or `.webp` (case-insensitive).

These tests target the pure `is_allowed_image_filename` helper in
`routers/digitize.py`, generating random base names paired with both allowed and
disallowed extensions and asserting the helper's boolean matches the spec.
"""

from hypothesis import given, strategies as st

from routers.digitize import is_allowed_image_filename

ALLOWED_EXTS = [".jpg", ".jpeg", ".png", ".webp"]
DISALLOWED_EXTS = [
    ".gif",
    ".bmp",
    ".tiff",
    ".svg",
    ".pdf",
    ".txt",
    ".exe",
    ".jpg.txt",
    ".heic",
    ".mp4",
    "",  # no extension
]

# Base names: letters/digits/underscores/dashes/dots/spaces, may include dots
# inside the name so we exercise splitext behaviour on multi-dot filenames.
base_name = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="_- .",
    ),
    min_size=1,
    max_size=40,
).filter(lambda s: s.strip(". ") != "")


def _random_case(s: str, data) -> str:
    """Randomly upper/lower each char to exercise case-insensitivity."""
    flags = data.draw(st.lists(st.booleans(), min_size=len(s), max_size=len(s)))
    return "".join(c.upper() if f else c.lower() for c, f in zip(s, flags))


@given(name=base_name, ext=st.sampled_from(ALLOWED_EXTS), data=st.data())
def test_allowed_extensions_are_accepted(name, ext, data):
    """Any filename ending in an allowed extension (any case) is accepted."""
    filename = f"{name}{_random_case(ext, data)}"
    assert is_allowed_image_filename(filename) is True


@given(name=base_name, ext=st.sampled_from(DISALLOWED_EXTS))
def test_disallowed_extensions_are_rejected(name, ext):
    """Any filename ending in a non-image extension is rejected."""
    filename = f"{name}{ext}"
    # Guard: the random base name must not itself end in an allowed extension
    # once the (possibly empty) disallowed ext is appended.
    from routers.digitize import ALLOWED_EXTENSIONS
    import os

    _, actual_ext = os.path.splitext(filename)
    expected = actual_ext.lower() in ALLOWED_EXTENSIONS
    assert is_allowed_image_filename(filename) is expected


@given(
    name=base_name,
    ext=st.sampled_from(ALLOWED_EXTS + DISALLOWED_EXTS),
    data=st.data(),
)
def test_acceptance_iff_extension_allowed(name, ext, data):
    """The helper accepts a filename iff its lowercased extension is allowed."""
    import os
    from routers.digitize import ALLOWED_EXTENSIONS

    filename = f"{name}{_random_case(ext, data)}"
    _, actual_ext = os.path.splitext(filename)
    expected = actual_ext.lower() in ALLOWED_EXTENSIONS
    assert is_allowed_image_filename(filename) is expected
