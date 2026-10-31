# Engineering notes from September 2025

Working notes from a debugging session on the ingestion service, kept as they were written, in Italian. They had been deleted from the project and are restored here unchanged, apart from the redactions applied to the whole repository. You can find their original commits with `git log --all -- ingestion/docs/`.

| File | What it is |
|---|---|
| [TEST_RESULTS.md](TEST_RESULTS.md) | A local test run, with table counts and a bug being narrowed down. |
| [FIX_REPORT.md](FIX_REPORT.md) | The problems that run exposed, their causes and the fixes. |
| [PERFORMANCE_OPTIMIZATIONS.md](PERFORMANCE_OPTIMIZATIONS.md) | The caching and indexing plan that followed. |

Read them as history, not as documentation of the current code:

- The figures under "Performance Attese" in PERFORMANCE_OPTIMIZATIONS.md are expected values, not measurements.
- They mention endpoints and files that are not in this repository, such as `/admin/cache/*` and `database_indexes.sql`.
