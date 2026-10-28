# Optional development and legacy material

These files are preserved for review and reproducibility. The upgraded application
does not import this directory during normal solving or fact-checking.

| Folder or file | Contents |
|---|---|
| `tests/` | Automated workflow, calculation, formatting and Streamlit regression tests |
| `benchmarks/` | Deterministic calculation fixtures and optional live benchmark runner |
| `docs/` | Audit, validation evidence and recorded benchmark results |
| `legacy/flow.json` | Original declarative codeless Flow, preserving existing local edits |
| `legacy/sitecustomize.py` | Former startup hook; already a no-op before relocation |
| `legacy/placeholders/` | Unused original crews, knowledge and skills directory placeholders |
| `assistant-notes/` | Coding-assistant instruction files; not application runtime modules |
| `artifacts/` | Previously generated outputs, when present |
| `previous_README.md` | Earlier detailed documentation, with references updated for this layout |
| `relocation-manifest.json` | SHA-256 hashes and original locations recorded before moving files |

Run these commands from the **project root**, not from this directory:

```powershell
.\.venv-validation\Scripts\python.exe -m unittest discover -s experiments/tests -v
.\.venv-validation\Scripts\python.exe experiments/benchmarks/run_benchmark.py --output .local/benchmark.json
```

For a fresh environment, use `uv run --frozen python` in place of the validation
environment's executable. Live benchmarks consume API quota and require a valid
provider configuration. Historical reports describe the state when recorded;
paths shown as historical audit evidence may refer to the earlier layout.

No API credentials, Git database, installed virtual environment or live history
database was moved here. Existing user edits in the legacy Flow were preserved.
