"""
Unit tests for the JWT verification dependency (`auth.get_current_user`).

Covers the acceptance criteria for Requirements 21.1 and 21.2:
- Missing Authorization header -> 401
- Invalid/expired token -> 401
- Valid token -> returns the authenticated user's id

Supabase is mocked so these tests exercise the dependency logic in isolation
without making network calls.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import auth


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.asyncio
async def test_missing_header_returns_401():
    """No Authorization header (credentials is None) -> 401."""
    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(credentials=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_empty_token_returns_401():
    """Authorization header with an empty token -> 401."""
    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(credentials=_credentials(""))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401(monkeypatch):
    """supabase auth raising (invalid/expired token) -> 401."""

    class _RaisingAuth:
        def get_user(self, _token):
            raise Exception("AuthApiError: invalid token")

    monkeypatch.setattr(
        auth, "get_supabase_client", lambda: SimpleNamespace(auth=_RaisingAuth())
    )

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(credentials=_credentials("bad-token"))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_token_with_no_user_returns_401(monkeypatch):
    """supabase returning a response without a user -> 401."""

    class _NoUserAuth:
        def get_user(self, _token):
            return SimpleNamespace(user=None)

    monkeypatch.setattr(
        auth, "get_supabase_client", lambda: SimpleNamespace(auth=_NoUserAuth())
    )

    with pytest.raises(HTTPException) as exc_info:
        await auth.get_current_user(credentials=_credentials("token"))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_valid_token_returns_user(monkeypatch):
    """A valid token -> returns AuthUser with the extracted user_id and email."""

    fake_user = SimpleNamespace(id="user-123", email="cat@example.com")

    class _ValidAuth:
        def get_user(self, token):
            assert token == "good-token"
            return SimpleNamespace(user=fake_user)

    monkeypatch.setattr(
        auth, "get_supabase_client", lambda: SimpleNamespace(auth=_ValidAuth())
    )

    result = await auth.get_current_user(credentials=_credentials("good-token"))
    assert result.user_id == "user-123"
    assert result.email == "cat@example.com"
