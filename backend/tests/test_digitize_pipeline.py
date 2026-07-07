import time

import pytest
from fastapi.testclient import TestClient

import services.digitize as digitize_service
from auth import AuthUser, get_current_user
from services.digitize import digitize
from main import app

from ._fakes import FAKE_BREED, FAKE_COLORS, FAKE_AVATAR_URL, make_card, FakeSupabase

USER_ID = "user-123"
GAME_RUN_ID = "run-1"
CAT_NAME = "Sir Pounce"





@pytest.fixture
def fake_supabase(monkeypatch):
    fake = FakeSupabase(
        tables={"game_run": [{"id": GAME_RUN_ID, "user_id": USER_ID, "status": "DIGITIZING"}]}
    )
    monkeypatch.setattr(digitize_service, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(digitize_service, "classify_breed", lambda _b: FAKE_BREED)
    monkeypatch.setattr(digitize_service, "extract_colors", lambda _b: FAKE_COLORS)
    monkeypatch.setattr(digitize_service, "generate_card", lambda **kw: make_card(CAT_NAME))
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
    monkeypatch.setattr(digitize_service, "generate_card", lambda **kw: make_card(CAT_NAME))
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
