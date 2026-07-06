"""
Avatar Generator — Hugging Face-powered pixel-art avatar generation.

Uses FLUX.1-schnell via HF Inference Providers (fal.ai) to create
a pixel-art cat sprite from the image_prompt field.

Related: Requirements 1.4, 6.4
"""

import os

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from PIL import Image

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
MODEL = "black-forest-labs/FLUX.1-schnell"
PROVIDER = "fal-ai"


def _build_prompt(subject_prompt: str) -> str:
    return (
        f"Generate a pixel-art avatar for a game character. "
        f"The character: {subject_prompt}. "
        f"Style: pixel-art game sprite, 64x64 pixels, transparent background, "
        f"facing forward, centred, clean outlines, vibrant colours, "
        f"no text, no UI elements."
    )


def generate_avatar(image_prompt: str) -> Image.Image:
    if not HF_TOKEN:
        raise ValueError("HF_TOKEN is not set")

    prompt = _build_prompt(image_prompt)

    client = InferenceClient(provider=PROVIDER, api_key=HF_TOKEN)
    return client.text_to_image(prompt, model=MODEL)
