# Football intelligence platform

Backend, data pipeline and AI agent prototype for a football analytics product: collecting match data, measuring the accuracy of predictions and answering questions in natural language.

[![CI](https://github.com/firechair/football-intelligence-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/firechair/football-intelligence-platform/actions/workflows/ci.yml)

## What it did

The product collected fixtures, predictions and odds compared across bookmakers, then measured how often those predictions came true. Users could ask about the data through an AI assistant.

It was an MVP, stopped before launch. See [Project status](#project-status) for what worked and what did not.

## Architecture

```mermaid
flowchart LR
    provider["Football API<br/>(mock in the demo)"] --> ingestion["ingestion/<br/>FastAPI, scheduler"]
    ingestion --> pg[("Postgres")]
    pg --> web["web/<br/>Next.js accuracy page"]
    platform["platform/<br/>accounts, analytics, agent"] --> pg
    platform --> redis[("Redis")]
    platform --> llm["LLM<br/>(mock in the demo)"]
    platform --> provider
```

More detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Run it

You need Docker. No API keys: the football API and the LLM are replaced by local mocks, and all data is synthetic.

```bash
docker compose up -d --build --wait

# Collect data, finish today's matches and score the predictions (about 30 seconds)
docker compose run --rm ingestion python scripts/collect_once.py --simulate-results

# Ask the agent a question: it prints the tools it called, then the answer
docker compose run --rm platform python scripts/ask_agent.py "What are the odds for Inter vs Milan?"
```

Then open:
- http://localhost:3000/accuracy for the accuracy page;
- http://localhost:8000/docs for the accounts and analytics API;
- http://localhost:8001/docs for the data API.

To stop and delete everything, run `docker compose down -v`.

To use a real LLM, copy `.env.example` to `.env` and fill it in.

### Tests

```bash
cd ingestion && pytest -q                                      # 24 tests
docker compose run --rm ingestion pytest -m integration -q     # 3 tests against Postgres and the mock API
cd platform && pytest -q --no-cov                              # 145 tests
cd demo && pytest -q                                           # 15 tests
cd web && npx vitest run                                       # 16 tests
```

## What each module shows

| Module | Where | What to look at |
|---|---|---|
| API client with rate limiting | `ingestion/app/utils/football_api.py` | Concurrency limit, atomic request spacing, per-endpoint statistics. No retry after a 429. |
| Scheduler and collectors | `ingestion/app/core/scheduler.py`, `ingestion/app/services/` | Separate jobs for fixtures, predictions, odds and results. |
| Accuracy evaluation | `ingestion/app/services/accuracy_evaluator.py` | Scores provider predictions against results. |
| Accuracy page | `web/src/app/accuracy/` | Next.js page with a typed adapter over the API. |
| Accounts and security | `platform/app/api/users.py`, `platform/app/services/` | JWT, TOTP 2FA, sessions, password recovery, rate limiting. |
| Intent detection | `platform/app/services/intent_detection.py` | Rule-based classification of Italian questions. |
| Odds movements and rankings | `platform/app/services/alert_engine.py`, `bookmaker_analytics.py` | Movement detection and a weighted bookmaker score. |
| Compliance | `platform/app/services/compliance_service.py` | Keyword screening of messages and replies, with help resources. |
| Agent (**prototype**) | `platform/app/services/function_calling_orchestrator.py` | Function-calling loop with four tools and a limit of five iterations. |

## Project status

It was an MVP, stopped before launch.

| Part | Status |
|---|---|
| Data collection, accuracy evaluation | Working, after the fixes listed below |
| Accounts and security | Working, after the fixes listed below |
| Frontend | Partial. It had about 20 pages, some with placeholder data. Only the accuracy page is published here. |
| AI chat | Unreliable. Intent detection plus an LLM was the path connected to the interface, and the Parlant framework caused timeouts and truncated answers. Not published here. |
| Function-calling agent | Prototype, never connected to the interface. Here it runs from a script. |
| Value bet detection, personalized suggestions, proprietary LLM | Not implemented. The stubs were removed, and the product used hosted models through OpenRouter. |

**Predictions come from the data provider, not from a proprietary model.** The accuracy page measures the provider's predictions.

Known limits are listed in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#known-limits).

## What the cleanup found

Making the code run from a clean clone, with tests, exposed bugs that the original project never caught. Each one has its own `fix:` commit with the explanation:

- **2FA could not work.** The secret was never saved and every code was rejected.
- **Saving a profile always failed**, and refreshing a token depended on a library missing from the requirements.
- **Accuracy results were always empty on a migrated database.** One route read fields that do not exist, and a timestamp was never set.
- **Under/over predictions could never score as correct.** The code compared them with the words "under" and "over", while the provider's documentation shows values like `-3.5`.
- **Bookmaker rankings always failed** on real data, and the cache did nothing once Redis was connected.
- **The compliance filter made harmful replies worse**, and a message about suicide received only gambling numbers.
- **Concurrent API requests started in bursts**, past the provider's limit.

The 81 account tests inherited from the project had also gone stale: 32 of them failed or errored on the first run. Their expectations now state what the code does on purpose, and the other 64 platform tests are new.

## Evolution

From prototypes in Streamlit, Flask and Go to the services here: [docs/EVOLUTION.md](docs/EVOLUTION.md). Working notes from the time are in [docs/history/](docs/history/).

## About this repository

*Extracted from a private startup codebase I built (2024–2026). History filtered for publication: product name, bookmaker names and credentials redacted, unrelated modules removed. Commits after the `history-import` tag are cleanup for publication.*

Bookmaker names such as "Bookmaker A" and the name "FIP" are placeholders from that redaction, and hosts appear as `example.invalid`.
