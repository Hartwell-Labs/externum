"""Regression tests for v4.4.1 \"Titan\" fixes found by `examples/titan_tour.ext`.

Covers:
  * enum constructor patterns with bindings and guards on both backends
  * local `.ext` imports and embedded sources in `.exbc` artifacts
  * `*args` / `**kwargs` parameter binding on the VM
  * `super().__init__` / `super().method()` and trait `impl` overrides
  * `static` values, `isinstance` with VM classes, and bash blocks

Run with:  python3 -m unittest tests/test_v441_tour.py -v
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from externum.analysis import preprocess
from externum.bytecode import BytecodeCompiler, module_from_bytes, module_to_bytes
from externum.lexer import Lexer
from externum.parser import Parser
from externum.runtime import Runtime
from externum.vm import VM


def run_py(src: str) -> str:
    out = io.StringIO()
    with redirect_stdout(out):
        Runtime().run(src)
    return out.getvalue()


def run_vm(src: str, search_roots=None) -> str:
    out = io.StringIO()
    with redirect_stdout(out):
        VM(stdout=out, search_roots=search_roots).run_source(src)
    return out.getvalue()


class TestEnumPatterns(unittest.TestCase):
    def test_variant_binding_and_guard(self):
        src = (
            "enum Shape:\n"
            "    Circle(Float)\n"
            "    Square(Float)\n"
            "    Blank\n"
            "\n"
            "def render(shape: Shape) -> Str:\n"
            "    match shape:\n"
            "        case Shape.Circle(r) if r > 1.0:\n"
            '            return f"big {r}"\n'
            "        case Shape.Circle(r):\n"
            '            return f"small {r}"\n'
            "        case Shape.Square(s):\n"
            '            return f"square {s}"\n'
            "        case _:\n"
            '            return "blank"\n'
            "\n"
            "print(render(Shape.Circle(2.5)))\n"
            "print(render(Shape.Circle(0.5)))\n"
            "print(render(Shape.Square(3.0)))\n"
            "print(render(Shape.Blank))\n"
        )
        expected = ["big 2.5", "small 0.5", "square 3.0", "blank"]
        self.assertEqual(run_py(src).strip().splitlines(), expected)
        self.assertEqual(run_vm(src).strip().splitlines(), expected)


class TestVariadicParams(unittest.TestCase):
    def test_varargs_and_kwargs(self):
        src = (
            'def greet(name: Str = "world", *args: Any, **kwargs: Any) -> Str:\n'
            "    parts: List[Str] = [name]\n"
            "    for a in args:\n"
            "        parts.append(str(a))\n"
            "    for k in kwargs:\n"
            '        parts.append(f"{k}={kwargs[k]}")\n'
            '    return "|".join(parts)\n'
            "\n"
            'print(greet("Titan", 1, 2, mode="tour"))\n'
        )
        expected = ["Titan|1|2|mode=tour"]
        self.assertEqual(run_py(src).strip().splitlines(), expected)
        self.assertEqual(run_vm(src).strip().splitlines(), expected)


class TestSuperAndImpl(unittest.TestCase):
    def test_super_init_and_trait_override(self):
        src = (
            "trait Speaker:\n"
            "    def speak(self) -> Str:\n"
            "        pass\n"
            "\n"
            "class Animal:\n"
            "    def __init__(self, name: Str):\n"
            "        self.name = name\n"
            "\n"
            "    def label(self) -> Str:\n"
            '        return f"Animal({self.name})"\n'
            "\n"
            "class Dog(Animal):\n"
            "    def __init__(self, name: Str):\n"
            "        super().__init__(name)\n"
            "\n"
            "    def label(self) -> Str:\n"
            '        return f"{super().label()}/dog"\n'
            "\n"
            "class Robot:\n"
            "    def __init__(self, serial: Int):\n"
            "        self.serial = serial\n"
            "\n"
            "    def speak(self) -> Str:\n"
            '        return "base"\n'
            "\n"
            "impl Speaker for Robot:\n"
            "    def speak(self) -> Str:\n"
            '        return f"impl-{self.serial}"\n'
            "\n"
            'dog: Dog = Dog("Rex")\n'
            "robot: Robot = Robot(7)\n"
            "print(dog.label())\n"
            "print(robot.speak())\n"
            "print(isinstance(dog, Animal))\n"
        )
        expected = ["Animal(Rex)/dog", "impl-7", "True"]
        self.assertEqual(run_py(src).strip().splitlines(), expected)
        self.assertEqual(run_vm(src).strip().splitlines(), expected)


class TestLocalImports(unittest.TestCase):
    HELPER = "def triple(n: Int) -> Int:\n    return n * 3\n\nNAME: Str = \"helper\"\n"

    def test_vm_finds_sibling_ext_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "tour_helper.ext"), "w", encoding="utf-8") as fh:
                fh.write(self.HELPER)
            # Imported `.ext` modules must run on the VM, not through the
            # Python transpiler compatibility layer.
            with mock.patch("externum.runtime.Runtime", side_effect=AssertionError("transpiler used")):
                out = run_vm(
                    "import tour_helper\nprint(tour_helper.triple(4), tour_helper.NAME)\n",
                    search_roots=[tmp],
                )
        self.assertEqual(out.strip().splitlines(), ["12 helper"])

    def test_exbc_bundles_local_imports(self):
        src = "import tour_helper\nprint(tour_helper.triple(4))\n"
        processed, _ = preprocess(src)
        ast = list(Parser(Lexer(processed).tokenize()).parse())
        module = BytecodeCompiler(ast, module_name="embedded.ext").compile()
        module.embedded_sources = {"tour_helper": self.HELPER}

        loaded = module_from_bytes(module_to_bytes(module))
        out = io.StringIO()
        with redirect_stdout(out):
            VM(stdout=out).run_module(loaded)
        self.assertEqual(out.getvalue().strip(), "12")


class TestStaticAndBash(unittest.TestCase):
    def test_static_value(self):
        src = 'static BUILD: Str = "4.4.1"\nprint(BUILD)\n'
        self.assertEqual(run_py(src).strip(), "4.4.1")
        self.assertEqual(run_vm(src).strip(), "4.4.1")

    def test_bash_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "bash.txt")
            src = f"`echo bash-v441 > {target}`\n"
            run_py(src)
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read().strip(), "bash-v441")
            run_vm(src)
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read().strip(), "bash-v441")


if __name__ == "__main__":
    unittest.main()
