# Problems I worked through

Written in November 2026, from the code, the commit history and my notes from 2025. Where a point comes from my memory and not from the code, it says so.

## 1. Live odds in Streamlit (February to April 2025)

**The goal.** An odds table that updates while the user watches it.

**What I tried.** The attempts are still in [`prototypes/streamlit-chatbot/app.py`](../prototypes/streamlit-chatbot/app.py), commented out: 615 of its 1052 lines.

| Attempt | Where |
|---|---|
| Reload the whole page with JavaScript every 2 seconds | [`add_auto_refresh_script`](../prototypes/streamlit-chatbot/app.py#L129) |
| Run a Flask server in a background thread inside Streamlit, to receive data | [`start_flask_server`](../prototypes/streamlit-chatbot/app.py#L221) |
| Queue the odds changes, process the queue every half second and redraw placeholders | [`init_session_state`](../prototypes/streamlit-chatbot/app.py#L402), [`process_odds_changes_from_queue`](../prototypes/streamlit-chatbot/app.py#L576) |
| Generate synthetic odds changes to test the refresh | [`generate_odds_changes`](../prototypes/streamlit-chatbot/app.py#L531) |
| Stop a table cell's dialog from reopening at every rerun | [`reset_dialog_on_interaction`](../prototypes/streamlit-chatbot/app.py#L570) |

**Why it could not work.**
- Streamlit reruns the script from the top for every update.
- Fragments, `st.fragment(run_every=...)`, were available in the 1.42 release the app used. They rerun part of the page on a timer, which is still polling.
- Data that arrives in a background thread cannot reach the page by itself: it waits for the next rerun.

So the page could refresh at intervals at best, never as the data arrived.

From memory: every change in this area broke something in session state or in page refreshes, and the Streamlit documentation of the time offered no way around it. The notes I kept in March 2025 include the documentation pages on session state, reruns and fragment-scoped reruns. The snapshot has no code that uses fragments.

**What I did next.** I separated data collection from display. Collection became its own service with a scheduler ([`ingestion/`](../ingestion/), from September 2025), and the interface moved to Next.js ([`web/`](../web/), from August 2025).

**What I would do today.** Push updates from the server to the browser, with server-sent events or WebSockets. The later product planned it ([`alert_engine.py`](../platform/app/services/alert_engine.py#L317): "Trigger WebSocket notifications"), but never built it.

## 2. Providers that deliver data in different ways

**Pull.** REST APIs that you poll:
- [`prototypes/seriea-api/`](../prototypes/seriea-api/), in Flask (January 2025);
- the Streamlit prototype's integrations for injuries, line-ups and predictions;
- later, [`ingestion/`](../ingestion/) against API-Football.

**Push.** One odds provider, Enetpulse, sends XML to an HTTP endpoint that you host. Its setup instructions installed a PHP receiver. **I rewrote the receiver in Go**: [`prototypes/odds-receiver/`](../prototypes/odds-receiver/).
- **Same contract as the PHP receiver.** It keeps the paths the provider calls ([`/receive.php`, `/receive_file.php`](../prototypes/odds-receiver/internal/api/handlers.go#L69)) and its reply, [`XML_RECEIVED_OK`](../prototypes/odds-receiver/internal/api/handlers.go#L175).
- **Acknowledge first, process later,** as the provider requires. The file is saved to disk, parsed in a goroutine, and each odds update goes through a persistent queue to DynamoDB.

The receiver went through two versions in three days:

| Version | What it shows |
|---|---|
| First commit, 18 March 2025 | The structure: endpoints, queue, metrics. The models had no XML tags, so every value was read as empty. A test added in 2026, `TestReadsAttributesInTheQueryResponseFormat`, fails on that commit. |
| Working tree, 20 March 2025, never committed; imported here as a snapshot | The fix for the tags, the provider's `spocosy` format, multipart uploads, a market map built from the provider's documentation, and the outcome store. |

**Data that arrives out of order.** The feed sends outcomes and betting offers in separate pushes, and not always in order. An outcome is what is priced, such as a home win; a betting offer is one bookmaker's price for it.

The [outcome store](../prototypes/odds-receiver/internal/storage/outcome_store.go#L159) keeps an offer whose outcome has not arrived yet, and releases it when the outcome comes in.

From memory: I later wanted the Go service to become the single entry point for all incoming data. It was not built.

**What I would do today.** Validate each push against the provider's schema, keep the raw files in object storage, and replay them in tests.

## 3. Concurrent requests and provider limits (September to December 2025)

API-Football has a daily quota and a per-second limit. The collectors fetch fixtures, predictions, odds and results for many matches at the same time.

What the code does about it:
- [at most 5 simultaneous calls](../ingestion/app/utils/football_api.py#L13), plus a minimum spacing between requests;
- separate limits for predictions (3) and for [live odds](../ingestion/app/core/scheduler.py#L321) (2);
- scheduler jobs every 6 hours for fixtures and predictions, every 3 hours for odds and every 30 minutes for results;
- the [live odds monitor switched off](../ingestion/app/main.py#L117) to stay inside the daily quota.

What it got wrong:
- The spacing check was not atomic, so concurrent callers started together. This was found only in 2026, by a test that measures when requests actually start (commit `3ae8990`).
- The lock holds during the wait, so requests effectively run one per second (see [known limits](ARCHITECTURE.md#known-limits)).

**What I would do today.** A token bucket shared by all workers, for example in Redis, and a retry with backoff after a 429.

## 4. The same data from different sources

- **Team names** differ between providers: [`team_aliases.py`](../prototypes/streamlit-chatbot/src/utils/team_aliases.py) and [`normalize_team_name`](../prototypes/streamlit-chatbot/src/backend/flask_server.py#L18).
- **Market codes** differ too: the receiver translates the provider's numeric types into names ([`market_mapping.go`](../prototypes/odds-receiver/internal/processor/market_mapping.go)).
- **The schema drifted between environments:** production and the migrations disagreed (see [EVOLUTION.md](EVOLUTION.md)).

**What I would do today.** One table of teams and one of markets, each holding every provider's IDs.
