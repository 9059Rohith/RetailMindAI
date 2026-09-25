# Deployment

## Streamlit Community Cloud

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, create an app from `9059Rohith/RetailMindAI`, branch `main`, main file `app/main.py`.
3. Use Python 3.12 if the deployment UI offers a runtime choice. `requirements.txt` is discovered at the repository root.
4. No secret or database is required for the included demo. The app starts directly from `data/demo_sales.csv`.
5. Wait for the app's health indicator and open the public `streamlit.app` URL.

Streamlit Community Cloud's local filesystem is ephemeral. Do not treat local artifacts or SQLite as durable shared storage. The public demo has no login or per-user database isolation; do not upload sensitive retail data.

## Local Docker

`docker compose up --build` starts the app at `http://localhost:8501` and a MySQL 8.4 container with a local development password. The app checks the MySQL connection and falls back to SQLite if unavailable. The database service is initialized from `sql/mysql_schema.sql`. Change the example passwords before any network-exposed deployment.

## Verification

Run `python -m pytest -q`, `python -m ruff check .`, `python -m scripts.generate_demo`, `python -m scripts.evaluate`, then `streamlit run app/main.py`. The workflow template in `ci/quality-gates.yml` repeats lint, tests, generator, evaluation and syntax compilation once copied to `.github/workflows/ci.yml` by a credential with GitHub's `workflow` permission. Hosted CI is not currently active.
