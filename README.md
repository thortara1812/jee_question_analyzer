# Agentic JEE Assistant

A CrewAI-based application for Mathematics, Physics and Chemistry questions,
with a separate educational fact-checking mode.

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
pyproject.toml             Dependencies and project configuration
uv.lock                    Reproducible dependency versions
.env                       Local API credentials (never share)
.env.example               Configuration template
src/agentic_jee_system/
  workflow.py              Routing, reasoning stages and verification gates
  backend.py               CrewAI agents and model configuration
  schemas.py               Validated stage outputs
  reliability.py           API retries and error handling
  evidence.py              Optional external evidence retrieval
  history.py               Optional local request history
  presentation.py          Readable equations and student-facing formatting
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
