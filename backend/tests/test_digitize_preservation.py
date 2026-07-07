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

import time

import pytest
from fastapi.testclient import TestClient

import services.digitize as digitize_service
from auth import AuthUser, get_current_user
from main import app

USER_ID = "user-owned-1"
GAME_RUN_ID = "run-owned-1"
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
    monkeypatch.setattr(digitize_service, "generate_card", lambda **kw: make_card())
    monkeypatch.setattr(digitize_service, "generate_avatar", lambda _p: FAKE_AVATAR_URL)

    import routers.digitize as digitize_router

    monkeypatch.setattr(digitize_router, "get_supabase_client", lambda: fake)
    return fake


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

            status_resp = _await_completion(client, task_id)
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


# ─── Test 2: unsupported content type (bugfix.md 3.2, design Property 4) ────


def test_unsupported_content_type_returns_400_before_pipeline_work(monkeypatch):
    """
    PRESERVATION BASELINE (bugfix.md 3.2, design.md Property 4).

    Observed on current (pre-fix) code: an unsupported content type (e.g.
    `image/gif`) returns 400 with the existing error message pattern, and
    this happens BEFORE any pipeline work -- the Supabase client is never even
    constructed. Re-run unchanged after the BUG 1 fix to confirm this 400
    branch still short-circuits ahead of the new auth/ownership checks (or at
    minimum still returns the same 400 message once auth passes).
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
    assert "Unsupported file type" in resp.json()["detail"]
    assert "image/gif" in resp.json()["detail"]


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
