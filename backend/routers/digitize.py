"""
Digitize Router — /api/digitize

Thin HTTP layer for cat digitization. It validates the uploaded image (content
type + size), reads the bytes, then delegates the entire ML/persistence pipeline
to the `services.digitize` orchestrator and returns the resulting `CatResponse`.

The endpoint is intentionally an OPEN mock endpoint (no auth requirement) for
now — see tasks 3.4 / 6.1. The heavy ML work happens behind the orchestrator,
which only CALLS the service functions (their heavy deps are lazily imported).

Related: Requirements 1.9, 2, 3, 4, 5, 6, 26.1, 26.2, 26.3, 26.4
"""

import os
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, UploadFile, File
from dotenv import load_dotenv

from models.schemas import CatResponse
from services.digitize import (
    digitize,
    DigitizeGenerationError,
    DigitizePersistenceError,
    DigitizeStorageError,
)

load_dotenv()

router = APIRouter(prefix="/digitize", tags=["digitize"])

# ─── Constants ────────────────────────────────────────────────────────────────

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ─── Pure validation helper ───────────────────────────────────────────────────


def is_allowed_image_filename(filename: str) -> bool:
    """Return True iff `filename`'s (lowercased) extension is an allowed image type.

    A file is allowed if and only if its extension is one of `.jpg`, `.jpeg`,
    `.png`, or `.webp` (case-insensitive). Pure and side-effect free so it can be
    property-tested in isolation.

    Related: Property 1 (Image File Validation) — Requirements 1.1, 27.1
    """
    if not filename:
        return False
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXTENSIONS


# ─── Endpoint ─────────────────────────────────────────────────────────────────


@router.post("", response_model=CatResponse)
async def digitize_cat(
    file: UploadFile = File(...),
    game_run_id: str = Form(...),
    user_id: str = Form(...),
    cat_name: str = Form(...),
    personality: Optional[str] = Form(None),
) -> CatResponse:
    """
    Digitize a cat photo into a game card.

    Validates the uploaded image, then delegates breed classification, colour
    extraction, card + avatar generation, and persistence to the orchestrator.
    """
    # ── 1. Validate file type ────────────────────────────────────────────────
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{content_type}'. Allowed: JPEG, PNG, WebP.",
        )

    # ── 2. Read & validate file size ─────────────────────────────────────────
    image_bytes = await file.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        size_mb = len(image_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed size is 10 MB.",
        )

    # ── 3. Delegate the pipeline to the orchestrator ─────────────────────────
    try:
        cat = await digitize(
            image_bytes=image_bytes,
            content_type=content_type,
            cat_name=cat_name,
            game_run_id=game_run_id,
            user_id=user_id,
            personality=personality,
        )
    except DigitizeGenerationError as exc:
        # Card / avatar generation failures are upstream (Gemini / FLUX) errors.
        raise HTTPException(status_code=502, detail=str(exc))
    except (DigitizeStorageError, DigitizePersistenceError) as exc:
        # Storage upload and DB persistence failures.
        raise HTTPException(status_code=500, detail=str(exc))

    return cat
