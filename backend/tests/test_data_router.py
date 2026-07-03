"""
Unit tests for the Data Router (`routers/data.py`).

These tests exercise the three data endpoints against the real FastAPI app via
Starlette's TestClient, with Supabase fully mocked (an in-memory fake client) and
the auth dependency overridden for the authenticated cases. No network calls are
made, so these tests verify the router's orchestration, auth/ownership
enforcement, validation, ordering, and response mapping.

Covers the acceptance criteria for Requirements 1.3, 22.1, 23.2, 23.3, 23.4, 24.1:
    * All three endpoints return 401 when the Authorization header is missing (Req 24.1)
    * PATCH /api/cats/{cat_id}/note -> 403 when the cat belongs to another user (Req 23.3)
    * PATCH /api/cats/{cat_id}/note -> 400 when the note exceeds 500 chars (Req 23.4)
    * GET /api/cats/memorial returns only the user's MEMORIAL cats + abilities (Req 22.1)
    * POST /api/game-runs inserts a DIGITIZING game_run for the user (Req 1.3)
    * PATCH happy path returns 200 with the updated personal_note (Req 23.2)
"""

import pytest
from fastapi.testclient import TestClient

import routers.data as data_router
from auth import AuthUser, get_current_user
from main import app

USER_ID = "user-123"
OTHER_USER_ID = "someone-else"
CAT_ID = "cat-1"


# ─── Fake Supabase client ─────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Records the chained select/insert/update/eq/order calls and executes."""

    def __init__(self, client, table_name):
        self._client = client
        self._table = table_name
        self._op = None
        self._payload = None
        self._filters = {}
        self._order = None  # (column, desc)

    def select(self, *_args):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def order(self, column, desc=False):
        self._order = (column, desc)
        return self

    def execute(self):
        if self._op == "insert":
            row = dict(self._payload)
            row.setdefault("id", f"{self._table}-{self._client.next_id()}")
            self._client.tables.setdefault(self._table, []).append(row)
            self._client.inserts.append(
                {"table": self._table, "payload": dict(self._payload)}
            )
            return _FakeResult([row])

        rows = self._client.tables.get(self._table, [])

        def _matches(row):
            return all(str(row.get(k)) == str(v) for k, v in self._filters.items())

        matched = [r for r in rows if _matches(r)]

        if self._order is not None:
            column, desc = self._order
            matched = sorted(
                matched, key=lambda r: r.get(column) or "", reverse=desc
            )

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
    """Minimal in-memory Supabase stand-in supporting the router's call chains."""

    def __init__(self, tables):
        self.tables = tables
        self.updates = []  # captured update() calls
        self.inserts = []  # captured insert() calls
        self._id_counter = 0

    def next_id(self):
        self._id_counter += 1
        return self._id_counter

    def table(self, name):
        return _FakeQuery(self, name)


# ─── Row builders ─────────────────────────────────────────────────────────────


def make_cat_row(**over):
    """A realistic `cat` table row (DB columns: `def`, `class`)."""
    row = {
        "id": CAT_ID,
        "user_id": USER_ID,
        "name": "Sir Pounce",
        "breed": "Tabby",
        "class": "STRENGTH",
        "current_hp": 0,
        "max_hp": 120,
        "dmg": 30,
        "def": 10,
        "spd": 12,
        "mana": 90,
        "max_mana": 90,
        "lore": "A brave and fluffy warrior.",
        "avatar_url": "https://example.com/cat.png",
        "lives_remaining": 0,
        "source_image_url": "https://example.com/source.jpg",
        "status": "MEMORIAL",
        "wins": 3,
        "death_date": "2024-03-01T00:00:00Z",
        "personal_note": None,
        "created_at": "2024-01-01T00:00:00Z",
    }
    row.update(over)
    return row


def make_game_run_row(**over):
    """A realistic `game_run` table row."""
    row = {
        "id": "run-1",
        "user_id": USER_ID,
        "cat_id": CAT_ID,
        "status": "IN_PROGRESS",
        "current_round": 2,
        "state": None,
        "created_at": "2024-02-01T00:00:00Z",
        "completed_at": None,
    }
    row.update(over)
    return row


def make_ability_rows(creature_id=CAT_ID):
    return [
        {
            "id": f"{creature_id}-claw",
            "creature_id": creature_id,
            "name": "Claw",
            "dmg": 15,
            "type": "DMG",
            "effect": None,
            "cooldown": 2,
            "mana_cost": 20,
            "lore": "A sharp strike.",
            "is_special": False,
            "description": "Rake the enemy with claws.",
        },
        {
            "id": f"{creature_id}-fury",
            "creature_id": creature_id,
            "name": "Nine Fury",
            "dmg": 40,
            "type": "DMG",
            "effect": "STUN",
            "cooldown": 3,
            "mana_cost": 50,
            "lore": "The fury of nine lives.",
            "is_special": True,
            "description": "Unleash devastating fury.",
        },
    ]


# ─── Fixtures / helpers ───────────────────────────────────────────────────────


@pytest.fixture
def client():
    """TestClient with auth dependency overrides cleared on teardown."""
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def override_auth(user_id=USER_ID):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id=user_id)


def install_fake_supabase(monkeypatch, tables):
    fake = FakeSupabase(tables)
    monkeypatch.setattr(data_router, "get_supabase_client", lambda: fake)
    return fake


# ─── 401 (missing/invalid auth) — Req 24.1 ────────────────────────────────────


def test_create_game_run_missing_auth_returns_401(client, monkeypatch):
    """POST /api/game-runs with no Authorization header -> 401."""
    install_fake_supabase(monkeypatch, {"game_run": []})
    resp = client.post("/api/game-runs")
    assert resp.status_code == 401


def test_memorial_missing_auth_returns_401(client, monkeypatch):
    """GET /api/cats/memorial with no Authorization header -> 401."""
    install_fake_supabase(monkeypatch, {"cat": []})
    resp = client.get("/api/cats/memorial")
    assert resp.status_code == 401


def test_active_game_run_missing_auth_returns_401(client, monkeypatch):
    """GET /api/game-runs/active with no Authorization header -> 401."""
    install_fake_supabase(monkeypatch, {"game_run": [], "cat": []})
    resp = client.get("/api/game-runs/active")
    assert resp.status_code == 401


def test_update_note_missing_auth_returns_401(client, monkeypatch):
    """PATCH /api/cats/{id}/note with no Authorization header -> 401."""
    install_fake_supabase(monkeypatch, {"cat": [make_cat_row()]})
    resp = client.patch(f"/api/cats/{CAT_ID}/note", json={"note": "hello"})
    assert resp.status_code == 401


# ─── PATCH /api/cats/{cat_id}/note — ownership (Req 23.3) ─────────────────────


def test_update_note_wrong_owner_returns_403(client, monkeypatch):
    """Cat owned by another user -> 403, and no update is persisted."""
    override_auth(user_id=USER_ID)
    fake = install_fake_supabase(
        monkeypatch, {"cat": [make_cat_row(user_id=OTHER_USER_ID)]}
    )

    resp = client.patch(f"/api/cats/{CAT_ID}/note", json={"note": "mine now"})
    assert resp.status_code == 403
    assert fake.updates == []


def test_update_note_missing_cat_returns_404(client, monkeypatch):
    """Unknown cat id -> 404."""
    override_auth()
    fake = install_fake_supabase(monkeypatch, {"cat": []})

    resp = client.patch("/api/cats/does-not-exist/note", json={"note": "hi"})
    assert resp.status_code == 404
    assert fake.updates == []


# ─── PATCH /api/cats/{cat_id}/note — length validation (Req 23.4) ─────────────


def test_update_note_too_long_returns_400(client, monkeypatch):
    """Note exceeding 500 chars -> 400, and no update is persisted."""
    override_auth()
    fake = install_fake_supabase(monkeypatch, {"cat": [make_cat_row()]})

    resp = client.patch(f"/api/cats/{CAT_ID}/note", json={"note": "x" * 501})
    assert resp.status_code == 400
    assert fake.updates == []


def test_update_note_exactly_500_is_allowed(client, monkeypatch):
    """Note of exactly 500 chars is accepted (boundary) -> 200."""
    override_auth()
    tables = {"cat": [make_cat_row()], "ability": make_ability_rows()}
    install_fake_supabase(monkeypatch, tables)

    note = "x" * 500
    resp = client.patch(f"/api/cats/{CAT_ID}/note", json={"note": note})
    assert resp.status_code == 200
    assert resp.json()["personal_note"] == note


# ─── PATCH /api/cats/{cat_id}/note — happy path (Req 23.2) ────────────────────


def test_update_note_happy_path_returns_200(client, monkeypatch):
    """Owner + valid note -> 200 with updated personal_note persisted."""
    override_auth()
    tables = {"cat": [make_cat_row()], "ability": make_ability_rows()}
    fake = install_fake_supabase(monkeypatch, tables)

    resp = client.patch(
        f"/api/cats/{CAT_ID}/note", json={"note": "Best cat ever."}
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["id"] == CAT_ID
    assert body["personal_note"] == "Best cat ever."
    # Abilities are attached in the response.
    assert {a["name"] for a in body["abilities"]} == {"Claw", "Nine Fury"}

    # The update targeted the right cat with the right payload.
    cat_updates = [u for u in fake.updates if u["table"] == "cat"]
    assert len(cat_updates) == 1
    assert cat_updates[0]["payload"] == {"personal_note": "Best cat ever."}
    assert cat_updates[0]["filters"] == {"id": CAT_ID}


# ─── GET /api/cats/memorial — Req 22.1, 24.1 ──────────────────────────────────


def test_memorial_returns_only_users_memorial_cats_with_abilities(
    client, monkeypatch
):
    """Only the authenticated user's MEMORIAL cats are returned, with abilities,
    ordered by death_date descending."""
    override_auth(user_id=USER_ID)

    mine_old = make_cat_row(
        id="cat-mine-old",
        name="Whiskers",
        death_date="2024-01-15T00:00:00Z",
    )
    mine_new = make_cat_row(
        id="cat-mine-new",
        name="Mittens",
        death_date="2024-05-20T00:00:00Z",
    )
    mine_alive = make_cat_row(id="cat-alive", name="Alive Cat", status="ALIVE")
    other_memorial = make_cat_row(
        id="cat-other", name="Not Mine", user_id=OTHER_USER_ID
    )

    tables = {
        "cat": [mine_old, mine_new, mine_alive, other_memorial],
        "ability": (
            make_ability_rows("cat-mine-old")
            + make_ability_rows("cat-mine-new")
        ),
    }
    install_fake_supabase(monkeypatch, tables)

    resp = client.get("/api/cats/memorial")
    assert resp.status_code == 200

    body = resp.json()
    ids = [c["id"] for c in body]

    # Only this user's MEMORIAL cats — alive cat and other user's cat excluded.
    assert ids == ["cat-mine-new", "cat-mine-old"]  # ordered by death_date desc
    assert all(c["user_id"] == USER_ID for c in body)
    assert all(c["status"] == "MEMORIAL" for c in body)

    # Each cat has its abilities attached.
    for c in body:
        assert {a["name"] for a in c["abilities"]} == {"Claw", "Nine Fury"}
        assert all(a["creature_id"] == c["id"] for a in c["abilities"])


def test_memorial_empty_when_user_has_no_memorial_cats(client, monkeypatch):
    """A user with only living cats gets an empty memorial list."""
    override_auth()
    tables = {"cat": [make_cat_row(status="ALIVE")], "ability": make_ability_rows()}
    install_fake_supabase(monkeypatch, tables)

    resp = client.get("/api/cats/memorial")
    assert resp.status_code == 200
    assert resp.json() == []


# ─── POST /api/game-runs — Req 1.3 ────────────────────────────────────────────


def test_create_game_run_inserts_digitizing_run_for_user(client, monkeypatch):
    """POST /api/game-runs inserts a DIGITIZING run owned by the user and
    returns its run_id."""
    override_auth(user_id=USER_ID)
    fake = install_fake_supabase(monkeypatch, {"game_run": []})

    resp = client.post("/api/game-runs")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "DIGITIZING"

    # Exactly one insert into game_run, with the expected payload.
    assert len(fake.inserts) == 1
    insert = fake.inserts[0]
    assert insert["table"] == "game_run"
    payload = insert["payload"]
    assert payload["user_id"] == USER_ID
    assert payload["status"] == "DIGITIZING"
    assert payload["cat_id"] is None

    # The response run_id matches the id of the inserted row.
    inserted_row = fake.tables["game_run"][0]
    assert body["run_id"] == str(inserted_row["id"])


# ─── GET /api/game-runs/active — Req 24.6, 24.7 ───────────────────────────────


def test_active_game_run_returns_run_and_alive_cat(client, monkeypatch):
    """An IN_PROGRESS run whose cat is ALIVE -> {run_id, cat} with abilities."""
    override_auth(user_id=USER_ID)
    alive_cat = make_cat_row(status="ALIVE", current_hp=80, lives_remaining=5)
    tables = {
        "game_run": [make_game_run_row(id="run-active", cat_id=CAT_ID)],
        "cat": [alive_cat],
        "ability": make_ability_rows(CAT_ID),
    }
    install_fake_supabase(monkeypatch, tables)

    resp = client.get("/api/game-runs/active")
    assert resp.status_code == 200

    body = resp.json()
    assert body["run_id"] == "run-active"
    assert body["cat"]["id"] == CAT_ID
    assert body["cat"]["status"] == "ALIVE"
    assert {a["name"] for a in body["cat"]["abilities"]} == {"Claw", "Nine Fury"}


def test_active_game_run_picks_most_recent_in_progress(client, monkeypatch):
    """When multiple IN_PROGRESS runs exist, the newest (by created_at) wins."""
    override_auth(user_id=USER_ID)
    old_cat = make_cat_row(id="cat-old", status="ALIVE")
    new_cat = make_cat_row(id="cat-new", status="ALIVE")
    tables = {
        "game_run": [
            make_game_run_row(
                id="run-old",
                cat_id="cat-old",
                created_at="2024-01-01T00:00:00Z",
            ),
            make_game_run_row(
                id="run-new",
                cat_id="cat-new",
                created_at="2024-06-01T00:00:00Z",
            ),
        ],
        "cat": [old_cat, new_cat],
        "ability": make_ability_rows("cat-old") + make_ability_rows("cat-new"),
    }
    install_fake_supabase(monkeypatch, tables)

    resp = client.get("/api/game-runs/active")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "run-new"
    assert body["cat"]["id"] == "cat-new"


def test_active_game_run_none_when_only_completed_runs(client, monkeypatch):
    """Only COMPLETED runs -> {run_id: null, cat: null}."""
    override_auth(user_id=USER_ID)
    tables = {
        "game_run": [make_game_run_row(id="run-done", status="COMPLETED")],
        "cat": [make_cat_row(status="ALIVE")],
        "ability": make_ability_rows(),
    }
    install_fake_supabase(monkeypatch, tables)

    resp = client.get("/api/game-runs/active")
    assert resp.status_code == 200
    assert resp.json() == {"run_id": None, "cat": None}


def test_active_game_run_none_when_cat_is_memorial(client, monkeypatch):
    """IN_PROGRESS run whose cat is MEMORIAL (not ALIVE) -> {run_id: null, cat: null}."""
    override_auth(user_id=USER_ID)
    tables = {
        "game_run": [make_game_run_row(id="run-active", cat_id=CAT_ID)],
        "cat": [make_cat_row(status="MEMORIAL")],
        "ability": make_ability_rows(),
    }
    install_fake_supabase(monkeypatch, tables)

    resp = client.get("/api/game-runs/active")
    assert resp.status_code == 200
    assert resp.json() == {"run_id": None, "cat": None}


def test_active_game_run_only_considers_authenticated_users_runs(
    client, monkeypatch
):
    """Another user's IN_PROGRESS run is ignored -> {run_id: null, cat: null}."""
    override_auth(user_id=USER_ID)
    tables = {
        "game_run": [
            make_game_run_row(
                id="run-other", user_id=OTHER_USER_ID, cat_id="cat-other"
            )
        ],
        "cat": [make_cat_row(id="cat-other", user_id=OTHER_USER_ID, status="ALIVE")],
        "ability": make_ability_rows("cat-other"),
    }
    install_fake_supabase(monkeypatch, tables)

    resp = client.get("/api/game-runs/active")
    assert resp.status_code == 200
    assert resp.json() == {"run_id": None, "cat": None}
