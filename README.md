# Agentic AI-Based JEE Assistant

A CrewAI-based JEE solving and educational fact-checking application. Python
controls validation, handoffs, bounded correction and final formatting; agents
perform analysis, solving and independent review. This is an academic project,
not a demonstrated production service or a guarantee of correct answers.

## Current architecture

```text
Streamlit / CLI → validate input → workflow router
  solve: analyzer → solver + tools → independent verifier + tools
             rejected → one correction → independent re-verification
             verified → deterministic Markdown response
             ambiguity / unverified → clarification or review message
  fact_check: claim extractor → Tavily evidence → evidence comparison
             citation allowlist validation → verdict + retrieved passages
```

The application uses `src/agentic_jee_system/workflow.py` as its explicit
orchestration layer. Each agent response is validated with Pydantic before the
next stage. Numeric verification requires successful tool calls from both the
latest solver and verifier attempts. A verifier is still an LLM: tool use alone
does not prove it used the right formula or inputs.

The existing `src/agentic_jee_system/flow.json` is retained as the **legacy**
declaration, including your pre-existing changes. `crewai run` still selects that
legacy flow. Use the commands below for the upgraded application. The legacy
flow does not have the new schemas, tools, routing or rate-limit controls.

## Windows PowerShell setup

Install Python 3.11 or 3.12 and uv, then run from the repository root:

```powershell
uv sync --frozen --python 3.12
# Only if you do not already have a configured .env:
Copy-Item .env.example .env
# Edit .env locally. Never paste or commit API keys.
$env:PYTHONUTF8 = '1'
uv run --frozen streamlit run app.py
```

If an existing `.venv` points to a removed/inaccessible Microsoft Store Python,
keep it and select a fresh environment:

```powershell
$env:UV_PROJECT_ENVIRONMENT = '.venv-validation'
uv sync --frozen --python 3.12
uv run --frozen streamlit run app.py
```

The validation environment created during this upgrade uses the available bundled
Python runtime. Your original `.venv` has been preserved. You can run the installed
validation environment directly:

```powershell
.\.venv-validation\Scripts\python.exe -m streamlit run app.py
.\.venv-validation\Scripts\python.exe run_flow.py 'Solve 2x + 5 = 15.'
.\.venv-validation\Scripts\python.exe run_flow.py --mode fact_check 'For constant mass, net force equals mass times acceleration.'
```

## Configuration

`.env.example` documents the settings. `GROQ_API_KEY` is required for the default
`groq/openai/gpt-oss-120b` model. `JEE_MODEL` selects another CrewAI-compatible
provider/model; supply that provider's credentials in its normal environment
variables. `TAVILY_API_KEY` is optional. Without retrieved evidence, fact checking
returns **inconclusive** and never claims it searched or verified sources.

`JEE_MAX_TOKENS` defaults to 900 per model response, `JEE_TIMEOUT` to 60 seconds
per request/agent execution, `JEE_ATTEMPTS` to 3, and `JEE_MIN_INTERVAL` to 20
seconds between stage attempts in one process. Tool reasoning is bounded to four
agent iterations. Authentication and invalid-request failures are not retried.
Transient failures and 429s receive bounded backoff; Retry-After up to 60 seconds
is honored, and longer cooldowns return a retry-later error. Provider failures
are sanitized in the application. Provider/library console logs are developer
output and should not be shared publicly without review.

Stage spacing is a conservative heuristic, **not** a guaranteed TPM reservation.
Tool calls can cause multiple model requests inside a stage. Quotas are shared
across account clients, and multiple application processes are not coordinated.
Reduce budgets or increase pacing to fit your actual quota. Changing API keys
does not establish a larger quota. There is no extra composer model request.
Solver and verifier tool caches are disabled, so each stage must execute its own
calculations. A registered `JSON` submission tool validates the final schema and
requires a calculation before accepting a numeric result. This also avoids the
observed Groq unknown-tool error when the model submitted JSON as a function.
Request-level timings, attempt categories and provider-reported usage (when
available) are returned in `Result.metrics`; missing token usage and cost are
not reported as zero.

## Computational scope

Registered CrewAI tools execute real Python calculations:

- Bounded arithmetic: numbers, parentheses, `+ - * / **`; no eval, function calls,
  imports, names or attributes. Node count, input length and powers are bounded.
- Mathematics: linear equations of the form `a*x+b=c` with nonzero `a`.
- Physics: kinetic energy, constant-force frictionless motion, centripetal
  acceleration, and km/h to m/s conversion.
- Chemistry: moles from supplied mass and molar mass, molarity and ideal-gas moles.

Tools validate exact parameter names, ranges and basic physical constraints.
SI units are required except explicitly named gram/liter fields. General symbolic
calculus, matrices, chemical balancing, periodic-table molar masses, limiting
reagents and a full dimensional-analysis engine are **not implemented**. Agents
may reason about other JEE topics, but these tools do not establish that coverage.

## Evidence and privacy

Tavily passages, titles and URLs are retained. Official educational hosts are
ranked first, and agent verdicts may cite only retrieved URLs. This prevents
invented URL references but does not prove a passage entails a claim. Source
quality, coverage, dates and conflicts still require human review. Search failure
returns inconclusive. No raw page URL from the model is fetched by this project.

Local history is opt-in in the UI. It stores up to 100 questions/results in
`.local/history.sqlite3`, displays the most recent 20, and can be cleared from the
sidebar. SQLite is not encrypted. No expensive request runs merely because a
widget reruns. There is no cross-user response cache; persistent history is not
used as a reasoning cache. No file-upload feature is enabled.

## Tests and evaluation

```powershell
$env:CREWAI_TRACING_ENABLED = 'false'
$env:OTEL_SDK_DISABLED = 'true'
$env:CREWAI_STORAGE_DIR = '.local/crewai'
$env:PYTHONUTF8 = '1'
.\.venv-validation\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-validation\Scripts\python.exe benchmarks/run_benchmark.py --output .local/benchmark.json
# Explicit opt-in: sends real requests and consumes your API quota.
.\.venv-validation\Scripts\python.exe benchmarks/run_benchmark.py --live --limit 1 --output .local/benchmark-live.json
# Reproduce the recorded Physics smoke case:
.\.venv-validation\Scripts\python.exe benchmarks/run_benchmark.py --live --case physics-block --output .local/physics-smoke.json
```

Offline tests mock external services. They check correction bounds, malformed
outputs, failed verification, MCQ mismatches, missing tools, ambiguity, citation
validation, rate limits, safe arithmetic, local history and Streamlit reruns.
The deterministic benchmark tests the formula registry, not the LLM's ability to
extract inputs, select methods, reason correctly or invoke tools. See
`docs/benchmark-offline.json` for the actual recorded run and `docs/VALIDATION.md`
for observed outcomes and limitations. The numeric live scorer is intentionally
simple and needs human review for units, symbolic equivalents and answer formats.
No general accuracy, false-accept rate or cost advantage has been established.

## Demonstration

1. Start Streamlit and select Physics; load the 2 kg block example and submit.
2. Inspect the concise derivation, final status and computational tool records.
3. Try an incomplete question and confirm that clarification is requested.
4. Select fact checking and enter a qualified educational claim. Inspect actual
   passages and sources, or the explicit unavailable-evidence result.
5. Enable local history if desired, rerun a widget, and confirm no duplicate call.

Audit findings and implementation scope are documented in `docs/AUDIT.md`.
Future work includes broader tools, a stronger claim-by-claim evidence evaluator,
measured live subject benchmarks, token-aware account-wide scheduling and a
security/observability review before public multi-user deployment.
