import time

import pytest
from fastapi.testclient import TestClient

import services.digitize as digitize_service
from auth import AuthUser, get_current_user
from services.digitize import digitize
from main import app

USER_ID = "user-123"
GAME_RUN_ID = "run-1"
CAT_NAME = "Sir Pounce"


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
FAKE_COLORS = [
    {"hex": "#C0A080", "ratio": 0.6},
    {"hex": "#8B6F47", "ratio": 0.4},
]
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
    fake = FakeSupabase(
        tables={"game_run": [{"id": GAME_RUN_ID, "user_id": USER_ID, "status": "DIGITIZING"}]}
    )
    monkeypatch.setattr(digitize_service, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(digitize_service, "classify_breed", lambda _b: FAKE_BREED)
    monkeypatch.setattr(digitize_service, "extract_colors", lambda _b: FAKE_COLORS)
    monkeypatch.setattr(digitize_service, "generate_card", lambda **kw: make_card())
    monkeypatch.setattr(digitize_service, "generate_avatar", lambda _p: FAKE_AVATAR_URL)
    return fake


def test_digitize_orchestrator_full_flow(fake_supabase):
    cat = digitize(
        image_bytes=b"\xff\xd8\xff-fake-jpeg-bytes",
        content_type="image/jpeg",
        cat_name=CAT_NAME,
        game_run_id=GAME_RUN_ID,
        user_id=USER_ID,
        personality="curious and aloof",
    )

    assert cat.name == CAT_NAME
    assert cat.breed == FAKE_BREED
    assert cat.class_.value == "INTELLIGENCE"
    assert cat.max_hp == 120
    assert cat.current_hp == 120
    assert cat.dmg == 30
    assert cat.defence == 12
    assert cat.spd == 18
    assert cat.mana == 90
    assert cat.max_mana == 90
    assert cat.lore == "A clever cat forged from pixels."
    assert cat.avatar_url == FAKE_AVATAR_URL
    assert cat.lives_remaining == 9
    assert cat.status.value == "ALIVE"
    assert cat.wins == 0
    assert cat.personality == "curious and aloof"
    assert cat.user_id == USER_ID

    assert cat.source_image_url.startswith("https://storage.example.com/cat-images/")

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

    assert len(fake_supabase.uploads) == 1
    upload = fake_supabase.uploads[0]
    assert upload["bucket"] == "cat-images"
    assert upload["path"].startswith(f"{USER_ID}/source-")
    assert upload["path"].endswith(".jpg")

    cat_inserts = [i for i in fake_supabase.inserts if i["table"] == "cat"]
    assert len(cat_inserts) == 1
    assert cat_inserts[0]["payload"]["personality"] == "curious and aloof"

    ability_rows = fake_supabase.tables.get("ability", [])
    assert len(ability_rows) == 4
    assert all(r["creature_id"] == cat.id for r in ability_rows)

    run_updates = [u for u in fake_supabase.updates if u["table"] == "game_run"]
    assert len(run_updates) == 1
    assert run_updates[0]["payload"] == {"cat_id": cat.id, "status": "IN_PROGRESS"}
    assert run_updates[0]["filters"] == {"id": GAME_RUN_ID}

    run_row = fake_supabase.tables["game_run"][0]
    assert run_row["cat_id"] == cat.id
    assert run_row["status"] == "IN_PROGRESS"


def test_digitize_endpoint_full_flow(monkeypatch):
    fake = FakeSupabase(
        tables={"game_run": [{"id": GAME_RUN_ID, "user_id": USER_ID, "status": "DIGITIZING"}]}
    )
    monkeypatch.setattr(digitize_service, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(digitize_service, "classify_breed", lambda _b: FAKE_BREED)
    monkeypatch.setattr(digitize_service, "extract_colors", lambda _b: FAKE_COLORS)
    monkeypatch.setattr(digitize_service, "generate_card", lambda **kw: make_card())
    monkeypatch.setattr(digitize_service, "generate_avatar", lambda _p: FAKE_AVATAR_URL)

    import routers.digitize as digitize_router

    monkeypatch.setattr(digitize_router, "get_supabase_client", lambda: fake)

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
            deadline = time.time() + 10

            result = None
            while time.time() < deadline:
                status_resp = client.get(f"/api/digitize/status/{task_id}")
                assert status_resp.status_code == 200
                status_body = status_resp.json()

                if status_body["status"] == "COMPLETED":
                    result = status_body["result"]
                    break
                elif status_body["status"] == "FAILED":
                    pytest.fail(f"Digitization task failed: {status_body.get('error')}")

                time.sleep(0.1)
    finally:
        app.dependency_overrides.clear()

    assert result is not None, "Task did not complete within the deadline"

    assert result["breed"] == FAKE_BREED
    assert result["avatar_url"] == FAKE_AVATAR_URL
    assert result["personality"] == "curious and aloof"
    assert result["status"] == "ALIVE"
    assert result["lives_remaining"] == 9
    assert len(result["abilities"]) == 4

    assert result["source_image_url"].startswith("https://storage.example.com/cat-images/")
    run_row = fake.tables["game_run"][0]
    assert run_row["status"] == "IN_PROGRESS"
    assert run_row["cat_id"] == result["id"]


def test_digitize_endpoint_rejects_unsupported_type(monkeypatch):
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
