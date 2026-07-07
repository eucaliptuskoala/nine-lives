"""
Two-account cross-user access isolation tests (BUG 3 — regression-prevention
backstop).

`bugfix.md` 1.9 documents BUG 3 as a *latent architectural* risk, not a known
active hole: because every Supabase query uses the service-role key (RLS is
bypassed), each handler's application-layer ownership filter is the *only*
access control for user-scoped records. `bugfix.md` 2.10 requires that a
signed-in user requesting another user's memorial reads, note updates, battle
start/action, or digitize (POST + status) receives a 403 (or an empty result
for list reads), "verified by two-account cross-user integration tests" —
these are exactly those tests.

`design.md` Property 3 ("Cross-User Access Rejected Everywhere") states: for
any authenticated request that targets another user's records (memorial
reads, note update, battle start/action, digitize) the fixed code SHALL
return 403 (or an empty result for list reads).

This file does not fix a bug — it locks in current + already-fixed behavior
as a regression backstop, so a future handler that forgets its ownership
filter is caught immediately by CI rather than by a real cross-user leak.
Each scenario uses two authenticated users, USER_A and USER_B, and asserts
BOTH that A cannot read/mutate B's records AND that B's own (legitimate)
access still succeeds — proving isolation without breaking normal access.

Fixture/dependency-override conventions mirror `tests/test_data_router.py`,
`tests/test_battle_router.py`, and `tests/test_digitize_security.py`: an
in-memory `FakeSupabase` double installed via `monkeypatch.setattr(<router
module>, "get_supabase_client", ...)`, and
`app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id=...)`
to simulate each authenticated caller.
"""

import time

import pytest
from fastapi.testclient import TestClient

import routers.battle as battle_router
import routers.data as data_router
import routers.digitize as digitize_router
import services.digitize as digitize_service
from auth import AuthUser, get_current_user
from main import app
from models.schemas import (
    AbilityType,
    Enemy,
    EnemyAbility,
    GameState,
    Phase,
)
from services.task_store import create_task

USER_A = "user-a-cross"
USER_B = "user-b-cross"


# ─── Combined in-memory Supabase double ──────────────────────────────────────
#
# Supports the chained call patterns used across `routers/data.py`,
# `routers/battle.py`, and `routers/digitize.py` / `services/digitize.py`:
# select/insert/update, `.eq()` filtering, `.order()`, and a storage stand-in
# for the digitize pipeline's image upload.


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeStorageBucket:
    def __init__(self, client, bucket):
        self._client = client
        self._bucket = bucket

    def upload(self, path, data, file_options=None):
        self._client.uploads.append({"bucket": self._bucket, "path": path})
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
        self._order = None

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

        if self._order is not None:
            column, desc = self._order
            matched = sorted(matched, key=lambda r: r.get(column) or "", reverse=desc)

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
    """Minimal in-memory Supabase stand-in shared across all three routers."""

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


# ─── Fixtures / helpers ───────────────────────────────────────────────────────


@pytest.fixture
def client():
    """TestClient with auth dependency overrides cleared on teardown."""
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def override_auth(user_id):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id=user_id)


def install_fake_supabase(monkeypatch, module, tables):
    fake = FakeSupabase(tables)
    monkeypatch.setattr(module, "get_supabase_client", lambda: fake)
    return fake


# ─── Row / state builders (mirrors tests/test_battle_router.py) ─────────────


def make_cat_row(**over):
    row = {
        "id": "cat-1",
        "user_id": USER_A,
        "name": "Sir Pounce",
        "breed": "Tabby",
        "class": "STRENGTH",
        "current_hp": 100,
        "max_hp": 120,
        "dmg": 30,
        "def": 10,
        "spd": 12,
        "mana": 90,
        "max_mana": 90,
        "lore": "A brave and fluffy warrior.",
        "avatar_url": "https://example.com/cat.png",
        "lives_remaining": 9,
        "wins": 3,
        "status": "ALIVE",
        "source_image_url": "https://example.com/cat-source.png",
        "death_date": None,
        "personal_note": None,
        "personality": None,
        "created_at": "2024-01-01T00:00:00Z",
    }
    row.update(over)
    return row


def make_ability_rows(creature_id="cat-1"):
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
            "id": f"{creature_id}-ultimate",
            "creature_id": creature_id,
            "name": "Nine Fury",
            "dmg": 40,
            "type": "DMG",
            "effect": None,
            "cooldown": 3,
            "mana_cost": 50,
            "lore": "The fury of nine lives.",
            "is_special": True,
            "description": "Unleash devastating fury.",
        },
    ]


def make_game_run_row(**over):
    row = {
        "id": "run-1",
        "user_id": USER_B,
        "cat_id": "cat-1",
        "status": "IN_PROGRESS",
        "state": None,
        "current_round": 0,
        "completed_at": None,
        "created_at": "2024-01-01T00:00:00Z",
    }
    row.update(over)
    return row


def build_state_dict(*, enemy_hp=200):
    """Build a valid persisted Game_State dict for `game_run.state`."""
    enemy = Enemy(
        name="Shadow",
        breed="Black Shorthair",
        hp=enemy_hp,
        max_hp=200,
        atk=12,
        defence=7,
        spd=9,
        mana=48,
        max_mana=80,
        ability_cooldowns={"e-scratch": 0, "e-special": 3},
        abilities=[
            EnemyAbility(
                id="e-scratch",
                name="Scratch",
                dmg=6,
                type=AbilityType.DMG,
                effect=None,
                mana_cost=10,
                cooldown=0,
                is_special=False,
                description="A quick scratch.",
            ),
            EnemyAbility(
                id="e-special",
                name="Shadow Pounce",
                dmg=18,
                type=AbilityType.DMG,
                effect=None,
                mana_cost=40,
                cooldown=3,
                is_special=True,
                description="Leaps from the shadows.",
            ),
        ],
        avatar_url="https://example.com/enemy.png",
    )
    state = GameState(
        player_hp=120,
        player_max_hp=120,
        player_mana=90,
        player_max_mana=90,
        player_is_defending=False,
        player_shield=0,
        lives_remaining=9,
        player_ability_cooldowns={"claw": 0, "ultimate": 3},
        phase=Phase.PLAYER_TURN,
        current_round=1,
        enemy=enemy,
    )
    return state.model_dump(mode="json")


# ═══════════════════════════════════════════════════════════════════════════
# 1. Memorial read isolation — GET /api/cats/memorial
# ═══════════════════════════════════════════════════════════════════════════


def test_memorial_read_isolation(client, monkeypatch):
    """Each user's `GET /api/cats/memorial` returns only their own MEMORIAL
    cats — the other user's cat id never appears (Req 1.9, 2.10)."""
    cat_a = make_cat_row(id="cat-a", user_id=USER_A, status="MEMORIAL")
    cat_b = make_cat_row(id="cat-b", user_id=USER_B, status="MEMORIAL")
    tables = {
        "cat": [cat_a, cat_b],
        "ability": make_ability_rows("cat-a") + make_ability_rows("cat-b"),
    }
    install_fake_supabase(monkeypatch, data_router, tables)

    # A sees only A's cat; B's cat id is absent.
    override_auth(USER_A)
    resp_a = client.get("/api/cats/memorial")
    assert resp_a.status_code == 200
    ids_a = {c["id"] for c in resp_a.json()}
    assert ids_a == {"cat-a"}
    assert "cat-b" not in ids_a

    # Legitimate access: B's own memorial read still succeeds and returns B's cat.
    override_auth(USER_B)
    resp_b = client.get("/api/cats/memorial")
    assert resp_b.status_code == 200
    ids_b = {c["id"] for c in resp_b.json()}
    assert ids_b == {"cat-b"}
    assert "cat-a" not in ids_b


# ═══════════════════════════════════════════════════════════════════════════
# 2. Note update isolation — PATCH /api/cats/{cat_id}/note
# ═══════════════════════════════════════════════════════════════════════════


def test_note_update_isolation(client, monkeypatch):
    """A cat owned by B: A's PATCH note -> 403; B's own PATCH note -> 200."""
    cat_b = make_cat_row(id="cat-1", user_id=USER_B)
    tables = {"cat": [cat_b], "ability": make_ability_rows("cat-1")}
    fake = install_fake_supabase(monkeypatch, data_router, tables)

    override_auth(USER_A)
    resp_a = client.patch("/api/cats/cat-1/note", json={"note": "not mine"})
    assert resp_a.status_code == 403
    assert fake.updates == []

    # Legitimate owner (B) can still update their own note -> 200.
    override_auth(USER_B)
    resp_b = client.patch("/api/cats/cat-1/note", json={"note": "mine"})
    assert resp_b.status_code == 200
    assert resp_b.json()["personal_note"] == "mine"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Battle start isolation — POST /api/battle/start
# ═══════════════════════════════════════════════════════════════════════════


def test_battle_start_isolation(client, monkeypatch):
    """A `game_run` owned by B: A's POST /api/battle/start -> 403; B's own
    start still succeeds -> 200."""
    run_b = make_game_run_row(
        id="run-1", user_id=USER_B, cat_id="cat-1", status="DIGITIZING", state=None
    )
    cat_b = make_cat_row(id="cat-1", user_id=USER_B)
    tables = {
        "game_run": [run_b],
        "cat": [cat_b],
        "ability": make_ability_rows("cat-1"),
    }
    fake = install_fake_supabase(monkeypatch, battle_router, tables)

    override_auth(USER_A)
    resp_a = client.post("/api/battle/start", json={"run_id": "run-1"})
    assert resp_a.status_code == 403
    assert fake.updates == []

    # Legitimate owner (B) can still start their own run -> 200.
    override_auth(USER_B)
    resp_b = client.post("/api/battle/start", json={"run_id": "run-1"})
    assert resp_b.status_code == 200
    assert resp_b.json()["cat"]["id"] == "cat-1"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Battle action isolation — POST /api/battle/action
# ═══════════════════════════════════════════════════════════════════════════


def test_battle_action_isolation(client, monkeypatch):
    """A `game_run` owned by B (already started): A's POST
    /api/battle/action -> 403; B's own action still succeeds -> 200."""
    existing_state = build_state_dict()
    run_b = make_game_run_row(
        id="run-1", user_id=USER_B, cat_id="cat-1", status="IN_PROGRESS",
        state=existing_state,
    )
    cat_b = make_cat_row(id="cat-1", user_id=USER_B)
    tables = {
        "game_run": [run_b],
        "cat": [cat_b],
        "ability": make_ability_rows("cat-1"),
    }
    fake = install_fake_supabase(monkeypatch, battle_router, tables)

    override_auth(USER_A)
    resp_a = client.post(
        "/api/battle/action", json={"run_id": "run-1", "action": "attack"}
    )
    assert resp_a.status_code == 403
    assert fake.updates == []

    # Legitimate owner (B) can still act on their own run -> 200.
    override_auth(USER_B)
    resp_b = client.post(
        "/api/battle/action", json={"run_id": "run-1", "action": "attack"}
    )
    assert resp_b.status_code == 200
    assert resp_b.json()["cat"]["id"] == "cat-1"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Digitize POST isolation — POST /api/digitize
# ═══════════════════════════════════════════════════════════════════════════

FAKE_BREED = "Siamese"
FAKE_COLORS = [{"hex": "#C0A080", "ratio": 0.6}, {"hex": "#8B6F47", "ratio": 0.4}]
FAKE_AVATAR_URL = "https://storage.example.com/cat-images/avatars/fake.png"


def make_card():
    return {
        "name": "Sir Pounce",
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


def _patch_pipeline(monkeypatch, fake):
    monkeypatch.setattr(digitize_service, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(digitize_service, "classify_breed", lambda _b: FAKE_BREED)
    monkeypatch.setattr(digitize_service, "extract_colors", lambda _b: FAKE_COLORS)
    monkeypatch.setattr(digitize_service, "generate_card", lambda **kw: make_card())
    monkeypatch.setattr(digitize_service, "generate_avatar", lambda _p: FAKE_AVATAR_URL)


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


@pytest.fixture(autouse=True)
def _isolate_rate_limiter():
    """Reset the module-level rate-limit state around every test in this
    file, so tests never leak rate-limit state into one another."""
    digitize_router._rate_limit_requests.clear()
    yield
    digitize_router._rate_limit_requests.clear()


def test_digitize_post_isolation(client, monkeypatch):
    """A `game_run` owned by B (DIGITIZING): A's POST /api/digitize with B's
    `game_run_id` -> 403 with no cat/ability records created. B's own POST
    still succeeds through to a COMPLETED `CatResponse` owned by B."""
    run_b = make_game_run_row(
        id="run-1", user_id=USER_B, cat_id=None, status="DIGITIZING", state=None
    )
    fake = install_fake_supabase(monkeypatch, digitize_router, {"game_run": [run_b]})
    _patch_pipeline(monkeypatch, fake)

    override_auth(USER_A)
    resp_a = client.post(
        "/api/digitize",
        data={"game_run_id": "run-1", "cat_name": "Sir Pounce"},
        files={"file": ("kitty.jpg", b"\xff\xd8\xff-fake-jpeg", "image/jpeg")},
    )
    assert resp_a.status_code == 403
    assert fake.tables.get("cat", []) == []
    assert fake.tables.get("ability", []) == []

    # Legitimate owner (B) can still digitize using their own game_run -> 202
    # -> COMPLETED, with the resulting cat owned by B.
    override_auth(USER_B)
    resp_b = client.post(
        "/api/digitize",
        data={"game_run_id": "run-1", "cat_name": "Sir Pounce"},
        files={"file": ("kitty.jpg", b"\xff\xd8\xff-fake-jpeg", "image/jpeg")},
    )
    assert resp_b.status_code == 202, resp_b.text
    task_id = resp_b.json()["task_id"]
    status_resp = _await_completion(client, task_id)
    assert status_resp.status_code == 200
    result = status_resp.json()["result"]
    assert result["user_id"] == USER_B


# ═══════════════════════════════════════════════════════════════════════════
# 6. Digitize status isolation — GET /api/digitize/status/{task_id}
# ═══════════════════════════════════════════════════════════════════════════


def test_digitize_status_isolation(client):
    """A task owned by B: A's GET status -> 403; B's own GET status -> 200."""
    task = create_task(owner_id=USER_B)

    override_auth(USER_A)
    resp_a = client.get(f"/api/digitize/status/{task.id}")
    assert resp_a.status_code == 403

    # Legitimate owner (B) can still poll their own task -> 200.
    override_auth(USER_B)
    resp_b = client.get(f"/api/digitize/status/{task.id}")
    assert resp_b.status_code == 200
