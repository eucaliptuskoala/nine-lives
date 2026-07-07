"""
Shared in-memory Supabase doubles for all backend tests.

Provides a `FakeSupabase` that supports the chained call patterns used across
`routers/data.py`, `routers/battle.py`, `services/digitize.py`, and
`routers/digitize.py`: select/insert/update, `.eq()` filtering, `.order()`,
insert with auto-ID / `created_at`, and a storage stand-in for image uploads.
"""

import time as _time
import pytest as _pytest


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
        self._order = None

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
    """In-memory Supabase stand-in shared across all backend tests."""

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


# ─── Shared test constants ─────────────────────────────────────────────────────


FAKE_BREED = "Siamese"
FAKE_COLORS = [{"hex": "#C0A080", "ratio": 0.6}, {"hex": "#8B6F47", "ratio": 0.4}]
FAKE_AVATAR_URL = "https://storage.example.com/cat-images/avatars/fake.png"


# ─── Shared test fixtures / helpers ────────────────────────────────────────────


def make_card(cat_name: str = "Sir Pounce") -> dict:
    return {
        "name": cat_name,
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
                "name": "Claw", "dmg": 15, "type": "DMG", "effect": None,
                "cooldown": 1, "mana_cost": 10, "lore": "A quick swipe.",
                "is_special": False, "description": "Rake with claws.",
            },
            {
                "name": "Purr Shield", "dmg": 20, "type": "SHIELD", "effect": None,
                "cooldown": 2, "mana_cost": 25, "lore": "A soothing purr.",
                "is_special": False, "description": "Raise a shield.",
            },
            {
                "name": "Catnap", "dmg": 30, "type": "HEAL", "effect": "REGEN",
                "cooldown": 3, "mana_cost": 30, "lore": "A restorative snooze.",
                "is_special": False, "description": "Heal over time.",
            },
            {
                "name": "Nine Fury", "dmg": 45, "type": "TRUE_DMG",
                "effect": "STUN", "cooldown": 4, "mana_cost": 60,
                "lore": "The fury of nine lives.", "is_special": True,
                "description": "Unleash devastating fury.",
            },
        ],
    }


def make_cat_row(**over: str | None) -> dict:
    row = {
        "id": "cat-1",
        "user_id": "user-123",
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


def make_ability_rows(creature_id: str = "cat-1") -> list[dict]:
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


def make_game_run_row(**over: str | None) -> dict:
    row = {
        "id": "run-1",
        "user_id": "user-123",
        "cat_id": "cat-1",
        "status": "IN_PROGRESS",
        "state": None,
        "current_round": 0,
        "completed_at": None,
        "created_at": "2024-01-01T00:00:00Z",
    }
    row.update(over)
    return row

def await_completion(client, task_id: str, timeout_s: int = 10):
    deadline = _time.time() + timeout_s
    while _time.time() < deadline:
        resp = client.get(f"/api/digitize/status/{task_id}")
        if resp.status_code != 200:
            return resp
        body = resp.json()
        if body["status"] in ("COMPLETED", "FAILED"):
            return resp
        _time.sleep(0.1)
    _pytest.fail("Task did not reach a terminal state within the deadline")
