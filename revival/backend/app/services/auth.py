# Why this exists: JWT resolution + workspace membership enforcement.
#
# Priority order for workspace_id:
#   1. In prod: only the JWT's user + membership table determine access.
#      X-Workspace-Id header is CONSULTED (for users in multiple workspaces)
#      but validated against the membership table.
#   2. In DEMO_MODE: auto-create a demo user + allow header/qp override.
#   3. REVIVAL_TEST_BYPASS=1 (test suite only): same behavior as DEMO.
#
# Webhooks never hit auth — their own signature verification is sufficient.
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import User, Workspace, WorkspaceMember
from app.utils.logger import get_logger
from app.utils.settings import get_settings

log = get_logger("auth")

DEMO_USER_EXTERNAL_ID = "demo-user"


@dataclass
class AuthContext:
    user_id: int            # internal users.id
    external_id: str        # jwt sub or DEMO sentinel
    email: Optional[str]
    workspace_id: int
    is_demo: bool = False


def _is_test_bypass() -> bool:
    return os.environ.get("REVIVAL_TEST_BYPASS") == "1"


def verify_jwt(token: str) -> Optional[dict]:
    """Validate a Supabase-issued HS256 JWT against the shared secret.
    Returns the decoded claims on success, None otherwise."""
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        return None
    try:
        import jwt as pyjwt
        # Supabase JWTs carry `aud: "authenticated"` — we accept it, and
        # also tolerate the default anon audience for edge cases.
        return pyjwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=["authenticated", "anon"],
            options={"verify_aud": False},  # we don't pin aud for flexibility
        )
    except Exception as e:
        log.info("jwt verify failed: %s", e)
        return None


def _upsert_user(db: Session, external_id: str, email: Optional[str]) -> User:
    user = db.scalars(select(User).where(User.external_id == external_id)).first()
    if user is None:
        user = User(external_id=external_id, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif email and user.email != email:
        user.email = email
        db.commit()
    return user


def _ensure_membership(db: Session, user: User, workspace_id: int, role: str = "owner") -> WorkspaceMember:
    mem = db.scalars(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    ).first()
    if mem is None:
        mem = WorkspaceMember(user_id=user.id, workspace_id=workspace_id, role=role)
        db.add(mem)
        db.commit()
        db.refresh(mem)
    return mem


def resolve_workspace(db: Session, user: User, requested_ws: Optional[int]) -> int:
    """Pick the right workspace for this user + request. Raises ValueError
    if the user has no membership in the requested workspace."""
    if requested_ws is not None:
        mem = db.scalars(
            select(WorkspaceMember).where(
                WorkspaceMember.user_id == user.id,
                WorkspaceMember.workspace_id == requested_ws,
            )
        ).first()
        if mem is None:
            raise ValueError(f"user {user.external_id} is not a member of workspace {requested_ws}")
        return requested_ws

    # No requested workspace: use the user's oldest membership.
    mem = db.scalars(
        select(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(WorkspaceMember.joined_at.asc())
    ).first()
    if mem is None:
        raise ValueError(f"user {user.external_id} has no workspace memberships")
    return mem.workspace_id


def _demo_context(db: Session, requested_ws: Optional[int]) -> AuthContext:
    """Bootstrap the DEMO user and their workspace 1 membership, plus ensure
    membership in any requested workspace (tests switch to workspace 2 via
    the `?workspace=2` param)."""
    user = _upsert_user(db, DEMO_USER_EXTERNAL_ID, "demo@revival.local")

    # Make sure workspace 1 exists + demo is a member.
    if db.get(Workspace, 1) is None:
        db.add(Workspace(id=1, name="Default workspace"))
        db.commit()
    _ensure_membership(db, user, 1)

    # If a specific workspace is requested and it exists, extend membership.
    if requested_ws is not None:
        if db.get(Workspace, requested_ws) is None:
            db.add(Workspace(id=requested_ws, name=f"Workspace {requested_ws}"))
            db.commit()
        _ensure_membership(db, user, requested_ws)

    ws = requested_ws or 1
    return AuthContext(
        user_id=user.id, external_id=user.external_id, email=user.email,
        workspace_id=ws, is_demo=True,
    )


def resolve_auth_context(
    db: Session,
    *,
    authorization_header: Optional[str],
    requested_workspace: Optional[int],
) -> Optional[AuthContext]:
    """Return an AuthContext or None (= 401 for authed paths).

    None is ONLY returned when auth is required but missing/invalid. Callers
    on public paths should skip this function entirely.
    """
    settings = get_settings()

    # Bearer token path.
    if authorization_header and authorization_header.lower().startswith("bearer "):
        token = authorization_header.split(None, 1)[1].strip()
        claims = verify_jwt(token)
        if claims is None:
            # If DEMO_MODE, tolerate a 'demo-' prefixed token for UI fake-login.
            if (settings.demo_mode or _is_test_bypass()) and token.startswith("demo-"):
                return _demo_context(db, requested_workspace)
            return None
        external_id = str(claims.get("sub") or "")
        email = claims.get("email")
        if not external_id:
            return None
        user = _upsert_user(db, external_id, email)
        # In real mode, users MUST already have a workspace membership
        # (seeded at signup time). If they don't, this is a 403.
        try:
            ws_id = resolve_workspace(db, user, requested_workspace)
        except ValueError:
            return None
        return AuthContext(
            user_id=user.id, external_id=external_id, email=email,
            workspace_id=ws_id, is_demo=False,
        )

    # No token path. DEMO or test-bypass → auto-login. Prod → None.
    if settings.demo_mode or _is_test_bypass():
        return _demo_context(db, requested_workspace)
    return None
