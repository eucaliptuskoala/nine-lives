"""
PRESERVATION BASELINE TESTS — digitize owned/valid flow and 400 validations.

These tests capture the CURRENT (pre-fix) behavior of:
  - the owned/valid happy-path digitize flow (POST -> task_id -> poll -> COMPLETED
    with a `CatResponse`-shaped result), and
  - the existing 400 validation paths (unsupported content type; oversized file),

on the UNFIXED code, per bugfix.md 3.1 and 3.2 and design.md Property 4
("Preservation — Non-buggy inputs unchanged").

They are observation-only: they assert what the code does TODAY for inputs where
the BUG 1 bug condition does NOT hold (an "owned" request in today's terms, i.e. a
request whose `user_id`/`game_run_id` are mutually consistent in the fake table) and
for the pre-existing 400 branches, which run before any auth/ownership work either
way. No source file (`routers/digitize.py`, `services/task_store.py`,
`services/digitize.py`) is modified here.

After the BUG 1 fix lands (task 3, verified in task 3.9), these SAME tests should be
re-run UNCHANGED against the fixed code (now sending a real bearer token for the
owning user instead of relying on the unauthenticated form field) to confirm the
owned/valid flow and the 400 validations still behave identically -- i.e. that
`F'(X) == F(X)` for all `X` where `NOT C(X)`.

Fixture/double style is duplicated (minimally) from `tests/test_digitize_pipeline.py`
so this file has no dependency on bugcondition/pipeline test internals.
"""

import pytest
from fastapi.testclient import TestClient

import services.digitize as digitize_service
from auth import AuthUser, get_current_user
from main import app

from ._fakes import FAKE_BREED, FAKE_COLORS, FAKE_AVATAR_URL, make_card, await_completion, FakeSupabase

USER_ID = "user-owned-1"
GAME_RUN_ID = "run-owned-1"
CAT_NAME = "Sir Pounce"





@pytest.fixture
def fake_supabase(monkeypatch):
    """Mock the whole ML/persistence pipeline so no real network/model calls
    happen. Seeds a single `game_run` row owned by USER_ID -- the "owned"
    scenario for the happy-path preservation test."""
    fake = FakeSupabase(
        tables={
            "game_run": [
                {"id": GAME_RUN_ID, "user_id": USER_ID, "status": "DIGITIZING"},
            ]
        }
    )
    monkeypatch.setattr(digitize_service, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(digitize_service, "classify_breed", lambda _b: FAKE_BREED)
    monkeypatch.setattr(digitize_service, "extract_colors", lambda _b: FAKE_COLORS)
    monkeypatch.setattr(digitize_service, "generate_card", lambda **kw: make_card(CAT_NAME))
    monkeypatch.setattr(digitize_service, "generate_avatar", lambda _p: FAKE_AVATAR_URL)

    import routers.digitize as digitize_router

    monkeypatch.setattr(digitize_router, "get_supabase_client", lambda: fake)
    return fake


# ─── Test 1: owned happy-path flow (bugfix.md 3.1, design Property 4) ───────


def test_owned_happy_path_returns_202_then_completed_cat_response(fake_supabase):
    """
    PRESERVATION BASELINE (bugfix.md 3.1, design.md Property 4).

    Observed on current (pre-fix) code: a request whose `user_id` form field
    matches the owner of the referenced `game_run_id` (an "owned" request in
    today's terms -- there is no auth yet, so ownership is only as strong as
    the caller-supplied `user_id`) returns 202 with a `task_id`. Polling the
    status endpoint eventually returns COMPLETED with a `result` matching the
    `CatResponse` shape. Re-run this same test after the BUG 1 fix (with a real
    bearer token for USER_ID replacing the form field) to confirm the shape
    and terminal outcome are unchanged.
    """
    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id=USER_ID)
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/digitize",
                data={
                    "game_run_id": GAME_RUN_ID,
                    "cat_name": CAT_NAME,
                    "personality": "curious and aloof",
                },
                files={"file": ("kitty.jpg", b"\xff\xd8\xff-fake-jpeg", "image/jpeg")},
            )

            assert resp.status_code == 202, resp.text
            body = resp.json()
            assert "task_id" in body
            task_id = body["task_id"]

            status_resp = await_completion(client, task_id)
    finally:
        app.dependency_overrides.clear()

    assert status_resp.status_code == 200
    status_body = status_resp.json()
    assert status_body["status"] == "COMPLETED"
    assert "result" in status_body

    result = status_body["result"]
    # Shape check against CatResponse's required fields.
    expected_fields = {
        "id",
        "user_id",
        "name",
        "breed",
        "class_",
        "current_hp",
        "max_hp",
        "dmg",
        "defence",
        "spd",
        "mana",
        "max_mana",
        "lore",
        "avatar_url",
        "lives_remaining",
        "abilities",
        "source_image_url",
        "status",
        "wins",
        "created_at",
    }
    assert expected_fields.issubset(result.keys())

    assert result["user_id"] == USER_ID
    assert result["name"] == CAT_NAME
    assert result["breed"] == FAKE_BREED
    assert result["avatar_url"] == FAKE_AVATAR_URL
    assert result["personality"] == "curious and aloof"
    assert result["status"] == "ALIVE"
    assert result["lives_remaining"] == 9
    assert result["wins"] == 0
    assert len(result["abilities"]) == 4
    assert result["source_image_url"].startswith(
        "https://storage.example.com/cat-images/"
    )

    # The referenced game_run was linked and moved to IN_PROGRESS.
    run_row = fake_supabase.tables["game_run"][0]
    assert run_row["status"] == "IN_PROGRESS"
    assert run_row["cat_id"] == result["id"]

    cat_inserts = [i for i in fake_supabase.inserts if i["table"] == "cat"]
    assert len(cat_inserts) == 1


# ─── Test 2: unsupported file extension ──────────────────────────────────────


def test_unsupported_content_type_returns_400_before_pipeline_work(monkeypatch):
    """
    An unsupported file extension (e.g. `.gif`) returns 400 before any pipeline
    work -- the Supabase client is never even constructed.
    """

    def _boom():
        raise AssertionError("pipeline should not run for invalid file type")

    monkeypatch.setattr(digitize_service, "get_supabase_client", _boom)

    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id=USER_ID)
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/digitize",
                data={
                    "game_run_id": GAME_RUN_ID,
                    "cat_name": CAT_NAME,
                },
                files={"file": ("kitty.gif", b"GIF89a", "image/gif")},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "Unsupported file extension" in resp.json()["detail"]


# ─── Test 3: oversized file (bugfix.md 3.2, design Property 4) ─────────────


def test_oversized_file_returns_400_before_pipeline_work(monkeypatch):
    """
    PRESERVATION BASELINE (bugfix.md 3.2, design.md Property 4).

    Observed on current (pre-fix) code: a file larger than the 10 MB limit
    returns 400 with the existing size-limit error message, before any
    pipeline work runs (the Supabase client is never constructed). Re-run
    unchanged after the BUG 1 fix to confirm this behavior is preserved.
    """

    def _boom():
        raise AssertionError("pipeline should not run for oversized file")

    monkeypatch.setattr(digitize_service, "get_supabase_client", _boom)

    oversized_bytes = b"\xff\xd8\xff" + (b"0" * (10 * 1024 * 1024 + 1))

    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id=USER_ID)
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/digitize",
                data={
                    "game_run_id": GAME_RUN_ID,
                    "cat_name": CAT_NAME,
                },
                files={"file": ("kitty.jpg", oversized_bytes, "image/jpeg")},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "File too large" in resp.json()["detail"]
    assert "Maximum allowed size is 10 MB" in resp.json()["detail"]
