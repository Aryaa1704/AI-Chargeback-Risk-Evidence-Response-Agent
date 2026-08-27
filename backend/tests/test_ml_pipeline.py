"""Tests for ML training, held-out evaluation, and risk explanations."""

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.init_db import init_db
from app.ml.features import FEATURE_COLUMNS, build_training_frame
from app.ml.evaluation import calculate_metrics, evaluate_held_out_model
from app.ml.prediction import predict_risk, probability_to_score, risk_level_for_score
from app.ml.training import build_preprocessor, split_dataset, train_and_persist
from app.seed.generate_synthetic import seed_synthetic


def _training_frame():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as db:
        seed_synthetic(db)
        return build_training_frame(db)


def test_preprocessor_transforms_mixed_features() -> None:
    frame = _training_frame()
    transformed = build_preprocessor().fit_transform(frame[FEATURE_COLUMNS])

    assert len(FEATURE_COLUMNS) == 22
    assert transformed.shape[0] == len(frame)
    assert transformed.shape[1] > len(FEATURE_COLUMNS)


def test_training_compares_three_models_and_persists_reloadable_artifact(tmp_path: Path) -> None:
    frame = _training_frame()
    result = train_and_persist(frame, tmp_path)

    assert set(result.validation_metrics) == {"logistic_regression", "random_forest", "xgboost"}
    for metrics in result.validation_metrics.values():
        assert {"precision", "recall", "f1", "accuracy", "roc_auc", "confusion_matrix"} <= set(metrics)
    assert result.artifact_path.exists()
    assert result.metadata_path.exists()

    settings = Settings(ml_model_artifact_path=str(result.artifact_path), risk_low_threshold=35, risk_high_threshold=70)
    prediction = predict_risk(frame[FEATURE_COLUMNS].iloc[0].to_dict(), settings=settings)
    assert 0.0 <= prediction.probability <= 1.0
    assert 0 <= prediction.risk_score <= 100
    assert prediction.risk_level in {"LOW", "MEDIUM", "HIGH"}
    assert prediction.model_derived_risk_factors
    assert all(factor.source_feature in FEATURE_COLUMNS for factor in prediction.model_derived_risk_factors)
    assert all(factor.attribution_method in {"model_native_feature_importance", "linear_model_coefficient"} for factor in prediction.model_derived_risk_factors)


def test_training_is_reproducible_with_fixed_seed(tmp_path: Path) -> None:
    frame = _training_frame()
    first = train_and_persist(frame, tmp_path / "first")
    second = train_and_persist(frame, tmp_path / "second")

    assert first.selected_model == second.selected_model
    assert first.validation_metrics == second.validation_metrics


def test_risk_score_thresholds() -> None:
    assert probability_to_score(0.704) == 70
    assert risk_level_for_score(34, 35, 70) == "LOW"
    assert risk_level_for_score(35, 35, 70) == "MEDIUM"
    assert risk_level_for_score(70, 35, 70) == "HIGH"


def test_calculate_metrics_uses_actual_labels_predictions_and_confusion_matrix() -> None:
    labels = np.array([0, 0, 1, 1])
    probabilities = np.array([0.1, 0.8, 0.4, 0.9])
    metrics = calculate_metrics(labels, probabilities)
    predictions = (probabilities >= 0.5).astype(int)

    assert metrics["confusion_matrix"] == [[1, 1], [1, 1]]
    assert metrics["confusion_matrix"] == confusion_matrix(labels, predictions, labels=[0, 1]).tolist()
    assert metrics["precision"] == precision_score(labels, predictions, zero_division=0)
    assert metrics["recall"] == recall_score(labels, predictions, zero_division=0)
    assert metrics["f1"] == f1_score(labels, predictions, zero_division=0)
    assert metrics["accuracy"] == accuracy_score(labels, predictions)
    assert metrics["roc_auc"] == roc_auc_score(labels, probabilities)
    assert metrics["support_counts"] == {"0": 2, "1": 2}


def test_held_out_evaluation_persists_recomputed_metrics_and_registry(tmp_path: Path) -> None:
    frame = _training_frame()
    training = train_and_persist(frame, tmp_path)
    evaluation = evaluate_held_out_model(frame, training.artifact_path, training.metadata_path)
    payload = json.loads(evaluation.evaluation_path.read_text(encoding="utf-8"))
    registry = json.loads(evaluation.registry_path.read_text(encoding="utf-8"))
    model = joblib.load(training.artifact_path)
    _x_train, _x_validation, x_test, _y_train, _y_validation, y_test = split_dataset(frame)
    expected = calculate_metrics(y_test, model.predict_proba(x_test)[:, 1])

    assert payload["metrics"] == expected
    assert evaluation.metrics == expected
    assert payload["split"]["row_count"] == len(y_test)
    assert registry["artifact_path"] == str(training.artifact_path.resolve())
    assert registry["evaluation_path"] == str(evaluation.evaluation_path.resolve())
    assert registry["feature_schema"] == FEATURE_COLUMNS
    assert evaluation.report_path.exists()
