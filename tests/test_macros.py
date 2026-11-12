"""Tests for the macro language companion (macros/macro_lang.py).

Run from the project root: python3 -m unittest discover -s tests -v
"""

import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bf_converter as bc  # noqa: E402
import macros.macro_lang as ml  # noqa: E402

EXAMPLE = os.path.join(ROOT, "macros", "examples", "famous_macros.md")


class TestMacroEngine(unittest.TestCase):
    def test_available_programs(self):
        progs = ml.available_programs()
        for key in ("hello_world", "fizzbuzz", "hanoi", "bottles", "mandelbrot"):
            self.assertIn(key, progs)

    def test_parse_example(self):
        lang = ml.load_macro_lang(EXAMPLE)
        self.assertEqual(lang.name, "FamousMacros")
        self.assertEqual(lang.token_to_key["FizzBuzz"], "fizzbuzz")
        self.assertEqual(lang.extension, ".famousmacros")

    def test_unknown_program_rejected(self):
        with self.assertRaises(bc.LanguageError):
            ml.MacroLang("X", {"Nope": "not_a_program"})

    def test_tokenize_longest_match(self):
        lang = ml.load_macro_lang(EXAMPLE)
        self.assertEqual(
            ml.tokenize_macros("Hello World FizzBuzz", lang.token_to_key),
            ["hello_world", "fizzbuzz"])

    def test_run_single(self):
        lang = ml.load_macro_lang(EXAMPLE)
        self.assertEqual(ml.run_macros(lang, "Hello World"), b"Hello World!\n")

    def test_run_composite(self):
        lang = ml.load_macro_lang(EXAMPLE)
        out = ml.run_macros(lang, "Hello World Alphabet")
        self.assertEqual(out, b"Hello World!\n" + b"ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def test_tape_isolation(self):
        # A tape-dirtying program must not corrupt the next macro.
        lang = ml.MacroLang("Iso", {"Dirty": "add", "Hello": "hello_world"})
        self.assertEqual(ml.run_macros(lang, "Dirty Hello"), b"5Hello World!\n")

    def test_comments_ignored(self):
        lang = ml.load_macro_lang(EXAMPLE)
        out = ml.run_macros(lang, "dear reader, Hello World — yours, FizzBuzz")
        expected = (bc.run_bf(ml.load_program_code("hello_world"))
                    + bc.run_bf(ml.load_program_code("fizzbuzz")))
        self.assertEqual(out, expected)

    def test_render_parse_roundtrip(self):
        lang = ml.load_macro_lang(EXAMPLE)
        md = ml.render_macro_md(lang.name, lang.token_to_key)
        back = ml.parse_macro_md(md)
        self.assertEqual(back.token_to_key, lang.token_to_key)


class TestMacroCLI(unittest.TestCase):
    def _cli(self, args, data=b""):
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "macros", "macro_lang.py")] + args,
            input=data, capture_output=True, timeout=120)

    def test_run_inline(self):
        p = self._cli(["run", EXAMPLE, "-c", "Hello World"])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, b"Hello World!\n")

    def test_verify(self):
        p = self._cli(["verify", EXAMPLE])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(b"ALL TESTS PASSED", p.stdout)
        self.assertIn(b"SKIP", p.stdout)  # mandelbrot skipped by default

    def test_generate_and_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._cli(["generate", EXAMPLE, "-o", tmp])
            self.assertEqual(p.returncode, 0, p.stderr)
            interp = os.path.join(tmp, "famousmacros_macro_interpreter.py")
            self.assertTrue(os.path.exists(interp))
            p = subprocess.run([sys.executable, interp, "-c", "Hello World Alphabet"],
                               capture_output=True, timeout=120)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(p.stdout, b"Hello World!\nABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def test_list(self):
        p = self._cli(["list"])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(b"fizzbuzz", p.stdout)


if __name__ == "__main__":
    unittest.main()
