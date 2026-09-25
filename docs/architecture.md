# Architecture

RetailMind AI separates **observed data**, **prediction**, and **decision support**.

```mermaid
flowchart LR
  A[Included demo / uploaded CSV / seeded generator] --> B[Validation + explicit cleaning]
  B --> C[Observed analytics + KPIs]
  B --> D[Leakage-safe daily features]
  D --> E[Expanding-window backtests]
  E --> F[Selected forecast + heuristic band]
  C --> G[Inventory policies]
  F --> G
  G --> H[Replenishment + risk + allocation]
  H --> I[What-if simulation + alerts + CSV reports]
  B <--> J[(SQLite / optional MySQL)]
```

The Streamlit interface is in `app/`. Testable calculations are in `retailmind/`. The included CSV is small enough for Community Cloud. Uploaded data remains in the user's Streamlit session unless they press **Save current dataset to database**. In a public deployment, local SQLite storage is ephemeral and shared by the app process; do not upload confidential data.

The MySQL DDL in `sql/mysql_schema.sql` documents a normalized academic schema (`products`, `stores`, `sales`, `inventory`, `forecast_runs`). The application's quick-save path persists a separate denormalized `sales_snapshot` table via pandas SQL for easy demo round trips, leaving the normalized tables intact. For a production multiuser deployment, use migrations, separate tenant identity and write access controls.
