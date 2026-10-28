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
