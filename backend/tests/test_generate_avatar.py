"""
Unit tests for `services/generate_avatar.py` — FLUX.1-schnell avatar generation.

Both the HF InferenceClient factory and the Supabase storage upload are
monkeypatched, so no network calls (and no HF quota) are used. These tests
verify that `generate_avatar` generates an image, uploads it, and returns the
resulting public URL — and that both collaborators are invoked.

Covers Requirements 1.4, 5.2, 5.3, 6.4.
"""

import services.generate_avatar as ga
from services.generate_avatar import generate_avatar


class _FakeInferenceClient:
    """Records calls and returns a small in-memory PIL image."""

    def __init__(self):
        self.calls = []

    def text_to_image(self, prompt, model=None):
        from PIL import Image

        self.calls.append({"prompt": prompt, "model": model})
        return Image.new("RGBA", (8, 8), (200, 100, 50, 255))


FAKE_URL = "https://example.com/storage/avatars/fake.png"


def test_generate_avatar_returns_uploaded_url(monkeypatch):
    """generate_avatar returns the URL from the (mocked) upload helper."""
    monkeypatch.setattr(ga, "HF_TOKEN", "test-token")

    fake_client = _FakeInferenceClient()
    monkeypatch.setattr(ga, "_get_client", lambda: fake_client)

    uploaded = {}

    def _fake_upload(image_bytes, storage_path):
        uploaded["bytes"] = image_bytes
        uploaded["path"] = storage_path
        return FAKE_URL

    monkeypatch.setattr(ga, "_upload_png", _fake_upload)

    result = generate_avatar("an orange tabby warrior cat")

    assert result == FAKE_URL

    # The FLUX client was called with the built prompt + model.
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["model"] == ga.MODEL
    assert "pixel-art" in fake_client.calls[0]["prompt"]

    # The upload helper received PNG bytes under a uuid-based avatars/ path.
    assert uploaded["path"].startswith("avatars/")
    assert uploaded["path"].endswith(".png")
    assert uploaded["bytes"][:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic number


def test_generate_avatar_raises_without_hf_token(monkeypatch):
    """No HF_TOKEN -> ValueError before any generation/upload."""
    monkeypatch.setattr(ga, "HF_TOKEN", None)

    def _should_not_be_called():  # pragma: no cover
        raise AssertionError("_get_client should not be called without a token")

    monkeypatch.setattr(ga, "_get_client", _should_not_be_called)

    try:
        generate_avatar("a cat")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_generate_avatar_uses_unique_paths(monkeypatch):
    """Two generations produce distinct uuid-based storage paths."""
    monkeypatch.setattr(ga, "HF_TOKEN", "test-token")
    monkeypatch.setattr(ga, "_get_client", lambda: _FakeInferenceClient())

    paths = []
    monkeypatch.setattr(ga, "_upload_png", lambda b, p: paths.append(p) or FAKE_URL)

    generate_avatar("cat one")
    generate_avatar("cat two")

    assert len(paths) == 2
    assert paths[0] != paths[1]
