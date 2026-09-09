# AI Chargeback Risk & Evidence Response Agent

> **Razorpay AI Builder Internship 2026 — Track 02: AI Risk Manager**

A fintech risk-operations application that automatically predicts chargeback risk and generates AI-powered investigation reports — so human analysts can make faster, better-informed decisions on payment disputes.

🔗 **Live Demo:** https://ai-chargeback-risk-evidence-response.onrender.com/
📹 **Video Explanation:** https://youtu.be/ud7P6qilmIc?si=V4iVDrkg7O9IdUI-

---

## 🤔 What Does This App Actually Do?

Input: Disputed transaction + customer + merchant + dispute context
Processing: ML risk scoring + database-backed AI investigation
Output: Risk score + evidence-backed investigation report + recommended action for human review

When a customer raises a **chargeback dispute** (e.g., "I didn't make this payment"), a risk analyst has to manually investigate hundreds of such cases every day. This app automates that process:

1. **A transaction comes in** → the ML model instantly predicts its chargeback risk score (0–100)
2. **Gemini AI agent investigates** → it pulls evidence from the database (transaction history, customer dispute record, merchant details, etc.) and writes a structured evidence report
3. **Human analyst reviews** → they see the risk score + AI evidence summary and make the final call (Accept / Reject / Escalate)

> ⚠️ **The system never takes any financial action automatically.** No refunds, no reversals. Every recommendation requires human approval.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   FRONTEND (React + Vite)                │
│  Dashboard → Transaction Queue → Investigation Page      │
└────────────────────┬────────────────────────────────────┘
                     │ REST API calls
┌────────────────────▼────────────────────────────────────┐
│                  BACKEND (FastAPI + Python)             │
│                                                         │
│              ┌──────────────────────────┐               │
│                    ML Risk Model
                 (Selected: Random Forest)
                  22 engineered features
                  → Risk Score (0–100)
│              └────────────┬─────────────┘                │
│                   ┌───────▼────────┐                     │
│                   │  SQLite DB     │                     │
│                   │  (Transactions,│                     │
│                   │   Customers,   │                     │
│                   │   Disputes)    │                     │
│                   └────────────────┘                     │
└──────────────────────────────────────────────────────────┘
```

**Two AI components working together:**
- **ML Model** → gives a *quantitative* risk score based on transaction features
- **Gemini Agent** → gives *qualitative* investigation — reads the DB, finds patterns, writes human-readable evidence

They work independently. If Gemini is unavailable, ML prediction still works.

---


### 🧠 ML Training Pipeline

The ML pipeline is trained entirely on deterministic synthetic transaction and dispute data.

#### 1. Synthetic Data Generation

The training pipeline first creates a deterministic synthetic dataset using
`backend/app/seed/generate_synthetic.py`.

The seed generates synthetic customers, merchants, devices, transactions,
and dispute records and stores them in the database.

No real Razorpay transaction data or customer PII is used.

#### 2. Target / Chargeback Label

For each transaction, the training pipeline checks whether a corresponding
dispute record exists.

- `has_chargeback = 1` → transaction has a corresponding dispute
- `has_chargeback = 0` → transaction has no corresponding dispute

This target is generated from the synthetic dispute records and is used as
the supervised learning label.

#### 3. Feature Extraction

`backend/app/ml/features.py` converts database records into a model-ready
training dataframe.

The model uses 22 features covering:

- Transaction amount and amount deviation
- Transaction velocity over 24 hours and 7 days
- Customer account age
- Customer dispute/refund/failed-transaction history
- Device age and new-device indicator
- Currency and transaction status
- Payment method
- Merchant category
- Customer and merchant country
- Transaction time/day buckets
- Customer/merchant location match

Categorical features are one-hot encoded and numerical features are
standardized inside the ML preprocessing pipeline.

#### 4. Train / Validation / Test Split

The dataset is split using a stratified:

- 60% training set
- 20% validation set
- 20% held-out test set

A fixed random seed is used to make the training process reproducible.

The test set remains untouched during model selection.

#### 5. Model Training

Three candidate classifiers are trained:

1. Logistic Regression
2. Random Forest
3. XGBoost

Each model is combined with the same preprocessing pipeline.

The models are evaluated on the validation set using:

- Precision
- Recall
- F1 Score
- Accuracy
- ROC-AUC
- Confusion Matrix

Because missing a genuine chargeback is considered costly, model selection
prioritizes the highest validation recall, followed by F1 and ROC-AUC.

#### 6. Model Persistence

After validation, the selected model and its preprocessing pipeline are
persisted as a `.joblib` artifact.

The pipeline also stores metadata including:

- Model version
- Dataset version
- Dataset fingerprint
- Feature list
- Validation metrics
- Split policy
- Random seed

This allows the exact training configuration to be tracked and reproduced.

#### 7. Held-Out Evaluation

The selected persisted model is evaluated separately on the untouched
test set.

The resulting metrics and evaluation reports are saved as artifacts and
exposed through the backend model-metrics endpoint.

> **Important:** The dataset is synthetic and deterministic. Therefore,
> model metrics demonstrate the correctness of the ML pipeline and feature
> engineering rather than production-level chargeback prediction
> performance.

#### 8. API Inference

During application runtime, the `/api/v1/risk/predict` endpoint receives the
model-ready transaction features.

The backend:

1. Loads the persisted `.joblib` pipeline.
2. Applies the same preprocessing used during training.
3. Generates a chargeback probability.
4. Converts the probability into a 0–100 risk score.
5. Maps the score to LOW / MEDIUM / HIGH.
6. Returns model-derived risk factors for analyst review.

Gemini is not required for ML prediction, so risk scoring remains available
even if the AI investigation service is unavailable.

```

```

### Features Used by the ML Model

The model uses 22 engineered features:

| Category | Features |
|---|---|
| Transaction | amount, amount_deviation, status, currency |
| Velocity | transaction_velocity_24h, transaction_velocity_7d |
| Customer History | customer_account_age_days, customer_dispute_count, customer_refund_count, customer_failed_tx_count |
| Device | device_age_days, has_device, is_new_device |
| Ratios | dispute_ratio, refund_ratio |
| Merchant | merchant_category, merchant_country |
| Customer | customer_country, location_match |
| Time | transaction_hour_bucket, transaction_day_of_week |
| Payment | payment_method |

**Algorithm:** Random Forest Classifier (scikit-learn)
**Output:** Risk score 0–100 + label (LOW / MEDIUM / HIGH)

---

## 🔴🟡🟢 Risk Score → Agent Decision

| Score | Risk Level | What the Agent Does |
|---|---|---|
| 70–100 | 🔴 HIGH | Prioritizes counter-evidence; flags for urgent human review |
| 35–69 | 🟡 MEDIUM | Investigates both sides; presents balanced report |
| 0–34 | 🟢 LOW | Recommends acceptance with rationale |

---

## 📁 Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST endpoints (transactions, cases, risk, health)
│   │   ├── core/            # Config, error handling
│   │   ├── db/              # SQLAlchemy session + DB init
│   │   ├── ml/              # ML model: features, training, prediction, evaluation
│   │   ├── models/          # ORM models (Transaction, Customer, Dispute, RiskCase)
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── seed/            # Synthetic data generator ← DATA SOURCE IS HERE
│   │   └── services/        # Gemini agent, evidence builder, response builder
│   ├── tests/
│   └── pyproject.toml
├── docs/
│   ├── architecture.md
│   ├── ml-pipeline.md
│   ├── agent-workflow.md
│   └── demo-script.md
├── frontend/
│   ├── src/
│   └── package.json
├── .env.example
└── README.md
```

---

## 🚀 Setup & Run (Fresh Clone)

### Requirements
- Python 3.12+
- Node.js 20+
- npm 10+

### Step 1 — Clone & configure environment
```bash
git clone https://github.com/Aryaa1704/AI-Chargeback-Risk-Evidence-Response-Agent
cd AI-Chargeback-Risk-Evidence-Response-Agent
cp .env.example .env
# Add your GEMINI_API_KEY to .env
```

### Step 2 — Backend (Terminal 1)
```bash
cd backend
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -e ".[dev]"
python -m app.ml.train_model    # ← generates synthetic data + trains ML model
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 3 — Seed demo data (run once, after backend starts)
```bash
curl -X POST http://localhost:8000/api/v1/seed
```

### Step 4 — Frontend (Terminal 2)
```bash
cd frontend
npm install
npm run dev
```

Open: http://localhost:5173
Backend health check: http://localhost:8000/api/v1/health
OpenAPI/Swagger docs: http://localhost:8000/docs

---

## 🌱 Demo Transactions (Pre-seeded)

| Transaction ID | Risk Level | Description |
|---|---|---|
| `TX-DEMO-LOW-001` | 🟢 LOW | Clean domestic transaction |
| `TX-DEMO-MED-001` | 🟡 MEDIUM | Moderate risk factors |
| `TX-DEMO-HIGH-001` | 🔴 HIGH | Multiple high-risk signals |
| `TX-DEMO-REPEAT-001` | 🔴 HIGH | Customer with repeat dispute history |
| `TX-DEMO-001` | 🔴 HIGH | **Hero case** — high amount + failed + cross-border + prior disputes |

---

## ⚙️ Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `APP_ENV` | development / test / production | `development` |
| `DATABASE_URL` | SQLAlchemy DB URL | `sqlite:///./chargeback_risk.db` |
| `GEMINI_API_KEY` | Gemini API key (backend only, never exposed to frontend) | _(required)_ |
| `GEMINI_MODEL` | Gemini model to use | `gemini-2.5-flash` |
| `GEMINI_TIMEOUT_SECONDS` | Max time for Gemini request | `20` |
| `BACKEND_CORS_ORIGINS` | Allowed frontend origins | `http://localhost:5173` |
| `VITE_API_BASE_URL` | Frontend API base URL | `http://localhost:8000` |
| `ML_MODEL_ARTIFACT_PATH` | Where trained model is saved | `artifacts/models/chargeback-risk-v1.joblib` |
| `RISK_LOW_THRESHOLD` | Score below this = LOW risk | `35` |
| `RISK_HIGH_THRESHOLD` | Score above this = HIGH risk | `70` |

---

## 📈 Model Metrics

Metrics are generated fresh at training time — not hardcoded. To see them:

```bash
cd backend
python -m app.ml.train_model
cat artifacts/models/chargeback-risk-v1.evaluation.json
```

The frontend reads live metrics from `/api/v1/model/metrics`.

> Note: These metrics describe the **synthetic dataset only** and are not claims about production performance.

---

## 🔒 Safety Boundaries

This system is built with strict safety limits:

- ✅ Gemini runs **only on backend** — API key never reaches the frontend
- ✅ ML prediction works **independently** of Gemini availability
- ✅ Evidence claims **must trace to DB/tool output** — Gemini cannot hallucinate facts
- ✅ **Zero financial actions** — no refunds, reversals, transfers, or account changes
- ✅ Every recommendation requires **explicit human approval**

---

## 🧪 Tests

```bash
# Backend
cd backend
pytest

# Frontend build check
cd frontend
npm run build
```

---

## 📋 Docs & Diagrams

- [Architecture diagram](docs/architecture.md)
- [ML pipeline diagram](docs/ml-pipeline.md)
- [Agent/tool workflow](docs/agent-workflow.md)
- [Demo script (5 min)](docs/demo-script.md)
- [Evaluator Q&A](docs/evaluator-qa.md)
- [Final pitch outline](docs/final-pitch-outline.md)

---

## ⚠️ Limitations

- No authentication/login yet
- Gemini investigation requires a valid `GEMINI_API_KEY` in `.env`
- All data is synthetic — not real Razorpay production data

---

## License

MIT — see [LICENSE](LICENSE)
