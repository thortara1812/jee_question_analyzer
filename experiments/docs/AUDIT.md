# Repository audit — 27 October 2026

Baseline: `app.py` calls `run_flow.py`, which loads the JSON declaration in
`src/agentic_jee_system/flow.json`. Four sequential individual agents perform
analysis, solving, verification and composition. No crews or tools are present.

## Confirmed findings

1. The description advertises fact checking, but the declaration contains only
   four solving methods. There is no claim extractor, retrieval or router.
2. All four agents use unbounded string-model configuration, extensive repeated
   prompts and verbose execution. Composition costs another model call.
3. No calculation tools, validated stage schemas, correction controller, history,
   tests or benchmark exist. Verification is a prompt, not an accuracy guarantee.
4. Example buttons assign to `question` after its widget is instantiated, which
   Streamlit prohibits. Raw exceptions expose internal diagnostics to students.
5. README references a nonexistent `flow.yaml`. The actual file is `flow.json`.
6. Both entrypoint and sitecustomize globally monkey-patch CrewAI cache behavior.
7. The existing .venv points to an inaccessible Microsoft Store interpreter.
   Neither its Python nor the default Python alias starts in this environment.

## Baseline evidence and risks

No existing tests were found. A live baseline cannot be reported: the local
interpreter fails before application import. The user's earlier 400 J example is
historical evidence only. No API calls or secrets were inspected during audit.
Groq TPM behavior, model availability, real tool invocation and retrieval quality
require separate credentialed integration evaluation. No numerical accuracy score
can be inferred from prompts or mocked tests.

## Ordered implementation

1. Preserve the existing declaration and user changes; introduce a Python
   orchestration entrypoint with deterministic composition and bounded calls.
2. Validate analysis, solution, verification and evidence; stop on ambiguity and
   allow one correction followed by independent re-verification.
3. Register a constrained arithmetic calculator with solver and verifier.
4. Add explicit fact-check mode with real optional Tavily retrieval and citation
   validation; unavailable retrieval must return inconclusive.
5. Replace broken widget handling, add mode/subject controls and local history.
6. Add offline regression fixtures, reproducible reports and Windows instructions.

Symbolic algebra, broader domain tools and measured live benchmark results remain
separate work until implemented and verified. Do not claim production readiness.
