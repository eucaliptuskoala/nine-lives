"""
REQUIRED SECURITY UNIT TESTS — BUG 1 (digitize auth, ownership, rate limiting).

These tests verify the fix applied in tasks 3.1-3.6 of the
`security-audit-fixes` bugfix spec: `POST /api/digitize` and
`GET /api/digitize/status/{task_id}` now require a verified `CurrentUser`,
derive `user_id` from the token (never from the request body), verify
`game_run` ownership before any pipeline work, enforce task ownership on
status polls, and rate-limit per authenticated user.

Fixture/double style mirrors `tests/test_digitize_pipeline.py` and
`tests/test_battle_router.py`: a `FakeSupabase` in-memory double for the
persistence pipeline, and `app.dependency_overrides[get_current_user]` to
simulate an authenticated caller (left uninstalled to exercise the real 401
path).

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6, 2.10, Design Property 1**
"""

from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import routers.digitize as digitize_router
import services.digitize as digitize_service
from auth import AuthUser, get_current_user
from main import app
from services.task_store import create_task

from ._fakes import FAKE_BREED, FAKE_COLORS, FAKE_AVATAR_URL, make_card, await_completion, FakeSupabase

USER_ID = "user-owned-1"
GAME_RUN_ID = "run-owned-1"
CAT_NAME = "Sir Pounce"





# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_rate_limiter_and_overrides():
    """Reset the module-level rate-limit state and auth overrides around every
    test in this file, so tests never leak state into one another."""
    digitize_router._rate_limit_requests.clear()
    yield
    digitize_router._rate_limit_requests.clear()
    app.dependency_overrides.clear()


def _patch_pipeline(monkeypatch, fake):
    monkeypatch.setattr(digitize_service, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(digitize_service, "classify_breed", lambda _b: FAKE_BREED)
    monkeypatch.setattr(digitize_service, "extract_colors", lambda _b: FAKE_COLORS)
    monkeypatch.setattr(digitize_service, "generate_card", lambda **kw: make_card(CAT_NAME))
    monkeypatch.setattr(digitize_service, "generate_avatar", lambda _p: FAKE_AVATAR_URL)


# ─── 1. POST 401 without token ───────────────────────────────────────────────


def test_post_without_token_returns_401_and_never_creates_a_task(monkeypatch):
    """No Authorization header (auth NOT overridden) -> 401, and `create_task`
    (the digitize router's binding, called before any pipeline work) is never
    reached."""

    def _boom(*args, **kwargs):
        raise AssertionError("create_task should not be called when unauthenticated")

    monkeypatch.setattr(digitize_router, "create_task", _boom)

    with TestClient(app) as client:
        resp = client.post(
            "/api/digitize",
            data={"game_run_id": GAME_RUN_ID, "cat_name": CAT_NAME},
            files={"file": ("kitty.jpg", b"\xff\xd8\xff-fake-jpeg", "image/jpeg")},
        )

    assert resp.status_code == 401


# ─── 2. POST derives owner from token; `user_id` field is gone ─────────────


def test_post_ignores_extra_user_id_field_owner_comes_from_token(monkeypatch):
    """The endpoint no longer declares a `user_id` form field. Passing one
    anyway is simply dropped by FastAPI (unknown form fields are ignored), and
    the resulting cat/task are owned by the authenticated token's `user_id`,
    never by the extra field's value. Directly tests bugfix.md 2.3."""
    fake = FakeSupabase(
        tables={
            "game_run": [
                {"id": GAME_RUN_ID, "user_id": USER_ID, "status": "DIGITIZING"}
            ]
        }
    )
    _patch_pipeline(monkeypatch, fake)
    monkeypatch.setattr(digitize_router, "get_supabase_client", lambda: fake)

    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id=USER_ID)

    with TestClient(app) as client:
        resp = client.post(
            "/api/digitize",
            data={
                "game_run_id": GAME_RUN_ID,
                "cat_name": CAT_NAME,
                "user_id": "someone-else",  # not a declared field -> dropped
            },
            files={"file": ("kitty.jpg", b"\xff\xd8\xff-fake-jpeg", "image/jpeg")},
        )
        assert resp.status_code == 202, resp.text
        task_id = resp.json()["task_id"]
        status_resp = await_completion(client, task_id)

    assert status_resp.status_code == 200
    result = status_resp.json()["result"]
    assert result["user_id"] == USER_ID
    assert result["user_id"] != "someone-else"


# ─── 3. POST 403 on foreign game_run_id, no work performed ─────────────────


def test_post_foreign_game_run_returns_403_with_no_records_and_no_task(
    monkeypatch,
):
    """A `game_run` owned by a different user -> 403, with `create_task` never
    invoked (so no task/pipeline work) and no `cat`/`ability` rows written."""
    fake = FakeSupabase(
        tables={
            "game_run": [
                {"id": GAME_RUN_ID, "user_id": "other-user", "status": "DIGITIZING"}
            ]
        }
    )
    monkeypatch.setattr(digitize_router, "get_supabase_client", lambda: fake)

    mock_create_task = Mock(side_effect=AssertionError("create_task should not run"))
    monkeypatch.setattr(digitize_router, "create_task", mock_create_task)

    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id=USER_ID)

    with TestClient(app) as client:
        resp = client.post(
            "/api/digitize",
            data={"game_run_id": GAME_RUN_ID, "cat_name": CAT_NAME},
            files={"file": ("kitty.jpg", b"\xff\xd8\xff-fake-jpeg", "image/jpeg")},
        )

    assert resp.status_code == 403
    mock_create_task.assert_not_called()
    assert fake.tables.get("cat", []) == []
    assert fake.tables.get("ability", []) == []


# ─── 4. Status 401 without token ────────────────────────────────────────────


def test_status_without_token_returns_401():
    """GET status with no Authorization header (auth NOT overridden) -> 401."""
    with TestClient(app) as client:
        resp = client.get("/api/digitize/status/some-task-id")

    assert resp.status_code == 401


# ─── 5. Status 403 on foreign task, 200 for the owner ──────────────────────


def test_status_foreign_task_returns_403_owner_gets_200():
    """A task created for `owner-A` polled by `owner-B` -> 403; polled by
    `owner-A` -> 200 (owners can still read their own tasks)."""
    task = create_task(owner_id="owner-A")

    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id="owner-B")
    with TestClient(app) as client:
        resp_foreign = client.get(f"/api/digitize/status/{task.id}")
    assert resp_foreign.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id="owner-A")
    with TestClient(app) as client:
        resp_owner = client.get(f"/api/digitize/status/{task.id}")
    assert resp_owner.status_code == 200


# ─── 6. Rate limiter — 6th request in the window returns 429 ───────────────


def test_rate_limiter_blocks_sixth_request_for_same_user():
    """5 calls to `check_rate_limit` for a fixed user_id succeed; the 6th
    raises an HTTPException with status_code 429."""
    user_id = "rl-user-1"

    for _ in range(5):
        digitize_router.check_rate_limit(user_id)

    with pytest.raises(HTTPException) as exc_info:
        digitize_router.check_rate_limit(user_id)

    assert exc_info.value.status_code == 429


def test_rate_limiter_is_scoped_per_user():
    """A different user_id is unaffected by another user's exhausted limit
    (limits are per-user, not global)."""
    user_a = "rl-user-a"
    user_b = "rl-user-b"

    for _ in range(5):
        digitize_router.check_rate_limit(user_a)
    with pytest.raises(HTTPException) as exc_info:
        digitize_router.check_rate_limit(user_a)
    assert exc_info.value.status_code == 429

    # A fresh user is not affected by user_a's rate limit state.
    digitize_router.check_rate_limit(user_b)
