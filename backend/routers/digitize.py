import os
import threading
import time
from collections import deque
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, UploadFile, File
from dotenv import load_dotenv

from auth import CurrentUser
from models.schemas import CatResponse
from services.digitize import (
    digitize,
    DigitizeGenerationError,
    DigitizePersistenceError,
    DigitizeStorageError,
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


def _load_game_run(supabase, game_run_id: str, user_id: str) -> dict:
    """Fetch the game_run, verifying it exists and is owned by the user.

    Mirrors `routers/battle.py::_load_game_run`: 404 if the run does not exist,
    403 if it belongs to another user.
    """
    try:
        result = (
            supabase.table("game_run").select("*").eq("id", game_run_id).execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load game run: {exc}")

    if not result.data:
        raise HTTPException(status_code=404, detail="Game run not found.")

    game_run = result.data[0]

    if str(game_run.get("user_id")) != str(user_id):
        raise HTTPException(
            status_code=403,
            detail="You do not own this game run.",
        )

    return game_run


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

    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{content_type}'. Allowed: JPEG, PNG, WebP.",
        )

    image_bytes = await file.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        size_mb = len(image_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed size is 10 MB.",
        )

    # Verify ownership of the game_run BEFORE any pipeline work (Req 2.1-2.4).
    supabase = get_supabase_client()
    _load_game_run(supabase, game_run_id, user_id)

    # Rate limit AFTER auth+ownership, BEFORE enqueueing billed pipeline work.
    check_rate_limit(user_id)

    task = create_task(owner_id=user_id)

    def run():
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
            update_task(task.id, status=TaskStatus.COMPLETED, result=cat)
        except DigitizeGenerationError as exc:
            update_task(task.id, status=TaskStatus.FAILED, error=str(exc))
        except Exception as exc:
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
