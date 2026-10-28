# Frontend/backend integration checks - 28 October 2026

## Live endpoint inspection before the change

`https://jee-question-analyzer.onrender.com/_stcore/health` returned plain-text
`ok`. `/openapi.json` and `/health` returned Streamlit HTML rather than API JSON.
The deployment was a complete Streamlit application, not a callable backend API.

## Implemented change

- Render entry point: `api_server.py`, with FastAPI and one in-memory job worker.
- Authenticated submission/polling endpoints with a bounded queue.
- Streamlit server-side client selected by `JEE_API_URL`.
- Matching `JEE_API_TOKEN` required on both services; Groq/Tavily remain backend-only.
- Original local execution preserved when no API URL is configured.
- No automatic retry of an uncertain job submission.

## Actual verification

| Check | Outcome |
|---|---|
| Windows offline regression suite | 50 tests passed |
| Clean Linux locked dependency build | Passed on Python 3.12.14 |
| Linux offline regression suite | 50 tests passed |
| Render API Blueprint schema | Valid against Render's published JSON Schema |
| Linux HTTP API in a 512 MB container | JSON health and OpenAPI routes passed; unauthenticated submission returned 401 |
| In-process frontend/client/backend integration | Passed with a mocked workflow result; no external API request |
| Existing model/calculation regression tests | Passed in the same suite |

Tests cover unauthorized access, missing backend token, invalid inputs, unknown
jobs, queue capacity, invalid backend results, HTML mistaken for an API, network
timeouts, bounded polling, secret-safe errors and frontend API routing.

No new paid model requests were made for these integration checks. They do not
establish live cloud-to-cloud solving: the owner must change Render's service
settings and set the same private token in both hosts before that can be tested.

## Operational boundaries

Jobs and results are in memory, expire after 30 minutes once finished, and are
lost on restart. Run one API process/instance. At most three jobs can be active
or queued, with one executing at a time. The frontend waits up to 10 minutes.
These controls do not guarantee a particular Groq TPM quota or production SLA.
