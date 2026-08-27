# Five-Minute Pitch Outline

This outline is for the final recorded submission. Read metric values directly
from the locally generated `backend/artifacts/models/chargeback-risk-v1.evaluation.json`;
never state metric values from memory or replace them with fixed slides.

## 0:00–0:30 — Problem

- Chargeback teams need to prioritize risky transactions and gather facts
  across transaction, customer, device, merchant, and dispute records.
- Manual investigation is slow, while automated financial action is unsafe.

## 0:30–1:00 — Solution and differentiation

- Present AI Chargeback Risk & Evidence Response Agent as a synthetic-demo
  operations tool for Track 02: AI Risk Manager.
- Explain the separation: a persisted ML model quantifies chargeback risk;
  Gemini is a backend-only, tool-using investigation assistant.
- State the safety boundary: this app provides recommendations only and always
  requires human approval.

## 1:00–1:30 — Architecture and data flow

- Show the architecture diagram: React UI → FastAPI `/api/v1` → SQLite-local,
  PostgreSQL-compatible data layer and persisted ML artifact.
- Explain that Gemini accesses only restricted backend tools and that evidence
  references must originate from those tool/database results.
- Mention that the data is deterministic synthetic demo data, not Razorpay or
  production customer data.

## 1:30–3:45 — Live demo

1. Open the dashboard and identify `TX-DEMO-001`, the synthetic hero
   transaction.
2. Open its case and show the independently computed ML risk score and the
   audited prediction context.
3. Run **Investigate** with a configured backend `GEMINI_API_KEY`; show the
   investigation tool calls and only their returned evidence references.
4. Run **Build evidence package**; show source table/record IDs and any
   explicit unavailable-evidence markers.
5. Run **Generate recommendation**; point out `Human Approval Required` and
   `financial_action_executed: false`.

## 3:45–4:30 — Evaluation

- Open the locally generated evaluation JSON or the model metrics UI.
- State the actual held-out-test precision, recall, F1, accuracy, ROC-AUC, and
  confusion matrix from that file.
- Explain that Logistic Regression, Random Forest, and XGBoost are compared
  on validation data; model selection does not use the held-out test split.

## 4:30–5:00 — Safety, limitations, and next steps

- ML prediction remains available when Gemini is unavailable; the agent is
  not the quantitative risk model.
- No refunds, reversals, transfers, account closures, or payment-network
  submissions exist in the application.
- Close with the synthetic-data limitation and next steps: authenticated
  reviewer access, governed production data ingestion, and monitored model
  recalibration after an approved production rollout.
