"""CLI entry point for Phase 3 chargeback-risk model training."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.init_db import init_db
from app.ml.features import FEATURE_COLUMNS, build_training_frame
from app.ml.evaluation import evaluate_held_out_model
from app.ml.training import train_and_persist
from app.seed.generate_synthetic import seed_synthetic


def main() -> None:
    """Train from deterministic synthetic demo data and persist artifacts."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as db:
        seed_synthetic(db)
        frame = build_training_frame(db)
    result = train_and_persist(frame, Path("artifacts/models"))
    evaluation = evaluate_held_out_model(frame, result.artifact_path, result.metadata_path)
    print(f"feature_count={len(FEATURE_COLUMNS)}")
    print(f"models_trained={','.join(result.validation_metrics)}")
    print(f"selected_model={result.selected_model}")
    print(f"artifact_path={result.artifact_path}")
    print(f"metadata_path={result.metadata_path}")
    print(f"evaluation_path={evaluation.evaluation_path}")
    print(f"evaluation_report_path={evaluation.report_path}")
    print(f"registry_path={evaluation.registry_path}")
    for name, metrics in result.validation_metrics.items():
        print(f"{name}: {metrics}")


if __name__ == "__main__":
    main()
