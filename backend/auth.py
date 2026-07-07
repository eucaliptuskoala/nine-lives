"""
Authentication Dependency

Provides a reusable FastAPI dependency (`get_current_user`) that verifies the
Supabase JWT presented in the `Authorization: Bearer <token>` header and returns
the authenticated user. Battle and Data routers depend on this to enforce
authentication on protected endpoints.

Verification is delegated to supabase-py (`auth.get_user(jwt)`), which validates
the token against Supabase Auth and returns the user record. A 401 is raised when
the header is missing/malformed or the token is invalid/expired.

Related: Requirements 21.1, 21.2
"""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# HTTPBearer extracts the `Authorization: Bearer <token>` header and documents the
# scheme in OpenAPI. auto_error=False lets us return 401 (rather than 403) when the
# header is missing, matching the acceptance criteria.
_bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Missing or invalid authentication token",
    headers={"WWW-Authenticate": "Bearer"},
)


class AuthUser(BaseModel):
    """The authenticated user resolved from a verified Supabase JWT."""

    user_id: str
    email: str | None = None


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
) -> AuthUser:
    """
    Verify the Supabase JWT from the Authorization header and return the user.

    Args:
        credentials: Bearer credentials extracted from the Authorization header,
            or None if the header is missing/malformed.

    Returns:
        AuthUser containing the authenticated user's id (and email when present).

    Raises:
        HTTPException: 401 if the token is missing, malformed, invalid, or expired.
    """
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED

    token = credentials.credentials

    supabase = get_supabase_client()

    try:
        user_response = supabase.auth.get_user(token)
    except Exception:
        logger.exception("Supabase auth.get_user failed — treating as unauthorized")
        raise _UNAUTHORIZED

    user = getattr(user_response, "user", None)
    if user is None or not getattr(user, "id", None):
        raise _UNAUTHORIZED

    return AuthUser(user_id=str(user.id), email=getattr(user, "email", None))


# Convenience alias for route signatures: `user: CurrentUser`
CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
