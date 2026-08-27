"""Phase 12 security, reliability, and end-to-end workflow hardening tests."""

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.schemas.api import InvestigationResponse
from app.services.gemini_agent import GeminiAgentResponseInvalid, GeminiAgentUnavailable, GeminiInvestigationAgent
from tests.test_api_v1 import _prediction_payload
from tests.test_risk_cases import _create_case
from app.core.config import get_settings
from app.main import app


def test_cors_rejects_wildcards_and_normalizes_explicit_origins() -> None:
    settings = Settings(backend_cors_origins=" http://localhost:5173,https://demo.example.test ")
    assert settings.cors_origins == ["http://localhost:5173", "https://demo.example.test"]
    with pytest.raises(ValueError, match="wildcard CORS"):
        Settings(backend_cors_origins="*")


def test_gemini_retries_transient_failure_then_returns_valid_response() -> None:
    calls = {"count": 0}
    result = InvestigationResponse(
        risk_summary="Synthetic evidence reviewed.",
        evidence_references=["evidence_1"],
        risk_factors=["Prior synthetic dispute evidence."],
        recommendation="MANUAL_REVIEW",
        confidence=0.6,
        requires_human_review=True,
    )

    class FlakyClient:
        class models:
            @staticmethod
            def generate_content(**_: object) -> object:
                calls["count"] += 1
                if calls["count"] == 1:
                    raise TimeoutError("temporary timeout")
                return SimpleNamespace(candidates=[], text=result.model_dump_json())

    agent = GeminiInvestigationAgent(Settings(gemini_api_key="test-key", gemini_max_retries=1), client=FlakyClient())
    assert agent._validated_result(agent._response_text(agent._generate_content([])), {"evidence_1"}) == result
    assert calls["count"] == 2


def test_gemini_failure_path_returns_controlled_503(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    case = _create_case(api_client)

    def fail_investigate(self: GeminiInvestigationAgent, case_obj: object, db: object) -> tuple[InvestigationResponse, list[dict[str, Any]]]:
        raise GeminiAgentUnavailable("Gemini investigation is temporarily unavailable")

    monkeypatch.setattr(GeminiInvestigationAgent, "investigate", fail_investigate)
    previous_override = app.dependency_overrides[get_settings]
    app.dependency_overrides[get_settings] = lambda: previous_override().model_copy(update={"gemini_api_key": "test-key"})
    response = api_client.post(f"/api/v1/cases/{case['case_id']}/investigate")
    assert response.status_code == 503
    assert response.json() == {"detail": "Gemini investigation is temporarily unavailable", "code": "http_error"}
    app.dependency_overrides[get_settings] = previous_override


def test_malformed_structured_output_and_missing_evidence_are_rejected() -> None:
    with pytest.raises(GeminiAgentResponseInvalid, match="invalid investigation result"):
        GeminiInvestigationAgent._validated_result("not-json", {"evidence_1"})
    missing = InvestigationResponse(
        risk_summary="Synthetic evidence reviewed.",
        evidence_references=["evidence_missing"],
        risk_factors=["A cited item was not returned by tools."],
        recommendation="MANUAL_REVIEW",
        confidence=0.5,
        requires_human_review=True,
    )
    with pytest.raises(GeminiAgentResponseInvalid, match="not returned by a tool"):
        GeminiInvestigationAgent._validated_result(missing.model_dump_json(), {"evidence_1"})


def test_invalid_case_transition_and_api_validation_are_controlled(api_client: TestClient) -> None:
    case = _create_case(api_client)
    transition = api_client.patch(f"/api/v1/cases/{case['case_id']}", json={"status": "CLOSED"})
    assert transition.status_code == 409
    assert transition.json()["code"] == "http_error"

    malformed_prediction = api_client.post("/api/v1/risk/predict", json={"transaction_id": "bad id", "amount": -100})
    assert malformed_prediction.status_code == 422
    assert malformed_prediction.json() == {"detail": "Request validation failed", "code": "validation_error"}

    bad_path = api_client.get("/api/v1/transactions/not allowed")
    assert bad_path.status_code == 422
    assert bad_path.json()["code"] == "validation_error"


def test_model_metrics_endpoint_regression(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/model/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["model_version"]
    assert body["dataset_version"]
    assert {"precision", "recall", "f1", "accuracy", "roc_auc", "confusion_matrix"} <= set(body["metrics"])
    assert isinstance(body["metrics"]["confusion_matrix"], list)


def test_full_transaction_prediction_case_investigation_evidence_recommendation_flow(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def deterministic_investigate(self: GeminiInvestigationAgent, case_obj: object, db: object) -> tuple[InvestigationResponse, list[dict[str, Any]]]:
        evidence = api_client.get(f"/api/v1/cases/{case_obj.case_id}/evidence").json()
        evidence_id = evidence[0]["id"]
        return (
            InvestigationResponse(
                risk_summary="Synthetic database evidence was reviewed for human triage.",
                evidence_references=[evidence_id],
                risk_factors=["ML prediction and traceable synthetic evidence require human review."],
                recommendation="MANUAL_REVIEW",
                confidence=0.7,
                requires_human_review=True,
            ),
            [{"tool_name": "create_evidence_report", "arguments": {}, "evidence_references": [evidence_id]}],
        )

    monkeypatch.setattr(GeminiInvestigationAgent, "investigate", deterministic_investigate)
    previous_override = app.dependency_overrides[get_settings]
    app.dependency_overrides[get_settings] = lambda: previous_override().model_copy(update={"gemini_api_key": "test-key"})
    transaction = api_client.get("/api/v1/transactions", params={"page": 1, "page_size": 1}).json()["items"][0]
    payload = _prediction_payload()
    payload["transaction_id"] = transaction["transaction_id"]
    prediction = api_client.post("/api/v1/risk/predict", json=payload)
    assert prediction.status_code == 201
    case = api_client.post("/api/v1/cases", json={"transaction_id": transaction["transaction_id"], "assigned_reviewer": "reviewer@example.test"})
    assert case.status_code == 201
    case_id = case.json()["case_id"]
    investigation = api_client.post(f"/api/v1/cases/{case_id}/investigate")
    assert investigation.status_code == 200
    evidence = api_client.post(f"/api/v1/cases/{case_id}/evidence")
    assert evidence.status_code == 201
    recommendation = api_client.post(f"/api/v1/cases/{case_id}/recommendation")
    assert recommendation.status_code == 201
    assert recommendation.json()["human_approval_required"] is True
    assert recommendation.json()["financial_action_executed"] is False
    app.dependency_overrides[get_settings] = previous_override
