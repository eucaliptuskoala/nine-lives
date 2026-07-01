"""
Unit tests for the Battle Router (`routers/battle.py`).

These tests exercise the two battle endpoints against the real FastAPI app via
Starlette's TestClient, with Supabase fully mocked (an in-memory fake client) and
the auth dependency overridden for the authenticated cases. No network calls are
made and the pure battle engine runs for real, so these tests verify the router's
orchestration, ownership/auth enforcement, persistence, and error handling.

Covers the acceptance criteria for Requirements 7, 9, 10, 11, 20.5 and 21:
    * POST /api/battle/start builds a correct initial Game_State (Req 7)
    * POST /api/battle/start is idempotent (Req 7.10)
    * POST /api/battle/action "attack" damages the enemy + persists (Req 9, 20)
    * 401 when the Authorization header is missing/invalid (Req 21.1/21.2)
    * 403 when the game_run belongs to another user (Req 21.3/21.4)
    * 409 when the game_run is already COMPLETED (Req 20.5)
    * ability with insufficient mana -> 400 without persisting (Req 11.9)
    * action outside PLAYER_TURN -> 400 (Req 10/11)
"""

import pytest
from fastapi.testclient import TestClient

import routers.battle as battle_router
from auth import AuthUser, get_current_user
from main import app
from models.schemas import (
    AbilityType,
    Enemy,
    EnemyAbility,
    GameState,
    Phase,
)

USER_ID = "user-123"
RUN_ID = "run-1"
CAT_ID = "cat-1"


# ─── Fake Supabase client ─────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Records the chained select/update/eq calls and executes against memory."""

    def __init__(self, client, table_name):
        self._client = client
        self._table = table_name
        self._op = None
        self._payload = None
        self._filters = {}

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
    """Minimal in-memory Supabase stand-in supporting the router's call chains."""

    def __init__(self, tables):
        self.tables = tables
        self.updates = []  # captured update() calls for persistence assertions

    def table(self, name):
        return _FakeQuery(self, name)


# ─── Row / state builders ─────────────────────────────────────────────────────


def make_cat_row(**over):
    row = {
        "id": CAT_ID,
        "user_id": USER_ID,
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
        "created_at": "2024-01-01T00:00:00Z",
    }
    row.update(over)
    return row


def make_ability_rows():
    return [
        {
            "id": "claw",
            "creature_id": CAT_ID,
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
            "id": "ultimate",
            "creature_id": CAT_ID,
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


def make_game_run_row(*, state=None, status="IN_PROGRESS", user_id=USER_ID):
    return {
        "id": RUN_ID,
        "user_id": user_id,
        "cat_id": CAT_ID,
        "status": status,
        "state": state,
        "current_round": 1 if state else 0,
        "completed_at": None,
        "created_at": "2024-01-01T00:00:00Z",
    }


def build_state_dict(*, player_mana=90, phase="PLAYER_TURN", enemy_hp=200):
    """Build a valid persisted Game_State dict with a DMG-only enemy.

    The enemy has only DMG abilities so its turn can never heal it back — this
    keeps the "enemy HP decreases" assertion deterministic.
    """
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
        player_mana=player_mana,
        player_max_mana=90,
        player_is_defending=False,
        player_shield=0,
        lives_remaining=9,
        player_ability_cooldowns={"claw": 0, "ultimate": 3},
        phase=Phase(phase),
        current_round=1,
        enemy=enemy,
    )
    return state.model_dump(mode="json")


# ─── Fixtures ─────────────────────────────────────────────────────────────────


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
    monkeypatch.setattr(battle_router, "get_supabase_client", lambda: fake)
    return fake


# ─── POST /api/battle/start ───────────────────────────────────────────────────


def test_start_builds_correct_initial_state(client, monkeypatch):
    """Fresh start -> HP=max, mana=max, round 1, PLAYER_TURN, special CD pre-set."""
    override_auth()
    tables = {
        "game_run": [make_game_run_row(state=None, status="DIGITIZING")],
        "cat": [make_cat_row()],
        "ability": make_ability_rows(),
    }
    fake = install_fake_supabase(monkeypatch, tables)

    resp = client.post("/api/battle/start", json={"run_id": RUN_ID})
    assert resp.status_code == 200

    gs = resp.json()["game_state"]
    assert gs["player_hp"] == 120  # cat max_hp
    assert gs["player_max_hp"] == 120
    assert gs["player_mana"] == 90  # cat max_mana
    assert gs["player_max_mana"] == 90
    assert gs["current_round"] == 1
    assert gs["phase"] == "PLAYER_TURN"

    # Special ability cooldown pre-set to its max; regular starts at 0 (Req 8.9).
    assert gs["player_ability_cooldowns"]["ultimate"] == 3
    assert gs["player_ability_cooldowns"]["claw"] == 0

    # An enemy is present with its special on cooldown, regulars at 0.
    enemy = gs["enemy"]
    assert enemy is not None
    specials = [a for a in enemy["abilities"] if a["is_special"]]
    assert len(specials) == 1
    special = specials[0]
    assert enemy["ability_cooldowns"][special["id"]] == special["cooldown"]
    for a in enemy["abilities"]:
        if not a["is_special"]:
            assert enemy["ability_cooldowns"][a["id"]] == 0

    # State was persisted and the run marked IN_PROGRESS.
    run_updates = [u for u in fake.updates if u["table"] == "game_run"]
    assert len(run_updates) == 1
    assert run_updates[0]["payload"]["status"] == "IN_PROGRESS"
    assert "events" not in run_updates[0]["payload"]["state"]

    # The response includes the player Cat (Req 7.11) with id/name/abilities.
    cat = resp.json()["cat"]
    assert cat["id"] == CAT_ID
    assert cat["name"] == "Sir Pounce"
    assert cat["class_"] == "STRENGTH"
    assert cat["source_image_url"] == "https://example.com/cat-source.png"
    assert {a["id"] for a in cat["abilities"]} == {"claw", "ultimate"}

    # The Cat is NOT persisted into game_run.state (Req 7.12).
    assert "cat" not in run_updates[0]["payload"]["state"]


def test_start_is_idempotent(client, monkeypatch):
    """When state already exists it is returned as-is, without regeneration."""
    override_auth()
    existing = build_state_dict(enemy_hp=137)
    tables = {
        "game_run": [make_game_run_row(state=existing, status="IN_PROGRESS")],
        "cat": [make_cat_row()],
        "ability": make_ability_rows(),
    }
    fake = install_fake_supabase(monkeypatch, tables)

    resp = client.post("/api/battle/start", json={"run_id": RUN_ID})
    assert resp.status_code == 200

    gs = resp.json()["game_state"]
    # Returned verbatim — same enemy hp as the persisted state.
    assert gs["enemy"]["hp"] == 137
    # No regeneration => no persistence write occurred.
    assert fake.updates == []

    # Even on the idempotent path the player Cat is loaded and returned (Req 7.11).
    cat = resp.json()["cat"]
    assert cat["id"] == CAT_ID
    assert cat["name"] == "Sir Pounce"
    assert {a["id"] for a in cat["abilities"]} == {"claw", "ultimate"}


# ─── POST /api/battle/action ──────────────────────────────────────────────────


def test_action_attack_damages_enemy_and_persists(client, monkeypatch):
    """attack -> enemy HP decreases, state persisted, events non-empty."""
    override_auth()
    existing = build_state_dict(enemy_hp=200)
    tables = {
        "game_run": [make_game_run_row(state=existing, status="IN_PROGRESS")],
        "cat": [make_cat_row()],
        "ability": make_ability_rows(),
    }
    fake = install_fake_supabase(monkeypatch, tables)

    resp = client.post(
        "/api/battle/action", json={"run_id": RUN_ID, "action": "attack"}
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["game_state"]["enemy"]["hp"] < 200
    assert len(body["events"]) > 0

    # The response includes the player Cat (Req 9.8).
    cat = body["cat"]
    assert cat["id"] == CAT_ID
    assert cat["name"] == "Sir Pounce"
    assert {a["id"] for a in cat["abilities"]} == {"claw", "ultimate"}

    # State persisted via a game_run update (transient events excluded).
    run_updates = [u for u in fake.updates if u["table"] == "game_run"]
    assert len(run_updates) == 1
    assert "events" not in run_updates[0]["payload"]["state"]
    # The Cat is NOT persisted into game_run.state (Req 9.9).
    assert "cat" not in run_updates[0]["payload"]["state"]


def test_action_defeating_enemy_increments_returned_cat_wins(client, monkeypatch):
    """Defeating the enemy -> returned cat.wins reflects the increment (Req 19.1)."""
    override_auth()
    # Enemy at 1 HP so a basic attack finishes it and advances the round.
    existing = build_state_dict(enemy_hp=1)
    tables = {
        "game_run": [make_game_run_row(state=existing, status="IN_PROGRESS")],
        "cat": [make_cat_row(wins=3)],
        "ability": make_ability_rows(),
    }
    fake = install_fake_supabase(monkeypatch, tables)

    resp = client.post(
        "/api/battle/action", json={"run_id": RUN_ID, "action": "attack"}
    )
    assert resp.status_code == 200

    body = resp.json()
    # Enemy defeated -> wins incremented from 3 to 4 in the returned cat.
    assert body["cat"]["wins"] == 4

    # The wins increment was persisted to the cat table, not into game_run.state.
    cat_updates = [u for u in fake.updates if u["table"] == "cat"]
    assert len(cat_updates) == 1
    assert cat_updates[0]["payload"]["wins"] == 4
    run_updates = [u for u in fake.updates if u["table"] == "game_run"]
    assert "cat" not in run_updates[0]["payload"]["state"]


def test_missing_auth_returns_401(client, monkeypatch):
    """No Authorization header (auth NOT overridden) -> 401."""
    # Do not override auth; the real dependency should reject the missing header.
    install_fake_supabase(monkeypatch, {"game_run": [make_game_run_row()]})

    resp = client.post("/api/battle/action", json={"run_id": RUN_ID, "action": "attack"})
    assert resp.status_code == 401


def test_action_wrong_owner_returns_403(client, monkeypatch):
    """game_run owned by another user -> 403."""
    override_auth(user_id=USER_ID)
    existing = build_state_dict()
    tables = {
        "game_run": [make_game_run_row(state=existing, user_id="someone-else")],
        "cat": [make_cat_row()],
        "ability": make_ability_rows(),
    }
    fake = install_fake_supabase(monkeypatch, tables)

    resp = client.post(
        "/api/battle/action", json={"run_id": RUN_ID, "action": "attack"}
    )
    assert resp.status_code == 403
    assert fake.updates == []


def test_action_on_completed_run_returns_409(client, monkeypatch):
    """Acting on a COMPLETED run -> 409 (Req 20.5)."""
    override_auth()
    existing = build_state_dict()
    tables = {
        "game_run": [make_game_run_row(state=existing, status="COMPLETED")],
        "cat": [make_cat_row()],
        "ability": make_ability_rows(),
    }
    fake = install_fake_supabase(monkeypatch, tables)

    resp = client.post(
        "/api/battle/action", json={"run_id": RUN_ID, "action": "attack"}
    )
    assert resp.status_code == 409
    assert fake.updates == []


def test_ability_insufficient_mana_returns_400_without_persisting(client, monkeypatch):
    """Using an unaffordable ability -> 400 and no state persistence (Req 11.9)."""
    override_auth()
    # player_mana=5; after regen (+floor(90*0.1)=9) => 14 < ultimate cost 50.
    existing = build_state_dict(player_mana=5)
    # Ensure the special is off cooldown so mana is the sole blocker.
    existing["player_ability_cooldowns"]["ultimate"] = 0
    tables = {
        "game_run": [make_game_run_row(state=existing, status="IN_PROGRESS")],
        "cat": [make_cat_row()],
        "ability": make_ability_rows(),
    }
    fake = install_fake_supabase(monkeypatch, tables)

    resp = client.post(
        "/api/battle/action",
        json={"run_id": RUN_ID, "action": "ability", "ability_id": "ultimate"},
    )
    assert resp.status_code == 400
    # No mutation/persistence occurred.
    assert fake.updates == []


def test_action_wrong_phase_returns_400(client, monkeypatch):
    """Acting while phase is not PLAYER_TURN -> 400."""
    override_auth()
    existing = build_state_dict(phase="ENEMY_TURN")
    tables = {
        "game_run": [make_game_run_row(state=existing, status="IN_PROGRESS")],
        "cat": [make_cat_row()],
        "ability": make_ability_rows(),
    }
    fake = install_fake_supabase(monkeypatch, tables)

    resp = client.post(
        "/api/battle/action", json={"run_id": RUN_ID, "action": "attack"}
    )
    assert resp.status_code == 400
    assert fake.updates == []
