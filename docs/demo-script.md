# Five-Minute Demo Script

## 0:00–0:45 — Positioning
- State that this is a synthetic fintech risk-operations application for chargeback review.
- Emphasize separation of concerns: ML scores risk; Gemini investigates and explains using backend tools.
- Call out the safety boundary: no autonomous financial action.

## 0:45–1:30 — Dashboard
- Start backend and frontend, then open `http://localhost:5173`.
- Point to dashboard KPIs and actual held-out model metrics loaded from backend artifacts.
- Click **Open hero transaction** for `TX-DEMO-001`.

## 1:30–2:10 — Transaction queue
- Show the pre-filtered hero transaction.
- Explain why it is synthetic but realistic: high amount, failed status, cross-border merchant context, and previous customer disputes.
- Click **Investigate**.

## 2:10–3:40 — Investigation workflow
- In the case screen, show the audited ML risk score and case guardrails.
- Click **Investigate** to call the backend Gemini investigation service if `GEMINI_API_KEY` is configured.
- Click **Build evidence package** to generate database-sourced evidence.
- Click **Generate recommendation** to persist a bounded, human-review recommendation.

## 3:40–4:30 — Evidence traceability and safety
- Show evidence source table/record IDs.
- Show `Human Approval Required` and `financial_action_executed: false`.
- Mention Gemini failures do not block ML prediction.

## 4:30–5:00 — Technical close
- Mention FastAPI, SQLAlchemy, scikit-learn/XGBoost, React/TypeScript, pytest, and environment-based secrets.
- Close with limitations: synthetic data only, no production Razorpay data, no autonomous financial actions.
