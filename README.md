# Green Oracle 2026

A bilingual FastAPI website that turns `worldcup2026-green-oracle` into a schedule-first World Cup prediction desk. It syncs official World Cup fixtures and standings from football-data.org, runs the bundled Green Oracle engine for every prediction, lets the model fill explanation text only, and keeps a deterministic site fallback as the final safety net.

## Features

- Chinese and English homepages at `/` and `/en`
- Schedule-first homepage powered by a synced World Cup snapshot
- Green Oracle engine execution via `worldcup2026-green-oracle/tools/predict.py`
- Immutable numeric predictions with model-only commentary filling
- Knockout support with both 90-minute probabilities and advance outlook
- Prompt section six generated from the synced schedule snapshot
- JSON APIs at `GET /api/schedule` and `POST /api/predict`
- Protected `POST /internal/sync` endpoint for optional manual refreshes
- Docker and `railway.json` for the shortest Railway deployment path

## Quick Start

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e .[dev]
cp .env.example .env
.venv/bin/uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

If `FOOTBALL_DATA_API_KEY` is unset, the sync endpoint will still try the provider without auth, but availability depends on the provider's current limits and coverage.

## Environment

Core settings:

- `APP_BASE_URL`
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_TRANSLATION_MODEL`
- `FOOTBALL_DATA_BASE_URL`
- `FOOTBALL_DATA_API_KEY`
- `FOOTBALL_DATA_COMPETITION_CODE`
- `SCHEDULE_CACHE_PATH`
- `INTERNAL_SYNC_TOKEN`
- `REQUEST_TIMEOUT_S`
- `RATE_LIMIT_PER_MINUTE`
- `DEMO_FALLBACK_ENABLED`

## APIs

```json
GET /api/schedule
```

```json
POST /api/predict
{
  "teamA": "mexico",
  "teamB": "south-africa",
  "stage": "group",
  "lang": "zh",
  "fixtureId": "fd-12345"
}
```

## Railway Deployment

- Import the GitHub repository into Railway and let it build from the included Dockerfile.
- Railway injects `PORT`, which the container now honors automatically.
- Set `APP_BASE_URL` to the generated Railway public domain after the service is created.
- Required variables for the current working setup:
  - `FOOTBALL_DATA_API_KEY`
  - `ANTHROPIC_BASE_URL`
  - `ANTHROPIC_AUTH_TOKEN`
  - `ANTHROPIC_MODEL`
  - `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`
  - `CLAUDE_CODE_ATTRIBUTION_HEADER`

## Upstream Attribution

- Prediction skill source: `worldcup2026-green-oracle/SKILL.md`
- Original inspiration and MIT upstream prompt: `TradingAi666/worldcup2026-prediction-skill`
- Original upstream license copy: `app/data/upstream_LICENSE`

## Testing

```bash
.venv/bin/pytest
```
