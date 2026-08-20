from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from apps.api.security import decode_access_token
from packages.shared.db import get_db
from packages.shared.models import AdminUser

_bearer_scheme = HTTPBearer(auto_error=False)


def get_session(db: Session = Depends(get_db)) -> Generator[Session, None, None]:
    yield db


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_session),
) -> AdminUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        email = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    admin = db.query(AdminUser).filter(AdminUser.email == email).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found")
    return admin


def require_admin_role(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    """"PROMPT 8" §84 RBAC: any authenticated account (admin or viewer) can
    read via get_current_admin above; only role='admin' may reach a
    mutating endpoint — manual trading controls, the Kill Switch, risk
    limits, strategy lifecycle changes. A VIEWER account exists so an
    operator can hand out a read-only link without sharing the admin
    password (POST /api/auth/users, itself admin-only)."""
    if admin.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required")
    return admin
