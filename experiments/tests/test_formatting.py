import unittest

from agentic_jee_system.presentation import formula_block, student_text


class StudentFormattingTests(unittest.TestCase):
    def test_formula_does_not_repeat_arrow_derivation(self):
        self.assertEqual(formula_block(r"2x + 5 = 15 ;\Rightarrow; 2x = 10 ;\Rightarrow; x = \frac{10}{2} = 5"),
                         "$$\n2x + 5 = 15\n$$")

    def test_unwrapped_fraction_is_renderable(self):
        self.assertEqual(student_text(r"Divide both sides by 2: x = \frac{10}{2} = 5"),
                         r"Divide both sides by 2: x = $\frac{10}{2}$ = 5")

    def test_existing_physics_math_and_units_are_preserved(self):
        text = r"Use kinetic energy: $K = \frac{1}{2}mv^2$. The answer is $400\,\text{J}$."
        self.assertEqual(student_text(text), text)

    def test_arrows_inside_math_are_separate_equations(self):
        self.assertEqual(student_text(r"$2x=10 \Rightarrow x=5$"), "$2x=10$\n\n$x=5$")
