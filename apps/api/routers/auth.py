from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session, require_admin_role
from apps.api.schemas import AdminOut, CreateUserRequest, LoginRequest, TokenResponse
from apps.api.security import create_access_token, hash_password, verify_password
from packages.shared.models import AdminUser

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_session)) -> TokenResponse:
    admin = db.query(AdminUser).filter(AdminUser.email == payload.email).first()
    if admin is None or not verify_password(payload.password, admin.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token, expires_at = create_access_token(subject=admin.email)
    return TokenResponse(access_token=token, expires_at=expires_at)


@router.post("/logout")
def logout(_: AdminUser = Depends(get_current_admin)) -> dict:
    # Stateless JWT: nothing to invalidate server-side in Phase 1. The client
    # is responsible for discarding the token. A token blocklist can be added
    # later if early revocation becomes a requirement.
    return {"detail": "logged out"}


@router.get("/me", response_model=AdminOut)
def me(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    return admin


@router.post("/users", response_model=AdminOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest, db: Session = Depends(get_session), admin: AdminUser = Depends(require_admin_role)
) -> AdminUser:
    """"PROMPT 8" §77 RBAC — admin-only, so an operator can hand out a
    read-only VIEWER account without sharing the admin password. Defaults
    to 'viewer': creating another 'admin' is still possible (explicit
    role='admin' in the payload) but never the accidental default."""
    if payload.role not in ("admin", "viewer"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role must be 'admin' or 'viewer'")
    if db.query(AdminUser).filter(AdminUser.email == payload.email).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")

    user = AdminUser(email=payload.email, hashed_password=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
