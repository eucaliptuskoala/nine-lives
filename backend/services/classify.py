"""
Breed Classifier — local HuggingFace `transformers` ViT.

Runs the `dima806/cat_breed_image_detection` image-classification model
in-process to predict a cat breed from raw image bytes. There are no network
API calls (inference is local), so there is no HTTP retry/backoff — on any
failure we fall back to a sensible default breed.

Heavy dependencies (`transformers`, `PIL`) are imported lazily inside the
loader/function so that importing this module (and running the mocked test
suite) never requires the ML extra to be installed. Install the real pipeline
deps with `uv sync --extra ml`.

Related: Requirements 2.1, 2.2, 2.3
"""

import io
import logging

logger = logging.getLogger(__name__)

MODEL_NAME = "dima806/cat_breed_image_detection"
DEFAULT_BREED = "Domestic Shorthair"

# Module-level singleton cache for the loaded classification pipeline.
_classifier = None


def _get_classifier():
    """Lazily build and cache the transformers image-classification pipeline.

    Heavy imports happen inside this function so module import stays light.
    Monkeypatch this function in tests to return a fake callable.
    """
    global _classifier
    if _classifier is None:
        # Lazy import — only needed when the real model is used.
        from transformers import pipeline

        _classifier = pipeline("image-classification", model=MODEL_NAME)
    return _classifier


def classify_breed(image_bytes: bytes) -> str:
    """Classify the top-1 cat breed from raw image bytes.

    Returns the highest-scoring label from the local ViT classifier. On ANY
    exception (invalid bytes, model load failure, inference error) this returns
    the fallback default breed rather than raising.
    """
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))

        classifier = _get_classifier()
        predictions = classifier(image)

        # transformers returns a list sorted by score descending.
        return predictions[0]["label"]
    except Exception:
        logger.exception("Breed classification failed — falling back to default breed")
        return DEFAULT_BREED
