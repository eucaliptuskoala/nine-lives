"""
BUG-CONDITION "BEFORE/AFTER" PAIR — BUG 1 (digitize auth & ownership).

This file is the standalone before/after companion required by the bugfix
methodology: task 1 wrote these four tests to assert the CURRENT (buggy)
behavior on unfixed code (a pass confirmed the bug existed); task 3.8 (this
revision) inverts every assertion to instead verify the FIX applied in tasks
3.1-3.7 of the `security-audit-fixes` bugfix spec:

  - `POST /api/digitize` now requires a verified `CurrentUser` and returns 401
    with no work performed when unauthenticated (bugfix.md 2.1).
  - The endpoint derives `user_id` from the verified token, never from a
    caller-supplied form field -- a spoofed `user_id` field is ignored
    (bugfix.md 2.3).
  - `game_run_id` ownership is checked before any pipeline work, so a foreign
    game_run returns 403 and is never mutated (bugfix.md 2.4).
  - `GET /api/digitize/status/{task_id}` requires a verified `CurrentUser` and
    enforces task ownership, so a non-owner (or unauthenticated caller) gets
    401/403 instead of the task result (bugfix.md 2.10).

They correspond to design.md's Property 1 ("Expected Behavior — Authenticated,
owner-scoped digitize with no work on failure"). All four tests are expected
to PASS against the current (fixed) code; a pass here is the "after" half of
the bug-condition methodology and confirms the fix is complete.

Fixture/double style mirrors `tests/test_digitize_security.py` (the required
unit tests written in task 3.7): a `FakeSupabase` in-memory double for the
persistence pipeline, and `app.dependency_overrides[get_current_user]` to
simulate an authenticated caller. Some duplication of that file's helpers is
kept here intentionally so this file stands alone as the "before/after" pair
for the bug it was written to demonstrate.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.10, Design Property 1**
"""

import time

import pytest
from fastapi.testclient import TestClient

import routers.digitize as digitize_router
import services.digitize as digitize_service
from auth import AuthUser, get_current_user
from main import app
from services.task_store import TaskStatus, create_task, update_task

USER_A = "user-aaaa"
USER_B = "user-bbbb"
GAME_RUN_A = "run-aaaa"
GAME_RUN_B = "run-bbbb"
CAT_NAME = "Sir Pounce"


# ─── Fake Supabase double (mirrors tests/test_digitize_pipeline.py) ──────────


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeStorageBucket:
    def __init__(self, client, bucket):
        self._client = client
        self._bucket = bucket

    def upload(self, path, data, file_options=None):
        self._client.uploads.append(
            {"bucket": self._bucket, "path": path, "options": file_options}
        )
        return {"path": path}

    def get_public_url(self, path):
        return f"https://storage.example.com/{self._bucket}/{path}"


class _FakeStorage:
    def __init__(self, client):
        self._client = client

    def from_(self, bucket):
        return _FakeStorageBucket(self._client, bucket)


class _FakeQuery:
    def __init__(self, client, table_name):
        self._client = client
        self._table = table_name
        self._op = None
        self._payload = None
        self._filters = {}

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def select(self, *_args):
        self._op = "select"
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def execute(self):
        if self._op == "insert":
            payload = self._payload
            rows = payload if isinstance(payload, list) else [payload]
            inserted = []
            for p in rows:
                row = dict(p)
                row.setdefault("id", f"{self._table}-{self._client.next_id()}")
                row.setdefault("created_at", "2024-01-01T00:00:00Z")
                self._client.tables.setdefault(self._table, []).append(row)
                inserted.append(row)
            self._client.inserts.append({"table": self._table, "payload": payload})
            return _FakeResult(inserted)

        rows = self._client.tables.get(self._table, [])

        def _matches(row):
            return all(str(row.get(k)) == str(v) for k, v in self._filters.items())

        matched = [r for r in rows if _matches(r)]

        if self._op == "update":
            self._client.updates.append(
                {
                    "table": self._table,
                    "payload": self._payload,
                    "filters": dict(self._filters),
                }
            )
            for r in matched:
                r.update(self._payload)

        return _FakeResult(matched)


class FakeSupabase:
    def __init__(self, tables=None):
        self.tables = tables or {}
        self.inserts = []
        self.updates = []
        self.uploads = []
        self.storage = _FakeStorage(self)
        self._id_counter = 0

    def next_id(self):
        self._id_counter += 1
        return self._id_counter

    def table(self, name):
        return _FakeQuery(self, name)


FAKE_BREED = "Siamese"
FAKE_COLORS = [{"hex": "#C0A080", "ratio": 0.6}, {"hex": "#8B6F47", "ratio": 0.4}]
FAKE_AVATAR_URL = "https://storage.example.com/cat-images/avatars/fake.png"


def make_card():
    return {
        "name": CAT_NAME,
        "class": "INTELLIGENCE",
        "max_hp": 120,
        "dmg": 30,
        "defence": 12,
        "spd": 18,
        "max_mana": 90,
        "lore": "A clever cat forged from pixels.",
        "image_prompt": "a siamese cat mage, cream and brown fur",
        "abilities": [
            {
                "name": "Claw",
                "dmg": 15,
                "type": "DMG",
                "effect": None,
                "cooldown": 1,
                "mana_cost": 10,
                "lore": "A quick swipe.",
                "is_special": False,
                "description": "Rake with claws.",
            },
            {
                "name": "Purr Shield",
                "dmg": 20,
                "type": "SHIELD",
                "effect": None,
                "cooldown": 2,
                "mana_cost": 25,
                "lore": "A soothing purr.",
                "is_special": False,
                "description": "Raise a shield.",
            },
            {
                "name": "Catnap",
                "dmg": 30,
                "type": "HEAL",
                "effect": "REGEN",
                "cooldown": 3,
                "mana_cost": 30,
                "lore": "A restorative snooze.",
                "is_special": False,
                "description": "Heal over time.",
            },
            {
                "name": "Nine Fury",
                "dmg": 45,
                "type": "TRUE_DMG",
                "effect": "STUN",
                "cooldown": 4,
                "mana_cost": 60,
                "lore": "The fury of nine lives.",
                "is_special": True,
                "description": "Unleash devastating fury.",
            },
        ],
    }


@pytest.fixture
def fake_supabase(monkeypatch):
    """Mock the whole ML/persistence pipeline so no real network/model calls
    happen; two game_run rows owned by different users seed the ownership
    check scenario (test 3)."""
    fake = FakeSupabase(
        tables={
            "game_run": [
                {"id": GAME_RUN_A, "user_id": USER_A, "status": "DIGITIZING"},
                {"id": GAME_RUN_B, "user_id": USER_B, "status": "DIGITIZING"},
            ]
        }
    )
    monkeypatch.setattr(digitize_service, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(digitize_router, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(digitize_service, "classify_breed", lambda _b: FAKE_BREED)
    monkeypatch.setattr(digitize_service, "extract_colors", lambda _b: FAKE_COLORS)
    monkeypatch.setattr(digitize_service, "generate_card", lambda **kw: make_card())
    monkeypatch.setattr(digitize_service, "generate_avatar", lambda _p: FAKE_AVATAR_URL)
    return fake


def _post_digitize(client, **form_overrides):
    form = {
        "game_run_id": GAME_RUN_A,
        "cat_name": CAT_NAME,
    }
    form.update(form_overrides)
    return client.post(
        "/api/digitize",
        data=form,
        files={"file": ("kitty.jpg", b"\xff\xd8\xff-fake-jpeg", "image/jpeg")},
    )


def _await_completion(client, task_id, timeout_s=10):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"/api/digitize/status/{task_id}")
        if resp.status_code != 200:
            return resp
        body = resp.json()
        if body["status"] in ("COMPLETED", "FAILED"):
            return resp
        time.sleep(0.1)
    pytest.fail("Task did not reach a terminal state within the deadline")


# ─── Isolation: reset rate limiter + auth overrides around every test ──────


@pytest.fixture(autouse=True)
def _isolate_rate_limiter_and_overrides():
    digitize_router._rate_limit_requests.clear()
    yield
    digitize_router._rate_limit_requests.clear()
    app.dependency_overrides.clear()


# ─── Test 1: unauthenticated POST is rejected (bugfix.md 2.1) ───────────────


def test_unauthenticated_post_is_rejected(fake_supabase, monkeypatch):
    """
    EXPECTED BEHAVIOR (bugfix.md 2.1, design.md Property 1).

    `POST /api/digitize` now requires a verified `CurrentUser`. This test
    asserts the FIXED behavior: a request with valid form data and NO
    `Authorization` header returns 401, `create_task` is never reached (no
    pipeline work is started), and no `cat`/`ability` records are written.
    This inverts the original bug-condition assertion from task 1, which
    expected this same request to return 202.
    """

    def _boom(*args, **kwargs):
        raise AssertionError("create_task should not be called when unauthenticated")

    monkeypatch.setattr(digitize_router, "create_task", _boom)

    with TestClient(app) as client:
        resp = _post_digitize(client)

    assert resp.status_code == 401

    cat_inserts = [i for i in fake_supabase.inserts if i["table"] == "cat"]
    assert cat_inserts == []


# ─── Test 2: spoofed user_id is ignored (bugfix.md 2.3) ─────────────────────


def test_spoofed_user_id_is_ignored(fake_supabase):
    """
    EXPECTED BEHAVIOR (bugfix.md 2.3, design.md Property 1).

    The endpoint no longer declares a `user_id` form field, and identity is
    derived from the verified token, not the request body. This test asserts
    the FIXED behavior: an authenticated caller (token subject = USER_A) who
    also supplies a spoofed `user_id=USER_B` form field still gets a cat
    owned by USER_A -- the extra field is dropped by FastAPI and has no
    effect on ownership. This inverts the original bug-condition assertion
    from task 1, which expected the spoofed `user_id` to determine ownership.
    """
    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id=USER_A)

    with TestClient(app) as client:
        resp = _post_digitize(
            client,
            user_id=USER_B,  # not a declared field -> dropped
            game_run_id=GAME_RUN_A,  # owned by USER_A (the real token subject)
        )

        assert resp.status_code == 202, resp.text
        task_id = resp.json()["task_id"]
        status_resp = _await_completion(client, task_id)

    assert status_resp.status_code == 200
    result = status_resp.json()["result"]
    assert result["user_id"] == USER_A
    assert result["user_id"] != USER_B


# ─── Test 3: foreign game_run_id returns 403, no mutation (bugfix.md 2.4) ───


def test_foreign_game_run_returns_403(fake_supabase):
    """
    EXPECTED BEHAVIOR (bugfix.md 2.4, design.md Property 1).

    Two `game_run` rows exist, owned by USER_A and USER_B respectively. This
    test authenticates as USER_A but supplies USER_B's `game_run_id`. It
    asserts the FIXED behavior: the request is rejected with 403 BEFORE any
    pipeline work, and the foreign (USER_B-owned) game_run is left untouched
    -- no `cat_id`/`status` mutation, and no task is created. This inverts
    the original bug-condition assertion from task 1, which expected the
    foreign run to be mutated with no ownership check.
    """
    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id=USER_A)

    with TestClient(app) as client:
        resp = _post_digitize(client, game_run_id=GAME_RUN_B)

    assert resp.status_code == 403

    foreign_run = next(
        r for r in fake_supabase.tables["game_run"] if r["id"] == GAME_RUN_B
    )
    # FIX: the foreign run (owned by USER_B) was NOT mutated by USER_A's
    # request -- no ownership-check bypass.
    assert foreign_run["status"] == "DIGITIZING"
    assert "cat_id" not in foreign_run

    assert fake_supabase.tables.get("cat", []) == []
    assert fake_supabase.tables.get("ability", []) == []


# ─── Test 4: status endpoint rejects non-owners (bugfix.md 2.10) ───────────


def test_status_endpoint_rejects_non_owner():
    """
    EXPECTED BEHAVIOR (bugfix.md 2.10, design.md Property 1).

    `GET /api/digitize/status/{task_id}` now requires a verified `CurrentUser`
    and enforces task ownership. This test creates a task owned by USER_A
    with a completed result, then polls it (a) with NO `Authorization`
    header and (b) authenticated as USER_B (a non-owner). It asserts the
    FIXED behavior: both callers are rejected (401, 403 respectively) and
    never see the result, while USER_A (the owner) still gets 200. This
    inverts the original bug-condition assertion from task 1, which expected
    an anonymous caller to receive the full result with 200.
    """
    from models.schemas import CatResponse, CatStatus, Class

    task = create_task(owner_id=USER_A)
    result = CatResponse(
        id="cat-secret-1",
        user_id=USER_A,
        name=CAT_NAME,
        breed=FAKE_BREED,
        class_=Class.INTELLIGENCE,
        current_hp=120,
        max_hp=120,
        dmg=30,
        defence=12,
        spd=18,
        mana=90,
        max_mana=90,
        lore="A clever cat forged from pixels.",
        avatar_url=FAKE_AVATAR_URL,
        lives_remaining=9,
        source_image_url="https://storage.example.com/cat-images/source.jpg",
        status=CatStatus.ALIVE,
        wins=0,
        death_date=None,
        personal_note=None,
        personality=None,
        created_at="2024-01-01T00:00:00Z",
        abilities=[],
    )
    update_task(task.id, status=TaskStatus.COMPLETED, result=result)

    # No Authorization header at all -- FIX: rejected with 401.
    with TestClient(app) as client:
        anon_resp = client.get(f"/api/digitize/status/{task.id}")
    assert anon_resp.status_code == 401

    # Authenticated, but as a different user -- FIX: rejected with 403.
    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id=USER_B)
    with TestClient(app) as client:
        foreign_resp = client.get(f"/api/digitize/status/{task.id}")
    assert foreign_resp.status_code == 403

    # The actual owner still gets the result.
    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id=USER_A)
    with TestClient(app) as client:
        owner_resp = client.get(f"/api/digitize/status/{task.id}")
    assert owner_resp.status_code == 200
    assert owner_resp.json()["result"]["id"] == "cat-secret-1"
