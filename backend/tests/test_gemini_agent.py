"""Phase 7 tests for controlled Gemini investigation behavior."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.schemas.api import InvestigationResponse
from app.services.gemini_agent import GeminiAgentResponseInvalid, GeminiInvestigationAgent
from tests.test_api_v1 import _prediction_payload
from tests.test_risk_cases import _create_case


class EvidenceThenResultClient:
    """A provider double that proves tool outputs, rather than prompts, feed the result."""

    def __init__(self) -> None:
        self.calls: list[list[object]] = []

    class models:
        pass

    def generate(self, **kwargs: object) -> object:
        self.calls.append(kwargs["contents"])
        if len(self.calls) == 1:
            function_call = SimpleNamespace(name="create_evidence_report", args={})
            return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(function_call=function_call)]))])
        tool_response = self.calls[-1][-1]["parts"][0]["function_response"]["response"]
        evidence_id = tool_response["evidence_references"][0]
        return SimpleNamespace(candidates=[], text=json.dumps({"risk_summary": "Synthetic database evidence was reviewed.", "evidence_references": [evidence_id], "risk_factors": ["ML risk result requires review."], "recommendation": "MANUAL_REVIEW", "confidence": 0.7, "requires_human_review": True}))


def _agent_with_client(client: EvidenceThenResultClient) -> GeminiInvestigationAgent:
    client.models.generate_content = client.generate
    return GeminiInvestigationAgent(Settings(gemini_api_key="test-key"), client=client)


def test_agent_executes_allowlisted_tool_and_validates_tool_grounded_evidence(api_client: TestClient) -> None:
    case = _create_case(api_client)
    from app.db.session import get_db
    from app.main import app

    db = next(app.dependency_overrides[get_db]())
    try:
        from app.api.v1.cases import _case_or_404

        client = EvidenceThenResultClient()
        result, trace = _agent_with_client(client).investigate(_case_or_404(db, case["case_id"]), db)
    finally:
        db.close()
    assert result.requires_human_review is True
    assert len(trace) == 1
    assert trace[0]["tool_name"] == "create_evidence_report"
    assert trace[0]["arguments"] == {}
    assert set(result.evidence_references).issubset(trace[0]["evidence_references"])
    assert len(client.calls) == 2


def test_agent_rejects_disallowed_tools_and_malformed_or_ungrounded_output(api_client: TestClient) -> None:
    case = _create_case(api_client)
    from app.db.session import get_db
    from app.main import app
    from app.api.v1.cases import _case_or_404

    db = next(app.dependency_overrides[get_db]())
    try:
        bad_call = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(function_call=SimpleNamespace(name="delete_all_transactions", args={}))]))])
        class BadClient:
            class models:
                @staticmethod
                def generate_content(**_: object) -> object:
                    return bad_call
        with pytest.raises(GeminiAgentResponseInvalid, match="disallowed tool"):
            GeminiInvestigationAgent(Settings(gemini_api_key="test-key"), client=BadClient()).investigate(_case_or_404(db, case["case_id"]), db)
    finally:
        db.close()

    with pytest.raises(GeminiAgentResponseInvalid, match="invalid investigation result"):
        GeminiInvestigationAgent._validated_result("{not json}", set())
    valid_but_ungrounded = InvestigationResponse(risk_summary="Review", evidence_references=["evidence_1"], risk_factors=["Factor"], recommendation="MANUAL_REVIEW", confidence=0.5, requires_human_review=True)
    with pytest.raises(GeminiAgentResponseInvalid, match="not returned by a tool"):
        GeminiInvestigationAgent._validated_result(valid_but_ungrounded.model_dump_json(), set())


def test_gemini_outage_is_controlled_without_affecting_ml_prediction(api_client: TestClient) -> None:
    case = _create_case(api_client)
    unavailable = api_client.post(f"/api/v1/cases/{case['case_id']}/investigate")
    assert unavailable.status_code == 503
    assert "Gemini investigation is unavailable" in unavailable.json()["detail"]
    assert api_client.post("/api/v1/risk/predict", json=_prediction_payload()).status_code == 201
