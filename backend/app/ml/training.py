"""Reproducible training and model-comparison pipeline."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from app.ml.features import (
    CATEGORICAL_FEATURE_COLUMNS,
    DATASET_VERSION,
    FEATURE_COLUMNS,
    NUMERIC_FEATURE_COLUMNS,
    TARGET_COLUMN,
)

RANDOM_SEED = 20260822
NUMERIC_FEATURES = NUMERIC_FEATURE_COLUMNS
CATEGORICAL_FEATURES = CATEGORICAL_FEATURE_COLUMNS
MODEL_VERSION = "chargeback-risk-v1"


@dataclass(frozen=True)
class TrainingResult:
    """Summary of a completed training run."""

    model_version: str
    selected_model: str
    validation_metrics: dict[str, dict[str, Any]]
    artifact_path: Path
    metadata_path: Path


def dataset_fingerprint(frame: pd.DataFrame) -> str:
    """Return a stable digest for the exact synthetic dataset used in a run."""
    serialized = frame[[*FEATURE_COLUMNS, TARGET_COLUMN]].to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_preprocessor() -> ColumnTransformer:
    """Create preprocessing that scales numerics and encodes categoricals."""
    try:
        encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:  # scikit-learn < 1.2 compatibility
        encoder = OneHotEncoder(handle_unknown="ignore", sparse=False)
    return ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
            ("categorical", encoder, CATEGORICAL_FEATURES),
        ]
    )


def _candidate_models() -> dict[str, Any]:
    return {
        "logistic_regression": LogisticRegression(class_weight="balanced", max_iter=1000, random_state=RANDOM_SEED),
        "random_forest": RandomForestClassifier(
            n_estimators=120,
            class_weight="balanced",
            min_samples_leaf=2,
            random_state=RANDOM_SEED,
        ),
        "xgboost": XGBClassifier(
            n_estimators=80,
            max_depth=3,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            random_state=RANDOM_SEED,
            scale_pos_weight=6.4,
        ),
    }


def _metrics(y_true: pd.Series, probabilities: np.ndarray) -> dict[str, Any]:
    predictions = (probabilities >= 0.5).astype(int)
    return {
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "accuracy": float(accuracy_score(y_true, predictions)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "confusion_matrix": confusion_matrix(y_true, predictions).tolist(),
    }


def split_dataset(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """Create stratified train/validation/test splits with untouched held-out test data."""
    x = frame[FEATURE_COLUMNS]
    y = frame[TARGET_COLUMN]
    x_train_val, x_test, y_train_val, y_test = train_test_split(
        x, y, test_size=0.2, stratify=y, random_state=RANDOM_SEED
    )
    x_train, x_val, y_train, y_val = train_test_split(
        x_train_val, y_train_val, test_size=0.25, stratify=y_train_val, random_state=RANDOM_SEED
    )
    return x_train, x_val, x_test, y_train, y_val, y_test


def train_and_persist(frame: pd.DataFrame, artifact_dir: Path) -> TrainingResult:
    """Train candidates, select by validation recall then F1/ROC-AUC, and persist the winner."""
    x_train, x_val, _x_test, y_train, y_val, _y_test = split_dataset(frame)
    validation_metrics: dict[str, dict[str, Any]] = {}
    trained: dict[str, Pipeline] = {}
    for name, estimator in _candidate_models().items():
        pipeline = Pipeline([("preprocessor", build_preprocessor()), ("classifier", estimator)])
        pipeline.fit(x_train, y_train)
        probabilities = pipeline.predict_proba(x_val)[:, 1]
        validation_metrics[name] = _metrics(y_val, probabilities)
        trained[name] = pipeline

    selected_model = max(
        validation_metrics,
        key=lambda name: (
            validation_metrics[name]["recall"],
            validation_metrics[name]["f1"],
            validation_metrics[name]["roc_auc"],
        ),
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{MODEL_VERSION}.joblib"
    metadata_path = artifact_dir / f"{MODEL_VERSION}.metadata.json"
    joblib.dump(trained[selected_model], artifact_path)
    metadata = {
        "model_version": MODEL_VERSION,
        "training_date": datetime.now(UTC).isoformat(),
        "dataset_version": DATASET_VERSION,
        "dataset_fingerprint": dataset_fingerprint(frame),
        "feature_list": FEATURE_COLUMNS,
        "model_type": selected_model,
        "selection_criterion": "Highest validation recall; ties broken by validation F1 then ROC-AUC because chargeback misses are costlier.",
        "validation_metrics": validation_metrics,
        "split_policy": "Stratified 60/20/20 train/validation/test split using the recorded random seed.",
        "held_out_test_policy": "Test split is created stratified and not used for model selection; Phase 4 evaluates the persisted selected artifact separately.",
        "random_seed": RANDOM_SEED,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return TrainingResult(MODEL_VERSION, selected_model, validation_metrics, artifact_path, metadata_path)





if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.init_db import init_db
    from app.ml.features import build_training_frame

    engine = create_engine("sqlite:///./chargeback_risk.db", connect_args={"check_same_thread": False})
    init_db(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    print("Generating training dataset...")
    df = build_training_frame(db)
    print(f"Dataset ready: {len(df)} rows")

    artifact_dir = Path(__file__).resolve().parents[2] / "models"
    print(f"Training models, saving to {artifact_dir} ...")
    result = train_and_persist(df, artifact_dir)

    print(f"\nTraining complete!")
    print(f"  Selected model : {result.selected_model}")
    print(f"  Artifact       : {result.artifact_path}")
    print(f"  Metadata       : {result.metadata_path}")
