"""
Integration tests for the digitization pipeline (`services/digitize.py` and the
thin `POST /api/digitize` router), with EVERYTHING external fully mocked.

No network calls and no real ML models are used:
    * `classify_breed`   -> monkeypatched to a fixed breed
    * `extract_colors`   -> monkeypatched to a fixed palette
    * `generate_card`    -> monkeypatched to a valid card dict
    * `generate_avatar`  -> monkeypatched to a fake URL
    * `get_supabase_client` -> an in-memory FakeSupabase (records inserts/updates
      + storage uploads), mirroring the fake client in test_data_router.py

These tests assert the full flow — classify → extract → card → avatar → persist —
returns a `CatResponse` whose fields map correctly, that exactly 4 abilities are
inserted, and that the `game_run` is updated with the new cat id + IN_PROGRESS.

`POST /api/digitize` is an OPEN mock endpoint (no auth), so no auth override is
needed.

Covers Requirements 1.9, 2, 3, 4, 5, 6.
"""

import pytest
from fastapi.testclient import TestClient

import services.digitize as digitize_service
from services.digitize import digitize
from main import app

USER_ID = "user-123"
GAME_RUN_ID = "run-1"
CAT_NAME = "Sir Pounce"


# ─── Fake Supabase client (in-memory, with storage) ───────────────────────────


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeStorageBucket:
    """Records uploads and returns a deterministic public URL."""

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
    """Records chained insert/update/eq calls and executes against memory."""

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
            self._client.inserts.append(
                {"table": self._table, "payload": payload}
            )
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
    """Minimal in-memory Supabase stand-in with table + storage support."""

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


# ─── Fixtures / stubs ─────────────────────────────────────────────────────────


FAKE_BREED = "Siamese"
FAKE_COLORS = [
    {"hex": "#C0A080", "ratio": 0.6},
    {"hex": "#8B6F47", "ratio": 0.4},
]
FAKE_AVATAR_URL = "https://storage.example.com/cat-images/avatars/fake.png"


def make_card():
    """A valid card dict as `generate_card` would return."""
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
    """Install a FakeSupabase and stub all ML services on the orchestrator."""
    fake = FakeSupabase(
        tables={"game_run": [{"id": GAME_RUN_ID, "user_id": USER_ID, "status": "DIGITIZING"}]}
    )
    monkeypatch.setattr(digitize_service, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(digitize_service, "classify_breed", lambda _b: FAKE_BREED)
    monkeypatch.setattr(digitize_service, "extract_colors", lambda _b: FAKE_COLORS)
    monkeypatch.setattr(digitize_service, "generate_card", lambda **kw: make_card())
    monkeypatch.setattr(digitize_service, "generate_avatar", lambda _p: FAKE_AVATAR_URL)
    return fake


# ─── Orchestrator-level integration ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_digitize_orchestrator_full_flow(fake_supabase):
    """The orchestrator runs classify→extract→card→avatar→persist and maps
    every field onto the returned CatResponse."""
    cat = await digitize(
        image_bytes=b"\xff\xd8\xff-fake-jpeg-bytes",
        content_type="image/jpeg",
        cat_name=CAT_NAME,
        game_run_id=GAME_RUN_ID,
        user_id=USER_ID,
        personality="curious and aloof",
    )

    # ── Field mapping ────────────────────────────────────────────────────────
    assert cat.name == CAT_NAME
    assert cat.breed == FAKE_BREED  # from the (mocked) classifier
    assert cat.class_.value == "INTELLIGENCE"
    assert cat.max_hp == 120
    assert cat.current_hp == 120  # current_hp seeded from max_hp
    assert cat.dmg == 30
    assert cat.defence == 12  # DB `def` -> `defence`
    assert cat.spd == 18
    assert cat.mana == 90
    assert cat.max_mana == 90
    assert cat.lore == "A clever cat forged from pixels."
    assert cat.avatar_url == FAKE_AVATAR_URL  # from generate_avatar
    assert cat.lives_remaining == 9
    assert cat.status.value == "ALIVE"
    assert cat.wins == 0
    assert cat.personality == "curious and aloof"  # persisted
    assert cat.user_id == USER_ID

    # source image url comes from the storage upload public URL
    assert cat.source_image_url.startswith("https://storage.example.com/cat-images/")

    # ── Exactly 4 abilities, mapped from the card ────────────────────────────
    assert len(cat.abilities) == 4
    assert {a.name for a in cat.abilities} == {
        "Claw",
        "Purr Shield",
        "Catnap",
        "Nine Fury",
    }
    specials = [a for a in cat.abilities if a.is_special]
    assert len(specials) == 1 and specials[0].name == "Nine Fury"
    assert all(a.creature_id == cat.id for a in cat.abilities)

    # ── Storage upload happened once, JPEG under the user's path ─────────────
    assert len(fake_supabase.uploads) == 1
    upload = fake_supabase.uploads[0]
    assert upload["bucket"] == "cat-images"
    assert upload["path"].startswith(f"{USER_ID}/source-")
    assert upload["path"].endswith(".jpg")

    # ── Persistence: one cat insert + 4 ability rows ─────────────────────────
    cat_inserts = [i for i in fake_supabase.inserts if i["table"] == "cat"]
    assert len(cat_inserts) == 1
    assert cat_inserts[0]["payload"]["personality"] == "curious and aloof"

    ability_rows = fake_supabase.tables.get("ability", [])
    assert len(ability_rows) == 4
    assert all(r["creature_id"] == cat.id for r in ability_rows)

    # ── game_run updated with the new cat id + IN_PROGRESS ───────────────────
    run_updates = [u for u in fake_supabase.updates if u["table"] == "game_run"]
    assert len(run_updates) == 1
    assert run_updates[0]["payload"] == {"cat_id": cat.id, "status": "IN_PROGRESS"}
    assert run_updates[0]["filters"] == {"id": GAME_RUN_ID}

    run_row = fake_supabase.tables["game_run"][0]
    assert run_row["cat_id"] == cat.id
    assert run_row["status"] == "IN_PROGRESS"


# ─── Endpoint-level integration (TestClient) ──────────────────────────────────


def test_digitize_endpoint_full_flow(monkeypatch):
    """POST /api/digitize (open mock endpoint) returns a mapped CatResponse."""
    fake = FakeSupabase(
        tables={"game_run": [{"id": GAME_RUN_ID, "user_id": USER_ID, "status": "DIGITIZING"}]}
    )
    monkeypatch.setattr(digitize_service, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(digitize_service, "classify_breed", lambda _b: FAKE_BREED)
    monkeypatch.setattr(digitize_service, "extract_colors", lambda _b: FAKE_COLORS)
    monkeypatch.setattr(digitize_service, "generate_card", lambda **kw: make_card())
    monkeypatch.setattr(digitize_service, "generate_avatar", lambda _p: FAKE_AVATAR_URL)

    with TestClient(app) as client:
        resp = client.post(
            "/api/digitize",
            data={
                "game_run_id": GAME_RUN_ID,
                "user_id": USER_ID,
                "cat_name": CAT_NAME,
                "personality": "curious and aloof",
            },
            files={"file": ("kitty.jpg", b"\xff\xd8\xff-fake-jpeg", "image/jpeg")},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["breed"] == FAKE_BREED
    assert body["avatar_url"] == FAKE_AVATAR_URL
    assert body["personality"] == "curious and aloof"
    assert body["status"] == "ALIVE"
    assert body["lives_remaining"] == 9
    assert len(body["abilities"]) == 4

    # Persisted the cat + linked the run.
    assert body["source_image_url"].startswith("https://storage.example.com/cat-images/")
    run_row = fake.tables["game_run"][0]
    assert run_row["status"] == "IN_PROGRESS"
    assert run_row["cat_id"] == body["id"]


def test_digitize_endpoint_rejects_unsupported_type(monkeypatch):
    """A disallowed content type is rejected with 400 before any pipeline call."""

    def _boom():  # pragma: no cover - must not be called
        raise AssertionError("pipeline should not run for invalid file type")

    monkeypatch.setattr(digitize_service, "get_supabase_client", _boom)

    with TestClient(app) as client:
        resp = client.post(
            "/api/digitize",
            data={
                "game_run_id": GAME_RUN_ID,
                "user_id": USER_ID,
                "cat_name": CAT_NAME,
            },
            files={"file": ("kitty.gif", b"GIF89a", "image/gif")},
        )

    assert resp.status_code == 400
