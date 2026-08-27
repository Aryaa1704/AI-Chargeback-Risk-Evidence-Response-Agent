"""Phase 8 tests for versioned evidence packages and bounded recommendations."""

import inspect

from fastapi.testclient import TestClient

from app.services import response_builder
from tests.test_risk_cases import _create_case


def _investigating_case(client: TestClient) -> dict[str, object]:
    case = _create_case(client)
    response = client.patch(f"/api/v1/cases/{case['case_id']}", json={"status": "INVESTIGATING"})
    assert response.status_code == 200
    return case


def test_evidence_package_contains_traceable_sections_and_can_regenerate(api_client: TestClient) -> None:
    case = _investigating_case(api_client)
    first = api_client.post(f"/api/v1/cases/{case['case_id']}/evidence")
    assert first.status_code == 201
    body = first.json()
    assert body["version"] == 1
    assert body["recommended_response"] in {"MANUAL_REVIEW", "MONITOR", "REQUEST_ADDITIONAL_VERIFICATION", "PRIORITIZE_CHARGEBACK_RESPONSE", "PREPARE_EVIDENCE_PACKAGE", "LOW_PRIORITY_REVIEW"}
    for section in ("transaction_evidence", "customer_history", "previous_disputes", "risk_analysis"):
        assert body[section]
        assert all(claim["content"] and claim["source"] and claim["source_id"] for claim in body[section])
    assert any(claim["source"] == "risk_predictions" and "ML factor" in claim["content"] for claim in body["risk_analysis"])

    regenerated = api_client.post(f"/api/v1/cases/{case['case_id']}/evidence")
    assert regenerated.status_code == 201
    assert regenerated.json()["version"] == 2


def test_recommendation_is_bounded_requires_approval_and_never_executes_financial_action(api_client: TestClient) -> None:
    case = _investigating_case(api_client)
    assert api_client.post(f"/api/v1/cases/{case['case_id']}/recommendation").status_code == 409
    evidence = api_client.post(f"/api/v1/cases/{case['case_id']}/evidence").json()
    response = api_client.post(f"/api/v1/cases/{case['case_id']}/recommendation")
    assert response.status_code == 201
    body = response.json()
    assert body["evidence_package_id"] == evidence["package_id"]
    assert body["human_approval_required"] is True
    assert body["financial_action_executed"] is False
    assert body["category"] in {"MANUAL_REVIEW", "MONITOR", "REQUEST_ADDITIONAL_VERIFICATION", "PRIORITIZE_CHARGEBACK_RESPONSE", "PREPARE_EVIDENCE_PACKAGE", "LOW_PRIORITY_REVIEW"}
    assert "requires human approval" in body["rationale"]
    assert api_client.get(f"/api/v1/cases/{case['case_id']}").json()["status"] == "INVESTIGATING"


def test_response_generation_obeys_case_state_rules(api_client: TestClient) -> None:
    case = _create_case(api_client)
    assert api_client.post(f"/api/v1/cases/{case['case_id']}/evidence").status_code == 409
    assert api_client.post(f"/api/v1/cases/{case['case_id']}/recommendation").status_code == 409


def test_response_builder_has_no_financial_execution_operations() -> None:
    """Evidence and recommendations may only create review artifacts, never execute money movement."""
    implementation = inspect.getsource(response_builder).lower()
    for forbidden_operation in ("issue_refund", "reverse_transaction", "transfer_money", "close_account"):
        assert forbidden_operation not in implementation
