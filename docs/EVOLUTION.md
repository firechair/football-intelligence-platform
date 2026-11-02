# How the project evolved

Dates come from `git log history-import` in this repository. Where the history does not record why a decision was made, this page says so.

## July 2024: project plan

A written plan for a web app that collects football data and lets people ask questions about it in natural language. It also planned a proprietary language model. That model was never built.

The plan itself is not in this repository.

## January to April 2025: prototypes

Three separate experiments, kept in [`prototypes/`](../prototypes/):

| Prototype | Date | Stack | Note |
|---|---|---|---|
| `streamlit-chatbot` | files last modified 2025-04-02 | Streamlit, transformers, LangChain web search | Ran on a Hugging Face Space that no longer exists. Imported as one snapshot commit, because the code was never committed. |
| `seriea-api` | 2025-01-21 | Flask, boto3, DynamoDB | One commit. |
| `odds-receiver` | 2025-03-18 and 2025-03-20 | Go, gorilla/mux, DynamoDB | My Go rewrite of the PHP receiver that the provider's instructions set up for its push feed. One commit, then a snapshot of the working tree, which was never committed. Fixed and tested in 2026. |

Streamlit could not show odds as they changed: every attempt at live updates is still in the code, commented out. So collection and display became separate services, described in [CHALLENGES.md](CHALLENGES.md) with the other problems of the time. The history does not record why storage moved from DynamoDB to Postgres.

## August to December 2025: the product

| Part | First commit | Last commit | Commits |
|---|---|---|---|
| Accounts and security (`platform/`) | 2025-08-03 | 2025-11-30 | 22 on `users.py` |
| Intent detection | 2025-08-03 | 2025-10-10 | 19 |
| Alerts and bookmaker analytics | 2025-08-22 | 2025-08-31 | 3 on `alert_engine.py` |
| Data collection (`ingestion/`) | 2025-09-08 | 2025-12-04 | 198 on `ingestion/app` |
| Accuracy page and its routes (`web/`) | 2025-11-11 | 2025-12-01 | 7 |

Most of the work went into the data collection service, and its commit messages show the difficulties plainly: deployment problems, schema drift between environments, and live-match filters that took many attempts.

Accuracy evaluation arrived in November, and its results depended on a schema that production and the migrations disagreed about. See "What the cleanup found" in the [README](../README.md).

[`docs/history/`](history/) holds three working notes from a debugging session on 30 September 2025.

## January 2026: the agent

The chat that users saw combined rule-based intent detection, a language model and the Parlant framework. Analyses written at the time recorded responses being truncated to short phrases and concluded that Parlant added limited value over calling the model directly.

The last snapshot (2026-01-16) adds a function-calling orchestrator with four tools and a compliance service. This agent was **never connected to the interface**, so it stayed a prototype. Then the team decided to close the project, before launch.

## October and November 2026: reopening and publication

Everything after the `history-import` tag: removing unsafe endpoints, fixing bugs, adding mocks and tests. None of it adds product features. [REOPENING.md](REOPENING.md) lists, part by part, how far each part had got and what reopening it found.
