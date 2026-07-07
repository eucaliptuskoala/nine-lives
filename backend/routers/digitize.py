import os
import threading
import time
from collections import deque
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, UploadFile, File
from dotenv import load_dotenv

from auth import CurrentUser
from routers._helpers import load_game_run
from services.digitize import (
    digitize,
    DigitizeGenerationError,
)
from services.supabase_client import get_supabase_client
from services.task_store import (
    TaskStatus,
    create_task,
    get_task,
    update_task,
)

load_dotenv()

router = APIRouter(prefix="/digitize", tags=["digitize"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def is_allowed_image_filename(filename: str) -> bool:
    if not filename:
        return False
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXTENSIONS


# ─── Per-user in-process rate limiter ────────────────────────────────────────
#
# NOTE: This limiter is per-process (in-memory). If this API is horizontally
# scaled (multiple processes/instances), request counts will not be shared
# across processes and the effective limit will be higher than intended. Move
# to a shared store (e.g. Redis) if/when the API is deployed with more than
# one worker/instance.

_rate_limit_lock = threading.Lock()
_rate_limit_requests: dict[str, deque] = {}


def check_rate_limit(
    user_id: str, max_requests: int = 5, window_seconds: float = 60.0
) -> None:
    """Raise 429 if `user_id` has exceeded `max_requests` within `window_seconds`."""
    now = time.time()
    with _rate_limit_lock:
        timestamps = _rate_limit_requests.setdefault(user_id, deque())
        timestamps.append(now)
        while timestamps and timestamps[0] <= now - window_seconds:
            timestamps.popleft()
        if len(timestamps) > max_requests:
            raise HTTPException(
                status_code=429,
                detail="Too many digitize requests. Please wait a moment and try again.",
            )


@router.post("", status_code=202)
async def digitize_cat(
    user: CurrentUser,
    file: UploadFile = File(...),
    game_run_id: str = Form(...),
    cat_name: str = Form(...),
    personality: Optional[str] = Form(None),
) -> dict:
    user_id = user.user_id

    if not is_allowed_image_filename(file.filename or ""):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file extension. Allowed: .jpg, .jpeg, .png, .webp.",
        )

    if len(cat_name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Cat name must not be empty.")

    if len(cat_name) > 100:
        raise HTTPException(
            status_code=400,
            detail="Cat name must be 100 characters or fewer.",
        )

    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{content_type}'. Allowed: JPEG, PNG, WebP.",
        )

    # Read in chunks, aborting early if the file exceeds MAX_FILE_SIZE (OOM
    # prevention — a malicious client could send a multi-GB file otherwise).
    image_bytes = b""
    chunk_size = 256 * 1024  # 256 KB per read
    while len(image_bytes) <= MAX_FILE_SIZE:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        image_bytes += chunk
    if len(image_bytes) > MAX_FILE_SIZE:
        size_mb = len(image_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed size is 10 MB.",
        )

    # Verify ownership of the game_run BEFORE any pipeline work (Req 2.1-2.4).
    supabase = get_supabase_client()
    load_game_run(supabase, game_run_id, user_id)

    # Rate limit AFTER auth+ownership, BEFORE enqueueing billed pipeline work.
    check_rate_limit(user_id)

    task = create_task(owner_id=user_id)

    def run():
        import logging
        logger = logging.getLogger(__name__)
        try:
            update_task(task.id, status=TaskStatus.PROCESSING)
            cat = digitize(
                image_bytes=image_bytes,
                content_type=content_type,
                cat_name=cat_name,
                game_run_id=game_run_id,
                user_id=user_id,
                personality=personality,
            )
            # Convert CatResponse to dict for JSON serialization.
            cat_dict = cat.model_dump(mode="json")
            update_task(task.id, status=TaskStatus.COMPLETED, result=cat_dict)
        except DigitizeGenerationError as exc:
            logger.error(f"[DIGITIZE] Task {task.id} failed: {exc}")
            update_task(task.id, status=TaskStatus.FAILED, error=str(exc))
        except Exception as exc:
            logger.error(
                f"[DIGITIZE] Task {task.id} failed unexpectedly: {exc}", exc_info=True
            )
            update_task(task.id, status=TaskStatus.FAILED, error=str(exc))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    return {"task_id": task.id}


@router.get("/status/{task_id}")
async def get_digitize_status(task_id: str, user: CurrentUser) -> dict:
    task = get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.owner_id != user.user_id:
        raise HTTPException(
            status_code=403, detail="You do not own this digitize task."
        )

    response: dict = {"status": task.status.value}
    if task.status == TaskStatus.COMPLETED and task.result is not None:
        response["result"] = task.result
    elif task.status == TaskStatus.FAILED:
        response["error"] = task.error or "Digitization failed"

    return response
