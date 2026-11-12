"""Regression tests for the v4.4.0 "Titan" update.

Covers the features added to bring the bytecode VM up to parity with the
Python transpiler and to fix long-standing defects in both backends:

  * class inheritance + super() on the VM
  * list/dict/set comprehensions on the VM (nested `for`, `if`, tuple targets)
  * `except ... as e`, exception-type filters, `finally`
  * `with ... as` binding and closing on the VM
  * `*args` / `**kwargs` calls, star-unpacking inside literals
  * index assignment (`d[k] = v`, `d[k] += 1`), `del`
  * enums as values *and* constructors, payloads, equality
  * f-string format specs, triple-quoted strings, `print(sep=/end=)`
  * struct field names, struct kwargs
  * transpiler: dict comprehensions, `not in`, `[...]` method calls,
    `comptime`, `Ok`/`Some`, union/generic annotations, walrus, `yield from`,
    function-level `defer`
  * generators on both backends

Run with:  python3 -m unittest tests/test_v440_features.py -v
"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from externum.runtime import Runtime
from externum.vm import VM


def run_py(src: str) -> str:
    out = io.StringIO()
    with redirect_stdout(out):
        Runtime().run(src)
    return out.getvalue()


def run_vm(src: str) -> str:
    out = io.StringIO()
    with redirect_stdout(out):
        VM(stdout=out).run_source(src)
    return out.getvalue()


def run_both(src: str) -> tuple[str, str]:
    return run_py(src), run_vm(src)


class TestClassInheritance(unittest.TestCase):
    def test_inheritance_and_super(self):
        src = (
            "class A:\n"
            "    def hi(self):\n"
            '        print("A")\n'
            "\n"
            "class B(A):\n"
            "    def hi(self):\n"
            "        super().hi()\n"
            '        print("B")\n'
            "\n"
            "B().hi()\n"
        )
        for out in run_both(src):
            self.assertEqual(out.strip().splitlines(), ["A", "B"])

    def test_inherited_attribute_and_init(self):
        src = (
            "class Base:\n"
            "    def __init__(self, n):\n"
            "        self.n = n\n"
            "\n"
            "class Child(Base):\n"
            "    pass\n"
            "\n"
            "c = Child(7)\n"
            "print(c.n)\n"
        )
        for out in run_both(src):
            self.assertIn("7", out)


class TestComprehensions(unittest.TestCase):
    def test_list_comprehension_with_filter(self):
        src = "print([x * x for x in range(6) if x % 2 == 0])\n"
        for out in run_both(src):
            self.assertIn("[0, 4, 16]", out)

    def test_nested_comprehension(self):
        src = "print([(a, b) for a in range(2) for b in range(2)])\n"
        for out in run_both(src):
            self.assertIn("(0, 0)", out)
            self.assertIn("(1, 1)", out)

    def test_dict_comprehension(self):
        src = "print({k: v for k, v in [(1, 2), (3, 4)]})\n"
        for out in run_both(src):
            self.assertIn("{1: 2, 3: 4}", out)

    def test_set_comprehension(self):
        src = "print(sorted({x % 3 for x in range(10)}))\n"
        for out in run_both(src):
            self.assertIn("[0, 1, 2]", out)


class TestExceptions(unittest.TestCase):
    def test_except_as_binds_value(self):
        src = "try:\n    raise ValueError('boom')\nexcept ValueError as e:\n    print('caught', e)\n"
        for out in run_both(src):
            self.assertIn("caught boom", out)

    def test_type_filter_skips_non_matching_handler(self):
        src = (
            "try:\n"
            "    raise TypeError('t')\n"
            "except ValueError:\n"
            '    print("wrong")\n'
            "except TypeError as e:\n"
            '    print("right", e)\n'
        )
        for out in run_both(src):
            self.assertNotIn("wrong", out)
            self.assertIn("right t", out)

    def test_finally_runs(self):
        src = (
            "try:\n"
            "    raise ValueError('x')\n"
            "except ValueError:\n"
            '    print("handled")\n'
            "finally:\n"
            '    print("cleanup")\n'
        )
        for out in run_both(src):
            self.assertIn("cleanup", out)


class TestWithStatement(unittest.TestCase):
    def test_with_as_closes_handle(self):
        src = (
            'with open("/tmp/_ext_v440_with.txt", "w") as fh:\n'
            "    fh.write('data')\n"
            'with open("/tmp/_ext_v440_with.txt") as fh:\n'
            "    print(fh.read())\n"
        )
        for out in run_both(src):
            self.assertIn("data", out)


class TestUnpacking(unittest.TestCase):
    def test_star_args_and_kwargs(self):
        src = "def f(a, b):\n    return a + b\nargs = [1, 2]\nkw = {'a': 3, 'b': 4}\nprint(f(*args))\nprint(f(**kw))\n"
        for out in run_both(src):
            self.assertIn("3", out)
            self.assertIn("7", out)

    def test_star_in_list_literal(self):
        src = "xs = [1, 2]\nprint([0, *xs])\n"
        for out in run_both(src):
            self.assertIn("[0, 1, 2]", out)

    def test_tuple_assignment(self):
        src = "a, b = 1, 2\nprint(a + b)\n"
        for out in run_both(src):
            self.assertIn("3", out)


class TestIndexAssignment(unittest.TestCase):
    def test_set_and_augmented_index(self):
        src = 'd = {}\nd["k"] = 1\nd["k"] += 1\nprint(d["k"])\n'
        for out in run_both(src):
            self.assertIn("2", out)

    def test_del_index(self):
        src = "xs = [1, 2]\ndel xs[0]\nprint(xs)\n"
        for out in run_both(src):
            self.assertIn("[2]", out)


class TestEnums(unittest.TestCase):
    def test_variant_is_value_and_constructor(self):
        src = "enum Color:\n    Red\n    Green\nc = Color.Red\nd = Color.Red()\nprint(c == d)\nprint(c)\n"
        for out in run_both(src):
            self.assertIn("True", out)
            self.assertIn("Red", out)

    def test_payload(self):
        src = "enum Shape:\n    Circle(Float)\n    Square(Float)\ns = Shape.Circle(2.5)\nprint(s.data)\n"
        py_out, vm_out = run_both(src)
        self.assertIn("2.5", py_out)
        self.assertIn("2.5", vm_out)


class TestStringsAndPrint(unittest.TestCase):
    def test_format_spec(self):
        src = 'x = 3.14159\nprint(f"{x:.2f}")\n'
        for out in run_both(src):
            self.assertIn("3.14", out)

    def test_triple_quoted_string(self):
        src = 'print("""a\nb""")\n'
        for out in run_both(src):
            self.assertIn("a\nb", out)

    def test_print_end(self):
        src = 'print("a", end="")\nprint("b")\n'
        for out in run_both(src):
            self.assertIn("ab", out.replace(" ", ""))


class TestStructs(unittest.TestCase):
    def test_field_names_and_kwargs(self):
        src = "struct Point:\n    x: Int\n    y: Int\np = Point(1, y=2)\nprint(p.x, p.y)\n"
        for out in run_both(src):
            self.assertIn("1 2", out)


class TestTranspilerFixes(unittest.TestCase):
    def test_not_in(self):
        src = "print(1 not in [2])\n"
        for out in run_both(src):
            self.assertIn("True", out)

    def test_method_call_on_empty_list_literal(self):
        src = "print([].count(1))\n"
        for out in run_both(src):
            self.assertIn("0", out)

    def test_comptime_declaration(self):
        src = "comptime x = 2\nprint(x)\n"
        for out in run_both(src):
            self.assertIn("2", out)

    def test_result_and_option_values(self):
        src = "print(Ok(1))\nprint(Some(2))\n"
        for out in run_both(src):
            self.assertIn("Ok(1)", out)
            self.assertIn("Some(2)", out)

    def test_union_and_generic_annotations(self):
        src = (
            "def first[T](xs: List[T]) -> T:\n"
            "    return xs[0]\n"
            "def maybe(x: Int | None) -> Int:\n"
            "    return 1\n"
            "print(first([9]))\n"
            "print(maybe(1))\n"
        )
        for out in run_both(src):
            self.assertIn("9", out)

    def test_walrus(self):
        src = "if (n := 5) > 3:\n    print(n)\n"
        for out in run_both(src):
            self.assertIn("5", out)

    def test_yield_from(self):
        src = "def g():\n    yield from [1, 2]\nprint(list(g()))\n"
        for out in run_both(src):
            self.assertIn("[1, 2]", out)

    def test_defer_runs_at_function_exit(self):
        src = 'def f():\n    defer print("done")\n    print("body")\nf()\n'
        for out in run_both(src):
            self.assertEqual(out.strip().splitlines(), ["body", "done"])


class TestGenerators(unittest.TestCase):
    def test_finite_generator(self):
        src = "def g():\n    yield 1\n    yield 2\nprint(list(g()))\n"
        for out in run_both(src):
            self.assertIn("[1, 2]", out)

    def test_generator_in_for_loop(self):
        src = (
            "def nums():\n"
            "    for i in range(3):\n"
            "        yield i\n"
            "total = 0\n"
            "for n in nums():\n"
            "    total += n\n"
            "print(total)\n"
        )
        for out in run_both(src):
            self.assertIn("3", out)


class TestExamplePrograms(unittest.TestCase):
    """The shipped examples must behave identically on both backends."""

    def _example(self, name: str) -> str:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "examples", name), encoding="utf-8") as fh:
            return fh.read()

    def test_hardcore_example(self):
        src = self._example("hardcore.ext")
        py_out, vm_out = run_both(src)
        self.assertEqual(py_out, vm_out)

    def test_pokedex_example(self):
        src = self._example("pokedex.ext")
        py_out, vm_out = run_both(src)
        self.assertEqual(py_out, vm_out)


if __name__ == "__main__":
    unittest.main()
