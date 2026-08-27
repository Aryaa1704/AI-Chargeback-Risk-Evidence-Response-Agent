"""Reusable chargeback-risk prediction service independent of Gemini."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.core.config import Settings, get_settings
from app.ml.evaluation import RiskFactor, explain_prediction
from app.ml.features import FEATURE_COLUMNS


@dataclass(frozen=True)
class RiskPredictionResult:
    """Validated risk prediction output for application logic."""

    probability: float
    risk_score: int
    risk_level: str
    model_version: str
    model_derived_risk_factors: tuple[RiskFactor, ...]


def probability_to_score(probability: float) -> int:
    """Convert a model probability to a bounded 0-100 risk score."""
    return max(0, min(100, round(probability * 100)))


def risk_level_for_score(score: int, low_threshold: int, high_threshold: int) -> str:
    """Map score to LOW/MEDIUM/HIGH using configurable thresholds."""
    if score < low_threshold:
        return "LOW"
    if score < high_threshold:
        return "MEDIUM"
    return "HIGH"


def load_model(artifact_path: str | Path) -> Any:
    """Reload a persisted preprocessing+model pipeline artifact."""
    path = Path(artifact_path)
    if not path.exists():
        raise FileNotFoundError(f"ML model artifact not found: {path}")
    return joblib.load(path)


def predict_risk(features: dict[str, Any], settings: Settings | None = None, top_n_factors: int = 5) -> RiskPredictionResult:
    """Predict risk with model-derived factors; no LLM prose is included."""
    settings = settings or get_settings()
    row = {column: features.get(column) for column in FEATURE_COLUMNS}
    model = load_model(settings.ml_model_artifact_path)
    probability = float(model.predict_proba(pd.DataFrame([row], columns=FEATURE_COLUMNS))[:, 1][0])
    score = probability_to_score(probability)
    return RiskPredictionResult(
        probability=probability,
        risk_score=score,
        risk_level=risk_level_for_score(score, settings.risk_low_threshold, settings.risk_high_threshold),
        model_version=Path(settings.ml_model_artifact_path).stem,
        model_derived_risk_factors=tuple(explain_prediction(model, row, top_n=top_n_factors)),
    )
