"""
Unit tests for `services/classify.py` (breed classifier).

The transformers ViT model is never loaded: we monkeypatch `_get_classifier`
to return a fake callable, so no heavy ML deps or network are required. These
tests verify the top-1 label is returned and that ANY failure falls back to the
default breed.

Covers Requirements 2.1, 2.2, 2.3.
"""

import pytest

import services.classify as classify
from services.classify import DEFAULT_BREED, classify_breed


@pytest.fixture(autouse=True)
def reset_classifier_cache():
    """Ensure the module-level singleton doesn't leak between tests."""
    classify._classifier = None
    yield
    classify._classifier = None


def _fake_predictions(*labels):
    """Build a fake transformers-style prediction list (sorted by score desc)."""
    return [
        {"label": label, "score": 1.0 - i * 0.1}
        for i, label in enumerate(labels)
    ]


def _make_fake_classifier(predictions):
    """A fake classifier callable that ignores the image and returns predictions."""
    def _classifier(_image):
        return predictions
    return _classifier


# A tiny valid PNG so PIL.Image.open succeeds for the happy path.
def _tiny_png_bytes() -> bytes:
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (120, 90, 60)).save(buf, format="PNG")
    return buf.getvalue()


def test_returns_top_1_label(monkeypatch):
    """classify_breed returns the highest-scoring label."""
    predictions = _fake_predictions("Sphynx", "Bengal", "Persian")
    monkeypatch.setattr(
        classify, "_get_classifier", lambda: _make_fake_classifier(predictions)
    )

    result = classify_breed(_tiny_png_bytes())
    assert result == "Sphynx"


def test_fallback_when_loader_raises(monkeypatch):
    """If the model loader raises, the default breed is returned."""
    def _boom():
        raise RuntimeError("model failed to load")

    monkeypatch.setattr(classify, "_get_classifier", _boom)

    result = classify_breed(_tiny_png_bytes())
    assert result == DEFAULT_BREED


def test_fallback_on_invalid_image_bytes(monkeypatch):
    """Invalid image bytes cause a fallback to the default breed."""
    # Loader would work, but PIL.Image.open fails on garbage bytes first.
    predictions = _fake_predictions("Sphynx")
    monkeypatch.setattr(
        classify, "_get_classifier", lambda: _make_fake_classifier(predictions)
    )

    result = classify_breed(b"not-an-image")
    assert result == DEFAULT_BREED


def test_fallback_when_inference_raises(monkeypatch):
    """If the classifier callable raises during inference, fall back."""
    def _classifier(_image):
        raise ValueError("inference blew up")

    monkeypatch.setattr(classify, "_get_classifier", lambda: _classifier)

    result = classify_breed(_tiny_png_bytes())
    assert result == DEFAULT_BREED
