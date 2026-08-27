"""Seed-data scaffolding for deterministic synthetic demo data."""

from sqlalchemy.orm import Session

from app.seed.generate_synthetic import SeedSummary, seed_synthetic


def seed_synthetic_demo_data(db: Session) -> SeedSummary:
    """Seed the deterministic demo dataset atomically.

    ``seed_synthetic`` upserts rows using the dataset's stable identifiers.  A
    rollback is still necessary for any unexpected error, but retrying the same
    failed inserts would only reproduce a uniqueness violation.
    """
    try:
        return seed_synthetic(db)
    except Exception:
        db.rollback()
        raise
