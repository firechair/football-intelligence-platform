# Reopening the project in 2026

The team decided to close the project in January 2026, before launch. In October and November 2026 I reopened it to publish it. Everything after the `history-import` tag comes from that work; everything before it is the history as it was, filtered for publication.

This page lists, part by part, how far each part had got and what reopening it found. Each fix has its own commit, with the explanation in the message: `git show <commit>`.

## How the problems showed up

- **Running everything from a clean clone,** with mocks in place of the paid APIs.
- **Tests written against the code as it was.** Of the 81 account tests in the project, 32 failed or errored on the first run.
- **The race detector,** on the Go receiver.
- **Watching the demo in a browser.** The accuracy page bug was invisible to every API check.
- **Reading the code against the providers' documentation,** and a review before publication.

## Prototypes, January to April 2025

**Streamlit chatbot and Flask API.** Replaced by the later services, for the reasons in [CHALLENGES.md](CHALLENGES.md). Kept as they were.

**Go push receiver.** Its last version, of 20 March 2025, was never committed: it is imported as a snapshot. In 2026 it got its first tests, 25 of them, run with the race detector (`cfd72d9`).

| Problem | Commit |
|---|---|
| Files received or queued in the same millisecond overwrote each other: in a test, 4 of 50 queued updates survived | `e7ec731` |
| The retry backoff was computed but never waited for, so ten retries ran out in under a minute | `c33034d` |
| The autosave read the outcome maps without the lock while pushes wrote to them, which can stop the process | `e85a34f` |
| After a restart, deleted outcomes came back and released offers became pending again | `f53015a` |
| A push whose offers all came from untracked bookmakers was dropped with its outcomes, so later offers for those outcomes could never be placed | `9def8e1` |
| An offer that arrived before its outcome was dropped unless it had a coupon key; once released, it was filed under the coupon's slug instead of the provider's event ID | `0bf882b` |
| An unreadable start date made every offer live. The first version checked the error; the second dropped the check | `f51b274` |

## Data collection, `ingestion/`, September to December 2025

**State in January 2026.** Deployed, with the scheduler collecting fixtures, predictions and odds. Accuracy evaluation had been added in November.

| Problem | Commit |
|---|---|
| Admin and debug endpoints had no authentication: job triggers, migrations, table recreation, user listing and bulk deletion | `eb1cd6b` |
| Concurrent requests to the provider started in bursts: the spacing check was not atomic | `3ae8990` |
| Under/over predictions could never score as correct, and win-or-draw ones counted any decisive result as correct, whichever team was predicted | `1171535` |
| The collect-and-evaluate route imported a class that does not exist, so it always failed; three stub routes reported success without doing anything | `f53acb3` |
| The live fixtures endpoint did not read its API key and URL from settings | `f3e7d65` |
| Migrations failed on a clean database | `43e6181` |
| Accuracy results and the summary returned nothing on a migrated database | `b9813ab` |
| Undefined names in fixture conversion and prediction cleanup | `b295c12` |

## Accounts, analytics and chat, `platform/`, August 2025 to January 2026

**State in January 2026.** Accounts with 2FA, intent detection plus an LLM behind the chat in the interface, alerts and bookmaker analytics. The function-calling agent was a prototype, never connected to the interface.

| Problem | Commit |
|---|---|
| Token refresh imported a library that was not installed | `95b517b` |
| Profile and 2FA changes were never saved | `c5261f7` |
| 2FA codes were always rejected | `2b3e825` |
| The service started without JWT signing keys | `292f81b` |
| Email addresses longer than the standard allows were accepted | `571b88c` |
| 32 inherited account tests no longer matched the code | `eb9ccad` |
| The compliance filter made harmful replies worse, a message about suicide received only gambling numbers, and ordinary words triggered it | `0ab977f`, `ecc69d5` |
| Intent detection read the plural "quote" as a team name | `27f1264` |
| The Redis cache awaited a synchronous client, so it did nothing once Redis was connected | `bf6f9d9` |
| Rankings and best odds returned hardcoded or invented data | `0d81607` |
| The ranking calculation multiplied a Decimal by a float and always failed | `9051919` |
| Two named bookmakers always received a "special" alert from sample data | `dd3f2e6` |
| Cache and alert triggers needed no login | `12656a1` |
| The registration rate limit was commented out, and a debug route was open | `e5938c8` |

## Accuracy page, `web/`, November to December 2025

**State in January 2026.** The frontend had about 20 pages, some with placeholder data. Only the accuracy page is published here.

| Problem | Commit |
|---|---|
| A win-or-draw prediction showed only the team, so a draw scored as correct looked like an error | `b5eeb64` |
| If the page was opened before any data arrived, it stayed at zero: the web server kept its first answer | `78eb087` |

## Also added in 2026

- **Mocks of the football API and of the LLM** (`6c20f24`, `479da2e`) and a Docker Compose file (`ecdf2d3`), so that everything runs without keys.
- **Tests and CI** (`a06868f`).
- **Code cleanup:** logging in place of print, dead code and unused imports removed, return types added.
- **Stubs removed** rather than left looking finished: value bet detection (`c635d24`).

## Not fixed

The limits of the services are listed in [ARCHITECTURE.md](ARCHITECTURE.md#known-limits). For the Go receiver:

- Offers waiting for an outcome never expire.
- An event built from a coupon key gets the current time as its start, so its offers are usually stored as live.
- Team names taken from coupon keys come out in capitals.
- The XML in a multipart body ends at the first `--`.
- The DynamoDB storage has no tests, because they would need AWS.
