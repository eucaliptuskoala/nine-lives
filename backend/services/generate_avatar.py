"""
Avatar Generator — Hugging Face-powered pixel-art avatar generation.

Uses FLUX.1-schnell via HF Inference Providers (fal.ai) to create a retro
pixel-art cat sprite from the `image_prompt` field, uploads the resulting PNG to
Supabase storage under a uuid-based path, and returns the public URL.

FLUX.1-schnell is guidance-free (no negative-prompt field), so the retro
pixel-art style AND the "avoid" terms are folded into a SINGLE POSITIVE prompt
by `_build_prompt` (e.g. "no text, no UI elements").

The InferenceClient factory and the storage-upload helper are small, separately
monkeypatchable functions so tests can mock both with no network access.

Related: Requirements 1.4, 5.2, 5.3, 6.4
"""

import io
import os
import uuid

from dotenv import load_dotenv

from services.supabase_client import get_supabase_client

load_dotenv()

HF_TOKEN = os.getenv("HUGGINGFACE_API_KEY")
MODEL = "black-forest-labs/FLUX.1-schnell"
PROVIDER = "fal-ai"
BUCKET_NAME = "cat-images"
# FLUX generation can be slow; give the inference call a generous timeout.
GENERATION_TIMEOUT = 30


def _build_prompt(subject_prompt: str) -> str:
    """Single POSITIVE prompt — style + avoid terms folded in (no negative field)."""
    return (
        f"Generate a pixel-art avatar for a game character. "
        f"The character: {subject_prompt}. "
        f"Style: pixel-art game sprite, 64x64 pixels, transparent background, "
        f"facing forward, centred, clean outlines, vibrant colours, "
        f"no text, no UI elements."
    )


def _get_client():
    """Build the HF InferenceClient. Monkeypatch in tests to avoid network."""
    from huggingface_hub import InferenceClient

    return InferenceClient(provider=PROVIDER, api_key=HF_TOKEN, timeout=GENERATION_TIMEOUT)


def _upload_png(image_bytes: bytes, storage_path: str) -> str:
    """Upload PNG bytes to Supabase storage and return the public URL.

    Kept as a small helper so tests can monkeypatch the whole upload with no
    network access.
    """
    client = get_supabase_client()
    client.storage.from_(BUCKET_NAME).upload(
        storage_path,
        image_bytes,
        file_options={
            "content-type": "image/png",
            "cache-control": "3600",
            "upsert": "false",
        },
    )
    return client.storage.from_(BUCKET_NAME).get_public_url(storage_path)


def generate_avatar(image_prompt: str) -> str:
    """Generate a pixel-art avatar and return its public storage URL."""
    if not HF_TOKEN:
        raise ValueError("HF_TOKEN is not set")

    prompt = _build_prompt(image_prompt)

    client = _get_client()
    image = client.text_to_image(prompt, model=MODEL)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()

    storage_path = f"avatars/{uuid.uuid4()}.png"
    return _upload_png(image_bytes, storage_path)
