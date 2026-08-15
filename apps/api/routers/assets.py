from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import AssetCreate, AssetOut, AssetUpdate
from packages.shared.models import AdminUser, Asset

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("", response_model=list[AssetOut])
def list_assets(
    asset_class: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_session),
) -> list[Asset]:
    query = db.query(Asset)
    if asset_class:
        query = query.filter(Asset.asset_class == asset_class)
    if is_active is not None:
        query = query.filter(Asset.is_active == is_active)
    return query.order_by(Asset.symbol).all()


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_session),
    _: AdminUser = Depends(get_current_admin),
) -> Asset:
    if db.query(Asset).filter(Asset.symbol == payload.symbol).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Asset already exists")
    asset = Asset(**payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.patch("/{asset_id}", response_model=AssetOut)
def update_asset(
    asset_id: int,
    payload: AssetUpdate,
    db: Session = Depends(get_session),
    _: AdminUser = Depends(get_current_admin),
) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    asset.is_active = payload.is_active
    db.commit()
    db.refresh(asset)
    return asset
