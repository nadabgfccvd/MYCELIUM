from __future__ import annotations

import unittest

from mycelium_accel.dsl import Node, compile_program, run_program


class DSLTests(unittest.TestCase):
    def test_compiled_program_matches_direct_api(self) -> None:
        tree = Node(
            "mul",
            children=[
                Node("inc", children=[Node("input")]),
                Node("max", children=[Node("const", value=3), Node("const", value=7)]),
            ],
        )
        macros = {"M001": Node("add", children=[Node("input"), Node("const", value=2)])}
        wrapped = Node("sub", children=[Node("macro", value="M001"), tree])

        executor = compile_program(
            wrapped,
            macros,
            max_nodes=63,
            max_abs_value=100000,
            max_steps=256,
        )

        for value in (-5, -1, 0, 1, 4, 9):
            compiled = executor.run(value)
            direct = run_program(
                wrapped,
                value,
                macros,
                max_nodes=63,
                max_abs_value=100000,
                max_steps=256,
            )
            self.assertEqual(compiled, direct)


if __name__ == "__main__":
    unittest.main()
