# Agentic JEE Assistant

A CrewAI-based application for Mathematics, Physics and Chemistry questions,
with a separate educational fact-checking mode.

## Deploy

[Deploy to Render](https://render.com/deploy?repo=https://github.com/thortara1812/jee_question_analyzer)

Render is configured to host the HTTP backend. For Streamlit Community Cloud, select repository
`thortara1812/jee_question_analyzer`, branch `main`, entrypoint `app.py`, and
Python 3.12. Use `.streamlit/secrets.toml.example` as the cloud-secret template.
Set the same private `JEE_API_TOKEN` on both hosts. Groq and optional Tavily keys
belong on Render. Streamlit submits a job to the backend and polls for the result.
See [the deployment guide](experiments/deployment/DEPLOYMENT.md) for both hosts.
Never upload `.env` or a populated `.streamlit/secrets.toml` to GitHub.

Cloud history is private to the browser session and disappears when the session
ends. `JEE_HISTORY_MODE=local` explicitly enables the old SQLite history for a
single-user local installation; do not use shared local history on a public app.

The Render start command is `.venv/bin/python api_server.py`, with health path
`/health`. A service still starting `streamlit run app.py` serves a webpage,
not the backend API. Update an existing manually configured service accordingly.

## Frontend/backend connection

```text
Student browser -> Streamlit frontend -> authenticated Render HTTP API
                                          -> queued CrewAI workflow and tools
```

On Streamlit, configure `JEE_API_URL=https://jee-question-analyzer.onrender.com`
and `JEE_API_TOKEN` in Secrets. The token is sent only by the Streamlit server,
never by browser JavaScript. Leave `JEE_API_URL` unset to preserve the local,
in-process workflow. Never set it on Render: Render executes workflows directly.

API routes are `GET /health`, authenticated `POST /api/v1/jobs`, authenticated
`GET /api/v1/jobs/{job_id}`, and authenticated `GET /api/v1/queue` for counts only.
API documentation is available at `/docs`.
The backend runs one worker with at most three active/queued jobs, returns 429
when full, and retains up to 100 job records for 30 minutes after completion.
Jobs are in memory and are lost on a Render restart or redeployment; do not run
multiple API processes or instances with this in-memory implementation. The
frontend never automatically resubmits an uncertain POST, avoiding duplicate
expensive agent runs. It polls for up to 10 minutes and reports timeout/failure
instead of showing an endless spinner. The frontend retains a request identifier
and job ID in its browser session: retrying an unfinished question resumes the
existing job. If the submission response was lost, the same Idempotency-Key lets
the updated backend return that job instead of creating another one.

Production workflows run in a disposable child process with a default 300-second
execution deadline (`JEE_JOB_TIMEOUT_SECONDS`, configurable from 30 to 600).
Timed-out processes are stopped before the queue slot is released, so a stuck
worker cannot occupy it indefinitely. The existing pacing interval also applies
between completed jobs. Existing Groq limits still apply. A full queue can still
occur legitimately when three different requests are outstanding.

## Run on Windows

From this folder in PowerShell:

```powershell
uv sync --frozen --python 3.12
# Only when setting up a new machine without an existing .env:
Copy-Item .env.example .env
# Edit .env and provide your own GROQ_API_KEY.
$env:PYTHONUTF8 = '1'
uv run --frozen streamlit run app.py
```

On the existing validated local environment:

```powershell
.\.venv-validation\Scripts\python.exe -m streamlit run app.py
```

Do not overwrite an already configured `.env`. Tavily is optional and requires
`TAVILY_API_KEY`. Without external evidence, fact-checking returns inconclusive.

## Active project files

```text
app.py                     Streamlit interface
run_flow.py                Command-line interface
api_server.py              Render HTTP backend entrypoint
pyproject.toml             Dependencies and project configuration
uv.lock                    Reproducible dependency versions
.env                       Local API credentials (never share)
.env.example               Configuration template
src/agentic_jee_system/
  workflow.py              Routing, reasoning stages and verification gates
  backend.py               CrewAI agents and model configuration
  groq_llm.py              Scoped Groq request compatibility adapter
  schemas.py               Validated stage outputs
  reliability.py           API retries and error handling
  evidence.py              Optional external evidence retrieval
  history.py               Optional local request history
  presentation.py          Readable equations and student-facing formatting
  api.py / api_jobs.py     Authenticated HTTP endpoints and bounded worker queue
  api_client.py            Streamlit server-to-server submission and polling
  api_contracts.py         Shared validated HTTP request/response schemas
  tools/                   Calculators and structured-result submission
experiments/               Tests, evaluation, reports and legacy material
```

The normal solving pipeline uses three roles: analyzer, solver and verifier.
One rejected solution may receive one correction and a fresh verification.
Python formats the final response. Fact-checking has two separate agent roles.
Verification is an additional review, not a guarantee of accuracy.

## Optional development material

Tests, benchmarks, audit reports, assistant notes, historical documentation and
the original codeless Flow are preserved in `experiments/`. They are not needed
to start the upgraded Streamlit application. See
[experiments/README.md](experiments/README.md) for their locations and commands.

The legacy `crewai run` definition is now
`experiments/legacy/flow.json`; the project configuration points to its new path.
It remains separate from the upgraded Python workflow used by `app.py`.

Environment, cache and Git folders remain in their original locations to avoid
breaking installed tools. On this Windows checkout they are marked Hidden for a
cleaner Explorer view. Enable **View > Show > Hidden items** to see them. Hidden
attributes are cosmetic, local to this checkout, and are not a security measure.
Runtime caches can be recreated automatically.

## Checks

```powershell
.\.venv-validation\Scripts\python.exe -m unittest discover -s experiments/tests -v
.\.venv-validation\Scripts\python.exe experiments/benchmarks/run_benchmark.py
```

On a new machine, prefix those commands with `uv run --frozen python` instead of
the local validation-environment executable. Routine tests mock external APIs;
benchmark execution uses deterministic calculations unless `--live` is supplied.
