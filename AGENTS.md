# AGENTS.md

## Project

工单数据分析系统 — 3 ML 模块 + 交互式 HTML 仪表盘。Python，无框架。

## Quick commands

```bash
pip install -r requirements.txt          # setup
python scripts/generate_data.py          # generate synthetic data (data/raw/)
python scripts/run_all.py                # run full pipeline → output/
python scripts/visualize.py              # static PNG charts → output/charts/
python scripts/dashboard.py              # regenerate HTML dashboard → output/dashboard.html
python src/api.py                        # start API server on :8000
python scripts/test_api.py               # test API endpoints
```

Run a single module directly: `python src/anomaly_detection.py` (same for risk_scoring, inventory_forecast).

## Structure

- `src/` — 3 analysis modules + utils. Each has a `run(config)` entrypoint.
- `scripts/` — orchestrators: run_all, generate_data, visualize, dashboard.
- `config/config.yaml` — all tunable parameters (contamination, weights, forecast_days, etc.).
- `data/raw/` — input CSVs (ticket_main, ticket_materials, inventory_daily).
- `output/` — CSV results + dashboard.html + charts/.
- `index.html` — copy of dashboard.html for GitHub Pages deployment.

## Gotchas

- `run_all.py` adds `src/` to `sys.path` at runtime. Individual module scripts do the same via relative import from `utils`. Do not add `src/` to PYTHONPATH globally.
- Prophet is optional — import failure prints a warning and skips. Do not hard-fail on ImportError in inventory_forecast.
- `scripts/dashboard.py` embeds all data as inline JSON in the HTML. After changing CSV outputs, must re-run `dashboard.py` to update the dashboard.
- Risk scoring logistic regression needs both classes in the label. The threshold is auto-calculated (not fixed at 0.7) to avoid single-class error.
- Chinese fonts (Noto CJK) are required for matplotlib charts. The dashboard (HTML) uses system fonts and has no such requirement.

## Deployment

GitHub Pages: `index.html` at repo root. See `DEPLOY.md` for full steps. Push to `main` triggers auto-deploy (~2 min).

## Data model

3 tables: `ticket_main` (5000 rows, PK ticket_id), `ticket_materials` (FK ticket_id), `inventory_daily` (PK: date+material_id+site_id). See `README.md` for full schema.
