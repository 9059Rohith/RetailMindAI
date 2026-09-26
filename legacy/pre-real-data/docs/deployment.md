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

`docker compose up --build` starts the app at `http://localhost:8501` and a MySQL 8.4 container with a local development password. Set `APP_PORT=8502` before running Compose if port 8501 is occupied. The app checks the MySQL connection and falls back to SQLite if unavailable. The database service is initialized from `sql/schema.sql`, `sql/indexes.sql` and `sql/seed.sql`; example reports are in `sql/analytical_queries.sql`. Change the example passwords before any network-exposed deployment.

The normalized save/load path was exercised against MySQL 8.0.46 in WSL and MySQL 8.4.11 through Docker Desktop. The Desktop run built both services, initialized the SQL schema and indexes, reached healthy status for both containers, and returned HTTP 200 from the app. Inside the app container, all nine workspace pages rendered without exceptions. The app connected to MySQL, saved and loaded 14 generated records, then replaced them with 7 records without leaving stale fact rows. The bundled analytical queries executed successfully.

## Verification

Run `python -m pytest -q`, `python -m ruff check .`, `python -m scripts.generate_demo`, `python -m scripts.evaluate`, then `streamlit run app/main.py`. The workflow template in `ci/quality-gates.yml` repeats lint, tests, generator, evaluation and syntax compilation once copied to `.github/workflows/ci.yml` by a credential with GitHub's `workflow` permission. Hosted CI is not currently active.
