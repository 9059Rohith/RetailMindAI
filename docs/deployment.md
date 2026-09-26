# Deployment

## Streamlit Community Cloud

**Live app:** [RetailMind AI on Streamlit Community Cloud](https://retailmindai-xfekkmevt9zabpnngqtcq8.streamlit.app/). The public dashboard and analytics loaded with the committed M5 observations on 26 September 2026.

The application starts from the committed real M5 subset and needs no secret or database. To reproduce the deployment, deploy the [GitHub repository](https://github.com/9059Rohith/RetailMindAI) with:

| Setting | Value |
| --- | --- |
| Repository | `9059Rohith/RetailMindAI` |
| Branch | `main` |
| Main file path | `app/main.py` |
| Dependencies | Root `requirements.txt` |
| Python | 3.12, when selectable |

If Community Cloud says **“the app’s code is not connected to a remote GitHub repository”** while creating another app, check that you are in the workspace for `9059Rohith` and that the repository owner has [connected and authorized GitHub](https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/connect-your-github-account). Streamlit requires admin permission on the repository. A local `git remote` or successful `git push` alone does not authorize the Community Cloud account.

The **Deploy** button inside the local Docker app also cannot discover the host's Git remote: Docker intentionally excludes `.git` from the image. Start deployment from [Community Cloud](https://share.streamlit.io/) using the pushed GitHub repository, rather than from that local button.

The Cloud filesystem is ephemeral. SQLite and model registry files are suitable for a local project demonstration, not durable multiuser storage. Public uploads should not contain confidential data.

## Local Docker

Run `docker compose up --build` to start Streamlit and MySQL 8.4. The default app port is 8501; set `APP_PORT=8502` if occupied. Docker uses local development credentials in `docker-compose.yml`; change them before exposing MySQL. Startup works without MySQL by falling back to SQLite.

## Verification

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest -q
python -m scripts.evaluate --horizon 7
python -m compileall -q app retailmind scripts
```

The `ci/quality-gates.yml` file is a GitHub Actions template. Hosted CI needs it installed at `.github/workflows/ci.yml` by a credential with `workflow` scope. Local checks remain runnable independently.
