"""Student-facing math formatting without changing numerical results."""
import re

_ARROW = r"(?:\\(?:Rightarrow|Longrightarrow|implies|rightarrow)\b|⇒|→|⟹)"
_MATH = re.compile(r"(\$\$.*?\$\$|\$[^\n$]*\$)", re.DOTALL)
# Cover common unwrapped commands, including nested fraction arguments.
_GROUP = r"\{(?:[^{}]|\{[^{}]*\})*\}"
_COMMAND = re.compile(r"\\[A-Za-z]+(?:\s*" + _GROUP + r")*")


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
            equations = re.split(r"\s*;?\s*" + _ARROW + r"\s*;?\s*", body)
            parts[index] = "\n\n".join(delimiter + equation.strip(" ;") + delimiter for equation in equations if equation.strip(" ;"))
        else:
            part = re.sub(r"\s*;?\s*" + _ARROW + r"\s*;?\s*", "\n\n", part)
            parts[index] = _COMMAND.sub(lambda match: "$" + match.group() + "$", part)
    return "".join(parts)


def formula_block(formula: str) -> str:
    """Show the governing equation, rather than a whole derivation in the formula line."""
    formula = re.split(_ARROW, formula, maxsplit=1)[0].strip(" ;\n")
    formula = formula.removeprefix("$$").removesuffix("$$").strip("$")
    formula = re.sub(r"^\\[\[(]|\\[\])]$", "", formula).strip(" ;\n")
    return "\n\n".join("$$\n" + equation.strip() + "\n$$" for equation in formula.split(";") if equation.strip())
