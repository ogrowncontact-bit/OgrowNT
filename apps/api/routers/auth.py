from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import AdminOut, LoginRequest, TokenResponse
from apps.api.security import create_access_token, verify_password
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
