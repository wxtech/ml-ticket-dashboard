# AGENTS.md

## Project

工单数据分析系统 — 3 ML 模块 + Web应用 + 交互式HTML仪表盘。Python。

## Quick commands

```bash
pip install -r requirements.txt          # setup
python scripts/generate_data.py          # generate synthetic data (data/raw/)
python scripts/run_all.py                # run full pipeline → output/
python scripts/visualize.py              # static PNG charts → output/charts/
python scripts/dashboard.py              # regenerate HTML dashboard → output/dashboard.html
python app.py                            # start Web app on :8080 (login/dashboard/upload)
python src/api.py                        # start REST API on :8000
python scripts/test_api.py               # test API endpoints
```

Run a single module directly: `python src/anomaly_detection.py` (same for risk_scoring, inventory_forecast).

## Structure

- `src/` — 3 analysis modules + api + auth + utils. Each module has a `run(config)` entrypoint.
- `scripts/` — orchestrators: run_all, generate_data, visualize, dashboard, test_api.
- `templates/` — HTML pages: login.html, dashboard.html, upload.html (Jinja2).
- `config/config.yaml` — all tunable parameters.
- `data/raw/` — input CSVs (ticket_main, ticket_materials, inventory_daily).
- `data/uploads/` — user uploaded files (auto-created).
- `data/users.json` — JWT user accounts (auto-created on first run).
- `output/` — CSV results + dashboard.html + charts/ + logs/.
- `app.py` — Web application entry (port 8080), serves templates + static.
- `src/api.py` — REST API entry (port 8000), Swagger docs at /docs.
- `index.html` — copy of dashboard.html for GitHub Pages deployment.

## Gotchas

- `app.py` adds both `src/` and `scripts/` to sys.path. Do not add them globally.
- Prophet is optional — import failure prints a warning and skips.
- `scripts/dashboard.py` embeds all data as inline JSON. After CSV changes, re-run `dashboard.py`.
- Risk scoring logistic regression auto-calculates threshold to avoid single-class error.
- Chinese fonts (Noto CJK) required for matplotlib charts. HTML dashboard uses system fonts.
- `app.py` runs background analysis threads for upload tasks. Task state is in-memory (lost on restart).

## Two servers

- **Port 8080** (`app.py`): Web UI with login, dashboard, upload. Serves templates.
- **Port 8000** (`src/api.py`): REST API with Swagger docs. Used by external integrations.

## Deployment

GitHub Pages: `index.html` at repo root. See `DEPLOY.md`. Push to `main` triggers auto-deploy.

## Data model

3 tables: `ticket_main` (5000 rows, PK ticket_id), `ticket_materials` (FK ticket_id), `inventory_daily` (PK: date+material_id+site_id). See `README.md` for full schema.
