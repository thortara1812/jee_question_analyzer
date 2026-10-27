"""Deterministic tool benchmark by default. --live explicitly spends API credits."""
import argparse
import json
import math
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from agentic_jee_system.tools.science import science
from agentic_jee_system.backend import CrewBackend
from agentic_jee_system.workflow import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case", help="Run one case ID")
    parser.add_argument("--output", default=".local/benchmark.json")
    args = parser.parse_args()
    cases = json.loads(Path(__file__).with_name("cases.json").read_text())
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
        if not cases:
            parser.error("Unknown case ID")
    if args.limit is not None:
        cases = cases[:max(0, args.limit)]
    rows = []
    for case in cases:
        if not args.live and "operation" not in case:
            continue
        started = time.perf_counter()
        row = {"id": case["id"]}
        backend = None
        try:
            if args.live:
                backend = CrewBackend()
                result = run(case["question"], subject=case["subject"], backend=backend)
                row["status"] = result.status
                row["metrics"] = result.metrics
                row["tool_successes"] = sum(call.success for call in result.tool_calls)
                row["tool_calls"] = [call.model_dump(exclude_none=True) for call in result.tool_calls]
                if "expected_status" in case:
                    row["correct"] = result.status == case["expected_status"]
                else:
                    # Deliberately simple numeric/option scorer; retain answer for human review.
                    answer = result.solution.answer if result.solution else ""
                    row["answer"] = answer
                    numbers = re.findall(r"(?<![A-Za-z])[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", answer)
                    match = any(math.isclose(float(n), case["expected"], rel_tol=1e-4, abs_tol=1e-6) for n in numbers)
                    option_ok = "option" not in case or result.solution and result.solution.option == case["option"]
                    row["correct"] = bool(result.status == "verified" and match and option_ok)
                row["false_accept"] = result.status == "verified" and not row["correct"]
            else:
                value = science(case["operation"], case["values"])[case["field"]]
                row.update(value=value, correct=math.isclose(value, case["expected"], rel_tol=1e-9), status="completed")
        except Exception:
            row.update(status="failed", correct=False)
            if backend is not None:
                row["metrics"] = backend.metrics
        row["seconds"] = time.perf_counter() - started
        rows.append(row)
    latency = sorted(row["seconds"] for row in rows)
    completed = sum(row["status"] != "failed" for row in rows)
    usage = [metric["usage"] for row in rows for metric in row.get("metrics", []) if metric.get("usage")]
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "live provider pipeline" if args.live else "deterministic formula registry only; not LLM accuracy",
        "cases": len(rows), "passed": sum(row["correct"] for row in rows), "completed": completed,
        "completion_rate": completed / len(rows) if rows else None,
        "accuracy": sum(row["correct"] for row in rows) / len(rows) if rows else None,
        "median_seconds": statistics.median(latency) if latency else None,
        "p95_seconds": latency[max(0, math.ceil(.95 * len(latency)) - 1)] if latency else None,
        "false_accept_count": sum(row.get("false_accept", False) for row in rows) if args.live else None,
        "false_accept_rate_among_verified": (sum(row.get("false_accept", False) for row in rows)
            / sum(row["status"] == "verified" for row in rows)) if args.live and any(row["status"] == "verified" for row in rows) else None,
        "rate_limit_attempts": sum(metric["status"] == "rate_limit" for row in rows for metric in row.get("metrics", [])) if args.live else None,
        "transient_attempts": sum(metric["status"] == "transient" for row in rows for metric in row.get("metrics", [])) if args.live else None,
        "provider_usage": usage or None, "cost": None,
        "limitations": "Numeric scorer requires human review for symbolic answers and units. Cost is unmeasured. Failed requests may lack provider token usage. Fact-check quality is covered by mocked control-flow tests, not this numeric benchmark.",
        "results": rows,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"{report['passed']}/{len(rows)} passed ({report['scope']}); report: {path.resolve()}")


if __name__ == "__main__":
    main()
