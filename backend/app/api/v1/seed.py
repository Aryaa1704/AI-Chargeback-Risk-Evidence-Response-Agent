"""Development-only synthetic database seeding endpoint."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.seed.scaffold import seed_synthetic_demo_data

router = APIRouter(tags=["seed"])


@router.post("/seed", status_code=status.HTTP_200_OK)
def seed(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if settings.app_env != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seeding is only available in development",
        )
    counts = seed_synthetic_demo_data(db)
    return {
        "status": "seeded",
        "counts": {
            "customers": counts["customers"],
            "transactions": counts["transactions"],
            "disputes": counts["disputes"],
            "devices": counts["devices"],
        },
    }
