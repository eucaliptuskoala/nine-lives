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

from ._fakes import FAKE_BREED, FAKE_COLORS, FAKE_AVATAR_URL, make_card, make_cat_row, make_ability_rows, make_game_run_row, await_completion, FakeSupabase

USER_A = "user-a-cross"
USER_B = "user-b-cross"


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




def _patch_pipeline(monkeypatch, fake):
    monkeypatch.setattr(digitize_service, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(digitize_service, "classify_breed", lambda _b: FAKE_BREED)
    monkeypatch.setattr(digitize_service, "extract_colors", lambda _b: FAKE_COLORS)
    monkeypatch.setattr(digitize_service, "generate_card", lambda **kw: make_card())
    monkeypatch.setattr(digitize_service, "generate_avatar", lambda _p: FAKE_AVATAR_URL)





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
    status_resp = await_completion(client, task_id)
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
