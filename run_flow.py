"""CLI and backwards-compatible solving entrypoint."""
import argparse
import sys
from pathlib import Path
from agentic_jee_system.workflow import run


def solve_jee_question(question: str):
    return run(question).markdown


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Solve or fact-check JEE input")
    parser.add_argument("question", nargs="?")
    parser.add_argument("--mode", choices=["solve", "fact_check"], default="solve")
    parser.add_argument("--subject", choices=["Auto", "Mathematics", "Physics", "Chemistry"], default="Auto")
    parser.add_argument("--output", help="Optional JSON result path; may contain question data")
    args = parser.parse_args()
    try:
        result = run(args.question or input("Enter JEE input: "), args.mode, args.subject)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(result.markdown)
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")
