"""Student-facing math formatting without changing numerical results."""
import re

_ARROW = r"(?:\\(?:Rightarrow|Longrightarrow|implies|rightarrow)\b|⇒|→|⟹)"
_MATH = re.compile(r"(\$\$.*?\$\$|\$[^\n$]*\$)", re.DOTALL)
# Cover common unwrapped commands, including nested fraction arguments.
_GROUP = r"\{(?:[^{}]|\{[^{}]*\})*\}"
_COMMAND = re.compile(r"\\[A-Za-z]+(?:\s*" + _GROUP + r")*")
_SPACING = r"\\(?:[;,! ]|quad\b|qquad\b)"


def student_text(text: str) -> str:
    """Normalize math delimiters and render stray commands instead of exposing TeX."""
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.DOTALL)
    parts = _MATH.split(text)
    for index, part in enumerate(parts):
        if part.startswith("$"):
            # Preserve existing math, separating chained equations without arrows.
            delimiter = "$$" if part.startswith("$$") else "$"
            body = part[len(delimiter):-len(delimiter)]
            # TeX spacing next to an arrow must not leave a dangling backslash
            # when the arrow is replaced with separate equations.
            if re.search(_ARROW, body):
                body = re.sub(_SPACING, " ", body)
            equations = re.split(r"\s*;?\s*" + _ARROW + r"\s*;?\s*", body)
            equations = [equation.strip().strip(" ;") for equation in equations]
            parts[index] = "\n\n".join(
                ("$$\n" + equation.strip(" ;") + "\n$$" if delimiter == "$$" else
                 "$" + equation.strip(" ;") + "$")
                for equation in equations if equation.strip(" ;"))
        else:
            # Spacing commands outside equations are layout, not standalone math.
            part = re.sub(_SPACING, " ", part)
            part = re.sub(r"\s*;?\s*" + _ARROW + r"\s*;?\s*", "\n\n", part)
            parts[index] = _COMMAND.sub(lambda match: "$" + match.group() + "$", part)
    result = "".join(parts)
    # Streamlit requires display delimiters on their own lines. Separate adjacent
    # blocks so inline spacing cannot produce $$$ sequences and KaTeX errors.
    result = re.sub(r"(?<!\$)\$\$\s*\$\$(?!\$)", "$$\n\n$$", result)
    return result


def formula_block(formula: str) -> str:
    """Show the governing equation, rather than a whole derivation in the formula line."""
    formula = re.split(_ARROW, formula, maxsplit=1)[0].strip(" ;\n")
    formula = formula.removeprefix("$$").removesuffix("$$").strip("$")
    formula = re.sub(r"^\\[\[(]|\\[\])]$", "", formula).strip(" ;\n")
    return "\n\n".join("$$\n" + equation.strip() + "\n$$" for equation in formula.split(";") if equation.strip())


def presentation_blocks(text: str):
    """Render display math separately so a stray delimiter cannot swallow prose.

    Standalone equations are recognized even when model delimiters are missing.
    Inline math stays in Markdown; no model call or answer substitution is used.
    """
    text = re.sub(r"\\\[(.*?)\\\]", r"\n$$\n\1\n$$\n", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.DOTALL)
    text = text.replace("$$", "\n$$\n")
    pending = []
    def flush():
        if pending:
            value = "\n".join(pending).strip()
            pending.clear()
            if value:
                return ("markdown", value)
        return None
    for line in text.splitlines():
        value = line.strip()
        if value == "$$":
            block = flush()
            if block:
                yield block
            continue
        # Prose headings and explanatory sentences must never enter st.latex.
        prose = bool(re.match(r"(?:\d+[.)]\s+|\*\*|#{1,6}\s)", value))
        plain_words = re.findall(r"\b[A-Za-z]{3,}\b", re.sub(r"\\[A-Za-z]+|\\text\{[^}]*\}", "", value))
        equation = ("=" in value and not prose and len(plain_words) <= 2)
        if equation:
            block = flush()
            if block:
                yield block
            value = value.replace("$", "")
            value = re.sub(_SPACING, " ", value)
            for equation in re.split(_ARROW, value):
                equation = equation.strip(" ;$")
                if equation:
                    yield ("latex", equation)
        else:
            pending.append(line)
    block = flush()
    if block:
        yield block
