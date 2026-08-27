# Architecture Diagram

```mermaid
flowchart LR
  Reviewer[Human reviewer] --> Frontend[React + TypeScript UI]
  Frontend -->|REST /api/v1| API[FastAPI backend]
  API --> DB[(SQLite local / PostgreSQL-compatible)]
  API --> ML[Scikit-learn/XGBoost risk model artifact]
  API --> Agent[Gemini investigation service]
  Agent --> Tools[Restricted backend tools]
  Tools --> DB
  API --> Evidence[Versioned evidence packages]
  API --> Recommendation[Bounded recommendation records]
  Recommendation --> Reviewer
```

## Safety boundary

The application separates quantitative ML prediction from the Gemini investigation layer. Gemini is called only by backend services, through restricted tools, after a human reviewer starts an investigation. Recommendations are persisted for review only; the app does not execute refunds, reversals, transfers, payment-network submissions, or account closures.
