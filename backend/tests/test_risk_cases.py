"""Phase 6 integration tests for traceable risk investigation cases."""

from fastapi.testclient import TestClient

from tests.test_api_v1 import _prediction_payload


def _create_case(client: TestClient, transaction_id: str = "synthetic_phase2_txn_0000") -> dict[str, object]:
    payload = _prediction_payload()
    payload["transaction_id"] = transaction_id
    assert client.post("/api/v1/risk/predict", json=payload).status_code == 201
    response = client.post("/api/v1/cases", json={"transaction_id": transaction_id, "assigned_reviewer": "reviewer@example.test"})
    assert response.status_code == 201
    return response.json()


def test_case_creation_builds_traceable_database_evidence(api_client: TestClient) -> None:
    case = _create_case(api_client)
    assert case["status"] == "NEW"
    assert case["history"][0]["event_type"] == "CASE_CREATED"
    evidence = api_client.get(f"/api/v1/cases/{case['case_id']}/evidence")
    assert evidence.status_code == 200
    items = evidence.json()
    assert {item["source"] for item in items} >= {"transactions", "customers", "merchants", "risk_predictions"}
    assert all(item["source_id"] and item["verification_status"] for item in items)
    prediction = next(item for item in items if item["source"] == "risk_predictions")
    assert prediction["source_id"] == case["prediction_id"]


def test_missing_related_evidence_is_explicitly_unavailable(api_client: TestClient) -> None:
    case = _create_case(api_client, "synthetic_phase2_txn_0050")
    items = api_client.get(f"/api/v1/cases/{case['case_id']}/evidence").json()
    unavailable = [item for item in items if item["verification_status"] == "EVIDENCE_UNAVAILABLE"]
    assert unavailable
    assert all(item["factual_content"] == "Evidence unavailable" and item["source_id"].startswith("unavailable:") for item in unavailable)


def test_case_status_transitions_are_validated_and_audited(api_client: TestClient) -> None:
    case = _create_case(api_client)
    rejected = api_client.patch(f"/api/v1/cases/{case['case_id']}", json={"status": "APPROVED"})
    assert rejected.status_code == 409
    investigating = api_client.patch(f"/api/v1/cases/{case['case_id']}", json={"status": "INVESTIGATING"})
    assert investigating.status_code == 200
    assert investigating.json()["status"] == "INVESTIGATING"
    assert investigating.json()["history"][-1]["from_status"] == "NEW"


def test_case_creation_is_idempotent_for_latest_prediction(api_client: TestClient) -> None:
    first = _create_case(api_client)
    second = api_client.post("/api/v1/cases", json={"transaction_id": first["transaction_id"]})
    assert second.status_code == 201
    assert second.json()["case_id"] == first["case_id"]
