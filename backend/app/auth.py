"""Local authentication: bcrypt password hashes + HS256 JWT bearer tokens + role guards."""
from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Callable, Optional
from uuid import uuid4

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import repository as repo
from app.config import get_settings
from app.models.schemas import (
    InviteRequest, InviteResponse, LoginRequest, SetPasswordRequest, TokenResponse, UserProfile,
)

log = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)
ROLE_RANK = {"engineer": 1, "reviewer": 2, "admin": 3}


# ----------------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    raw = password.encode("utf-8")[:72]  # bcrypt limit
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


def generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(length - 2))
    return core + "@" + secrets.choice(string.digits)


# ----------------------------------------------------------------------------- tokens
def create_token(profile: UserProfile) -> TokenResponse:
    s = get_settings()
    expires = timedelta(hours=s.jwt_expires_hours)
    now = datetime.utcnow()
    payload = {"sub": profile.id, "email": profile.email, "role": profile.role,
               "iat": int(now.timestamp()), "exp": int((now + expires).timestamp())}
    token = jwt.encode(payload, s.jwt_secret, algorithm="HS256")
    return TokenResponse(access_token=token, expires_in=int(expires.total_seconds()), profile=profile)


def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=["HS256"])


# ----------------------------------------------------------------------------- dependencies
def current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> UserProfile:
    if creds is None or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please sign in again")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = repo.get_user(str(payload.get("sub", "")))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or deactivated")
    return user


def require_role(min_role: str) -> Callable[..., UserProfile]:
    def dep(user: UserProfile = Depends(current_user)) -> UserProfile:
        if ROLE_RANK.get(user.role, 0) < ROLE_RANK[min_role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires {min_role} role")
        return user
    return dep


# ----------------------------------------------------------------------------- flows
def bootstrap_admin() -> None:
    """Create the first admin when the user table is empty."""
    if repo.count_users() > 0:
        return
    s = get_settings()
    password = s.bootstrap_admin_password
    generated = False
    if not password:
        password = generate_temp_password(14)
        generated = True
    user_id = uuid4().hex[:12]
    repo.create_user(user_id, s.bootstrap_admin_email, s.bootstrap_admin_name, "admin",
                     hash_password(password), must_set_password=True)
    if generated:
        out = s.data_dir / "first-admin-password.txt"
        out.write_text(f"{s.bootstrap_admin_email}\n{password}\n")
        log.warning("First admin created (%s). Temporary password written to %s", s.bootstrap_admin_email, out)
    else:
        log.warning("First admin created from BOOTSTRAP_ADMIN_* env (%s)", s.bootstrap_admin_email)


def login(req: LoginRequest) -> TokenResponse:
    row = repo.get_user_row_by_email(req.email)
    if row is None or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not row["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account deactivated. Contact your admin.")
    profile = repo.update_user(row["id"], last_sign_in_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z")
    return create_token(profile)  # type: ignore[arg-type]


def set_password(user: UserProfile, req: SetPasswordRequest) -> UserProfile:
    row = repo.get_user_row_by_email(user.email)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not user.must_set_password:
        if not req.current_password or not verify_password(req.current_password, row["password_hash"]):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    return repo.update_user(user.id, password_hash=hash_password(req.password), must_set_password=False)  # type: ignore[return-value]


def invite(req: InviteRequest) -> InviteResponse:
    email = req.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid email")
    if repo.get_user_row_by_email(email):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")
    temp = req.temporary_password or generate_temp_password()
    profile = repo.create_user(uuid4().hex[:12], email, req.full_name, req.role, hash_password(temp),
                               must_set_password=True)
    return InviteResponse(profile=profile, temporary_password=temp)
