# Deployment

## Streamlit Community Cloud

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, create an app from `9059Rohith/RetailMindAI`, branch `main`, main file `app/main.py`.
3. Use Python 3.12 if the deployment UI offers a runtime choice. `requirements.txt` is discovered at the repository root.
4. No secret or database is required for the included demo. The app starts directly from `data/demo_sales.csv`.
5. Wait for the app's health indicator and open the public `streamlit.app` URL.

Streamlit Community Cloud's local filesystem is ephemeral. Do not treat local artifacts or SQLite as durable shared storage. The public demo has no login or per-user database isolation; do not upload sensitive retail data.

The M5 importer accepts the three official CSVs through the browser. The configured upload cap is 300 MB per file. Large benchmark imports can exceed a free host's memory or request limits; use the local Docker or Python setup for full official files, and keep the sample size bounded in the M5 tab.

## Local Docker

`docker compose up --build` starts the app at `http://localhost:8501` and a MySQL 8.4 container with a local development password. The app checks the MySQL connection and falls back to SQLite if unavailable. The database service is initialized from `sql/schema.sql`, `sql/indexes.sql` and `sql/seed.sql`; example reports are in `sql/analytical_queries.sql`. Change the example passwords before any network-exposed deployment.

The normalized save/load path was also exercised against a live MySQL 8.0.46 server in WSL: schema, indexes and seed loaded; 280 generated records populated product/store/calendar/sales/inventory/promotion/price tables; a second save replaced the active sales, inventory, price and snapshot rows with 14 records; all analytical queries executed. This verifies the SQL path independently of Docker. Docker Compose configuration validates, but the local Docker Desktop daemon could not start, so a containerized runtime check remains open.

## Verification

Run `python -m pytest -q`, `python -m ruff check .`, `python -m scripts.generate_demo`, `python -m scripts.evaluate`, then `streamlit run app/main.py`. The workflow template in `ci/quality-gates.yml` repeats lint, tests, generator, evaluation and syntax compilation once copied to `.github/workflows/ci.yml` by a credential with GitHub's `workflow` permission. Hosted CI is not currently active.
