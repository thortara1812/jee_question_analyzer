# Validation evidence — 27 October 2026

## Baseline

No tests or benchmark were present. The original .venv could not start because
it referenced an inaccessible Microsoft Store interpreter. The default Python
alias also failed. No pre-change API accuracy or latency score is available.
The audit and baseline limitations are recorded in `AUDIT.md`.

## Current observed results

| Check | Observed outcome | Scope |
|---|---|---|
| Locked installation | 164 packages installed in separate .venv-validation | Python 3.12.14, CrewAI 1.15.22, Streamlit 1.64.0 |
| Automated regression suite | 32 tests passed | External APIs mocked; real registered tools executed locally |
| Streamlit AppTest | Example callbacks, empty submit and rerun persistence passed | No browser screenshot or live UI provider request |
| Formula benchmark | 10/10 cases passed | Deterministic registry only; see benchmark-offline.json |
| Live Physics smoke benchmark | 1/1 case passed; verified 400 J | Real Groq calls; see benchmark-live-smoke.json |
| Live fact-check entrypoint | Inconclusive; no external evidence | Real claim-extractor call; no evidence-backed verdict tested |
| Python compilation | Passed for app, CLI, source, tests and benchmark | Syntax/import-independent compilation |

The recorded live Physics benchmark took 47.952 seconds including pacing, with
no observed rate-limit or transient failures. The solver made two successful
calculator calls. The verifier made one invalid calculation attempt and then a
successful independent call computing 400 J. The application records that failed
tool attempt rather than hiding it. The provider-reported stage token totals
were 875, 3,147 and 5,071 (9,093 total); cost is unmeasured. These figures do not
prove operation under an 8,000 TPM account limit. Stage pacing is heuristic and
bounded retries provide graceful failure, not a quota guarantee.

Benchmark invocation used JEE_ATTEMPTS=1, JEE_MIN_INTERVAL=20,
JEE_MAX_TOKENS=900, JEE_TIMEOUT=60 and the default Groq GPT-OSS model. Tests used
disabled tracing and `.local/crewai` storage. Developer console event output was
not published as a report because CrewAI includes internal prompts there.

## Defects reproduced and fixed during validation

- Original example-widget mutation was replaced by pre-widget callbacks, then
  checked with Streamlit's actual test runtime.
- Windows history connections now close explicitly. Sandboxed Windows temporary
  directories prevented SQLite tests; the suite passed outside that restriction.
- Windows console encoding errors from CrewAI event emojis were resolved for the
  CLI by configuring UTF-8. PowerShell setup instructions also set PYTHONUTF8.
- Groq rejected invented native tools named JSON/json during structured output.
  Prompt clarification alone failed. A text-tool experiment produced no actual
  calculations, and the numeric verification guard correctly withheld success.
  The final implementation registers schema submission as a real result-as-answer
  tool. It requires successful calculation before accepting numeric output.
- Submission and final verification both prevent reuse of another stage's tool
  audit. Correction attempts cannot reuse a prior attempt's successful calls.

## Boundaries of this evidence

One successful live Physics example is a smoke test, not general accuracy or
verification validation. The report's 100% and 0% false-accept values describe
only that single case. No statistical accuracy, cost or superiority claim is
justified. Full live Mathematics/Chemistry/ambiguity/MCQ benchmark execution,
adversarial verification trials and evidence-backed fact-check quality evaluation
remain unperformed. Mocked fact-check tests validate control flow and citations,
not passage entailment or real search quality.

Broader symbolic and chemistry tools, account-wide token reservations,
multi-process coordination, cross-request caching and a public-service security
review remain future work. Both workflows are implemented; only solving and
the unavailable-evidence fact-check path were exercised with real model calls.

## Reproduce

From repository-root PowerShell, after the README setup:

```powershell
$env:CREWAI_TRACING_ENABLED = 'false'
$env:OTEL_SDK_DISABLED = 'true'
$env:CREWAI_STORAGE_DIR = '.local/crewai'
$env:PYTHONUTF8 = '1'
$env:LITELLM_LOCAL_MODEL_COST_MAP = 'true'
.\.venv-validation\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-validation\Scripts\python.exe benchmarks/run_benchmark.py --output .local/benchmark.json
$env:JEE_ATTEMPTS = '1'
.\.venv-validation\Scripts\python.exe benchmarks/run_benchmark.py --live --case physics-block --output .local/physics-smoke.json
```

The last command consumes API quota. Use additional cases deliberately; do not
present this small benchmark as JEE-wide coverage.
