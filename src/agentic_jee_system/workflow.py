"""Explicit orchestration with validated handoffs and at most one correction."""
import re
from .backend import CrewBackend
from .evidence import authoritative, retrieve
from .schemas import Analysis, Claims, FactVerdict, Result, Solution, Verification
from .reliability import ServiceError
from .presentation import formula_block, student_text


def validate_input(text: str) -> str:
    if not isinstance(text, str) or not 3 <= len(text.strip()) <= 4000:
        raise ValueError("Enter between 3 and 4,000 characters.")
    if any(ord(char) < 32 and char not in "\n\t\r" for char in text):
        raise ValueError("Input contains unsupported control characters.")
    return text.strip()


def compose(analysis: Analysis, solution: Solution, verification: Verification) -> str:
    """Formatting cannot upgrade a rejected answer into a verified answer."""
    intro = f"**{analysis.subject} · {analysis.topic}**\n\n"
    checks = "\n".join(f"- {student_text(check)}" for check in verification.checks)
    notes = list(analysis.assumptions)
    if analysis.ambiguities:
        notes = ["This answer is conditional on the assumptions below; the original question is incomplete or ambiguous."] + notes
        notes += ["Original uncertainty: " + item for item in analysis.ambiguities]
    assumptions_text = ("\n\n**Assumptions used**\n\n" + "\n".join(
        f"- {student_text(item)}" for item in notes)) if notes else ""
    if verification.verdict != "verified" or verification.errors or solution.limitations:
        issues = verification.errors + solution.limitations
        return (intro + "**Verification: needs review — no confirmed answer.**\n\n"
                + "\n".join(f"- {item}" for item in issues) + "\n\n" + verification.correction + assumptions_text)
    steps = "\n\n".join(f"**Step {i}**\n\n{student_text(step)}" for i, step in enumerate(solution.steps, 1))
    option = solution.option or ("No provided option matches." if analysis.options else "Not applicable")
    option_text = f"\n\n**Option:** {option}" if analysis.options else ""
    return (intro + f"**Equation to use**\n\n{formula_block(solution.formula)}\n\n{steps}\n\n"
            + f"**Final answer:** {student_text(solution.answer)}{option_text}\n\n"
            + f"**Verification: {'verified under stated assumptions' if analysis.ambiguities else 'verified'}**\n\n{checks}"
            + assumptions_text)


def run(text: str, mode: str = "solve", subject: str = "Auto", *, backend=None, search=None) -> Result:
    """Execute one workflow; dependencies are injectable for offline tests."""
    text = validate_input(text)
    if mode not in ("solve", "fact_check"):
        raise ValueError("Choose solve or fact_check.")
    if subject not in ("Auto", "Mathematics", "Physics", "Chemistry"):
        raise ValueError("Unknown subject selection.")
    backend = backend or CrewBackend()

    def finish(status, markdown, evidence=None, **stages):
        return Result(mode=mode, status=status, markdown=markdown,
                      evidence=evidence or [], tool_calls=backend.tool_calls, metrics=backend.metrics, **stages)

    if mode == "fact_check":
        claims = backend.ask("JEE Claim Extractor", "Extract up to five independently checkable claims. Preserve qualifications.",
                             {"input": text}, Claims)
        try:
            evidence = (search or retrieve)(claims.claims)
        except ServiceError:
            return finish("inconclusive", "**Inconclusive.** External evidence retrieval failed. Please retry later.")
        if not evidence:
            return finish("inconclusive", "**Inconclusive.** No external evidence was retrieved. Configure Tavily or retry search.")
        verdict = backend.ask("Official Educational Fact Checker",
            "Compare every claim with supplied evidence only. Prefer official sources. Explain conflicts, dates and missing coverage. "
            "Return inconclusive for insufficient or conflicting evidence. Cite only supplied URLs supporting the explanation.",
            {"claims": claims.claims, "evidence": [dict(item.model_dump(mode="json"),
             authoritative=authoritative(str(item.url))) for item in evidence]}, FactVerdict)
        allowed = {str(item.url).rstrip("/") for item in evidence}
        prose_urls = re.findall(r"https?://[^\s<>\[\]()]+", verdict.explanation)
        if (any(str(url).rstrip("/") not in allowed for url in verdict.citations)
                or any(url.rstrip(".,;/") not in allowed for url in prose_urls)
                or verdict.verdict != "inconclusive" and not verdict.citations):
            return finish("inconclusive", "**Inconclusive.** The proposed citations failed validation.", evidence)
        citations = "\n".join(f"- [{url}]({url})" for url in verdict.citations)
        return finish(verdict.verdict, f"**{verdict.verdict.capitalize()}**\n\n{verdict.explanation}\n\n{citations}", evidence)

    analysis = backend.ask("JEE Question Analysis Specialist",
        "Extract subject, topic, given values with units, unknowns, assumptions, options and a concise approach. "
        "Set calculation_required when numerical computation is needed. Do not solve. "
        "Flag ambiguity, missing essential data and contradictions. Continue by choosing reasonable JEE defaults and "
        "record EVERY assumed value or statement explicitly in assumptions, with units and a brief reason. "
        "Never put assumed values in given or present them as supplied facts. Preserve all explicit givens. "
        "Use conventional defaults where appropriate (g=9.8 m/s^2, ideal components, negligible air resistance). "
        "For missing mass, speed or other quantities without a standard default, choose a simple physically valid "
        "illustrative value, clearly label it illustrative, and plan a general symbolic answer as well. "
        "For ambiguous interpretations, select and document one interpretation. Do not request clarification "
        "instead of solving. Use Unknown only when the input contains no identifiable Math, Physics or Chemistry problem.",
        {"question": text, "subject_hint": subject}, Analysis)
    if analysis.subject == "Unknown":
        return finish("needs_review", "**Clarification needed.**\n\n" + "\n".join(
            analysis.ambiguities or ["Please provide a clear JEE question."]))
    payload = {"question": text, "analysis": analysis.model_dump()}
    solve_instruction = (
        "Proceed using the analysis assumptions despite missing data or ambiguity. Use exactly those assumed "
        "values and interpretations; do not introduce unrecorded defaults. State the general symbolic result "
        "as well when an illustrative numeric value was assumed. An explicitly resolved ambiguity is not a "
        "limitation requiring clarification. Keep genuine calculation errors or unresolved contradictions as limitations. "
        "Solve using the appropriate method and concise derivation. Use bounded_calculator for numerical substitutions. "
        "Check units and compare all MCQ options; use null if none match. Mark missing facts as limitations. "
        "Write for a student: explain each operation in a short plain-English sentence, then show its equation on a separate line. "
        "For example: 'Subtract 5 from both sides.\n\n$$2x = 15 - 5 = 10$$'. "
        "For Physics, explain what each formula finds and include units at each substitution. "
        "The formula field must contain only the governing equation(s), not the full working. "
        "Never use arrows, Rightarrow, therefore symbols or semicolon-separated derivation chains. "
        "Always enclose LaTeX in $...$ inline or $$...$$ on separate lines. Do not assign a verification verdict.")
    verify_instruction = (
        "Verify the candidate conditionally under the exact assumptions in the analysis. Missing original values "
        "are acceptable when explicitly assumed; do not reject solely because the original question was incomplete. "
        "Reject assumptions that contradict explicit givens, hidden assumptions, or invalid mathematics. "
        "Independently check the original problem and candidate: equations, assumptions, signs, units, boundaries and MCQ match. "
        "Recalculate numerical results with bounded_calculator, preferably another path. Reject errors with specific correction instructions. "
        "Do not mark unsupported answers verified. A correct calculation with no matching option is allowed; a wrong selected option is not.")
    solver_start = len(backend.tool_calls)
    solution = backend.ask("Expert JEE Solver", solve_instruction, payload, Solution, tools=True)
    verifier_start = len(backend.tool_calls)
    verification = backend.ask("Senior JEE Solution Verifier", verify_instruction,
                               {**payload, "solution": solution.model_dump()}, Verification, tools=True)
    if verification.verdict == "rejected":
        solver_start = len(backend.tool_calls)
        solution = backend.ask("Expert JEE Solver", solve_instruction,
                               {**payload, "candidate": solution.model_dump(), "feedback": verification.model_dump()}, Solution, tools=True)
        verifier_start = len(backend.tool_calls)
        verification = backend.ask("Senior JEE Solution Verifier", verify_instruction,
                                   {**payload, "solution": solution.model_dump()}, Verification, tools=True)
    if analysis.calculation_required:
        missing = [stage for stage, calls in (
            ("Expert JEE Solver", backend.tool_calls[solver_start:verifier_start]),
            ("Senior JEE Solution Verifier", backend.tool_calls[verifier_start:]))
            if not any(call.get("stage") == stage and call.get("success") for call in calls)]
        if missing:
            verification = Verification(verdict="needs_review", checks=["Computational tool audit"],
                errors=["Missing successful independent calculation: " + ", ".join(missing)],
                correction="Retry with successful solver and verifier tool calculations.")
    if solution.option is not None and solution.option not in analysis.options:
        verification = Verification(verdict="needs_review", checks=["Option label validation"],
                                    errors=["Selected option is not in the supplied options."], correction="Check the options.")
    status = verification.verdict
    if verification.errors or solution.limitations:
        status = "needs_review"
    return finish(status, compose(analysis, solution, verification),
                  analysis=analysis, solution=solution, verification=verification)
