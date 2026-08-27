# Final Submission Checklist

Use this checklist after running the clean-install and regression commands in
the README. This project is submitted for **Razorpay AI Builder Internship
2026 — Track 02: AI Risk Manager** as **AI Chargeback Risk & Evidence Response
Agent**.

## Reproducibility and release verification

- [ ] Start from a fresh clone and copy `.env.example` to `.env`; do not put a
  secret in a tracked file.
- [ ] Install the backend dependencies, run `python -m app.ml.train_model`,
  then verify that `artifacts/models/chargeback-risk-v1.joblib`,
  `.metadata.json`, `.evaluation.json`, `.evaluation.md`, and `.registry.json`
  were created locally.
- [ ] Confirm metadata and evaluation JSON have the same `model_version`,
  `model_type`, and `dataset_fingerprint`, and retain the generated evaluation
  JSON for the submission record.
- [ ] Record the actual held-out-test `precision`, `recall`, `f1`, `accuracy`,
  `roc_auc`, and confusion matrix from the locally generated evaluation JSON.
  Do not replace these values with claims from a prior run.
- [ ] Run backend `pytest` and frontend `npm run build` successfully.
- [ ] Start the API, call `POST /api/v1/seed` in development, and verify
  `GET /api/v1/health` returns `{"status":"ok","service":"api"}`.
- [ ] Open the frontend and verify `/api/v1/model/metrics` supplies the actual
  local held-out metrics to the dashboard.

## End-to-end demo verification

- [ ] Locate synthetic transaction `TX-DEMO-001` in the dashboard or
  transaction queue.
- [ ] Create or open its case, confirm the ML risk score is present, and show
  that it was computed without requiring Gemini availability.
- [ ] With a valid backend-only `GEMINI_API_KEY` configured, run
  **Investigate** and confirm the completed result cites only tool-returned
  evidence references.
- [ ] Build an evidence package and verify every claim exposes a source table
  and source record ID, or explicitly says `Evidence unavailable`.
- [ ] Generate a recommendation and verify that `human_approval_required` is
  true and `financial_action_executed` is false.
- [ ] Temporarily use an invalid/unavailable Gemini configuration and verify a
  controlled investigation failure does not prevent ML prediction.

## Safety and repository hygiene

- [ ] Confirm all dataset, UI, and demo claims identify the data as synthetic.
- [ ] Confirm no endpoint or UI path executes refunds, reversals, transfers,
  account closures, or payment-network submissions.
- [ ] Review tracked files and Git history for `.env` files, API keys, private
  keys, `node_modules`, virtual environments, and model binaries larger than
  100 MB.
- [ ] Keep locally generated artifacts, databases, and screenshots out of the
  commit unless a future release policy explicitly approves them.
- [ ] Confirm `git status --short` is clean immediately before submission.

## External submission fields

- [ ] GitHub repository URL is public and opens without authentication.
- [ ] Five-minute pitch-video URL is valid and plays.
- [ ] The video demonstrates `TX-DEMO-001`, the generated held-out metrics,
  traceable evidence, and the human-approval boundary.
- [ ] README, architecture diagram, ML pipeline diagram, agent workflow,
  demo script, and evaluator Q&A match the final implementation.
