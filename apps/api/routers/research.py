from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.deps import get_session
from apps.api.schemas import LearnedRuleOut
from packages.shared.models import LearnedRule

router = APIRouter(prefix="/api/research", tags=["research"])


@router.get("/rules", response_model=list[LearnedRuleOut])
def list_learned_rules(status: str | None = None, limit: int = 50, db: Session = Depends(get_session)) -> list[LearnedRule]:
    query = db.query(LearnedRule)
    if status is not None:
        query = query.filter(LearnedRule.status == status)
    return query.order_by(LearnedRule.created_at.desc()).limit(limit).all()
