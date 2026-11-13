"""Unit + end-to-end tests for bf_converter.py.

Run from the project root:
    python3 -m unittest discover -s tests -v
"""

import contextlib
import glob
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bf_converter as bc  # noqa: E402

PIRATE = {
    ">": "starboard", "<": "port", "+": "hoist", "-": "lower",
    ".": "shout", ",": "parrot", "[": "ahoy", "]": "avast",
}

OOK = {
    ">": "Ook. Ook?", "<": "Ook? Ook.", "+": "Ook. Ook.", "-": "Ook! Ook!",
    ".": "Ook! Ook.", ",": "Ook. Ook!", "[": "Ook! Ook?", "]": "Ook? Ook!",
}


def make_lang(name="PirateScript", mapping=None):
    return bc.Language(name, mapping or PIRATE)


class TestBrainfuckCore(unittest.TestCase):
    def test_builtin_programs(self):
        for name, src, data, expected in bc.TESTS:
            with self.subTest(name=name):
                self.assertEqual(bc.run_bf(bc.bf_filter(src), data), expected)

    def test_comments_ignored(self):
        self.assertEqual(bc.bf_filter("a+b!c[ignore]me-."), "+[]-.")

    def test_unmatched_open_bracket(self):
        with self.assertRaises(bc.BFError):
            bc.run_bf("[")

    def test_unmatched_close_bracket(self):
        with self.assertRaises(bc.BFError):
            bc.run_bf("]")

    def test_pointer_underflow(self):
        with self.assertRaises(bc.BFError):
            bc.run_bf("<")

    def test_step_limit(self):
        with self.assertRaises(bc.BFError):
            bc.run_bf("+[]", max_steps=100)  # infinite loop

    def test_empty_program(self):
        self.assertEqual(bc.run_bf(""), b"")

    def test_input_eof_stores_zero(self):
        # ',' at EOF stores 0, so the loop exits instead of hanging.
        self.assertEqual(bc.run_bf(",[.,]", b""), b"")

    def test_tape_grows_right(self):
        self.assertEqual(bc.run_bf(">" * 100 + "+" + "."), b"\x01")


class TestTokenize(unittest.TestCase):
    def test_longest_match_wins(self):
        t2b = {"ab": "+", "abc": "-"}
        self.assertEqual(bc.tokenize("abc ab", t2b), "-+")

    def test_tokens_with_spaces(self):
        t2b = {t: s for s, t in OOK.items()}
        src = "+++++[>+++++[>++<-]<-]>>."  # 5*5*2 = 50 -> '2'
        prog = bc.bf_to_lang(src, OOK)
        self.assertEqual(bc.run_bf(bc.tokenize(prog, t2b)), b"2")

    def test_unknown_chars_ignored(self):
        t2b = {t: s for s, t in PIRATE.items()}
        prog = "hoist, dear reader! shout"
        self.assertEqual(bc.tokenize(prog, t2b), "+.")

    def test_case_sensitive(self):
        t2b = {"pew": "+", "Pew": "-"}
        self.assertEqual(bc.tokenize("pew Pew", t2b), "+-")

    def test_empty_program(self):
        self.assertEqual(bc.tokenize("", {"x": "+"}), "")


class TestValidation(unittest.TestCase):
    def test_valid_set_passes(self):
        bc.validate_tokens(PIRATE)
        bc.validate_tokens(OOK)

    def test_missing_command(self):
        bad = dict(PIRATE)
        del bad["]"]
        with self.assertRaises(bc.LanguageError):
            bc.validate_tokens(bad)

    def test_duplicate_token(self):
        bad = dict(PIRATE)
        bad["]"] = bad["["]
        with self.assertRaises(bc.LanguageError):
            bc.validate_tokens(bad)

    def test_empty_token(self):
        bad = dict(PIRATE)
        bad["+"] = "   "
        with self.assertRaises(bc.LanguageError):
            bc.validate_tokens(bad)

    def test_multiline_token(self):
        bad = dict(PIRATE)
        bad["+"] = "two\nlines"
        with self.assertRaises(bc.LanguageError):
            bc.validate_tokens(bad)

    def test_prefix_warning(self):
        warns = bc.token_warnings({">": "ab", "<": "abc"})
        self.assertEqual(len(warns), 1)
        self.assertIn("prefix", warns[0])

    def test_no_warning_for_distinct_tokens(self):
        self.assertEqual(bc.token_warnings(PIRATE), [])


class TestMarkdownParsing(unittest.TestCase):
    def test_standard_three_column_table(self):
        md = "# PirateScript\n\n| Brainfuck | PirateScript | Description |\n| --- | --- | --- |\n"
        for sym, desc in bc.COMMANDS:
            md += "| `\\%s` | %s | %s |\n" % (sym, PIRATE[sym], desc)
        lang = bc.parse_markdown(md)
        self.assertEqual(lang.name, "PirateScript")
        self.assertEqual(lang.bf_to_token, PIRATE)
        self.assertEqual(lang.slug, "piratescript")

    def test_two_column_table_without_backticks(self):
        md = "| bf | new |\n|---|---|\n"
        for sym in bc.BF_COMMANDS:
            md += "| %s | %s |\n" % (sym, PIRATE[sym])
        lang = bc.parse_markdown(md, fallback_name="fallback")
        self.assertEqual(lang.bf_to_token, PIRATE)
        self.assertEqual(lang.name, "fallback")

    def test_reordered_columns_with_description_first(self):
        md = "# Swap\n\n| Meaning | New | Brainfuck |\n| --- | --- | --- |\n"
        for sym, desc in bc.COMMANDS:
            md += "| %s | %s | %s |\n" % (desc, PIRATE[sym], sym)
        lang = bc.parse_markdown(md)
        self.assertEqual(lang.bf_to_token, PIRATE)

    def test_name_variants(self):
        table = "| Brainfuck | X |\n| --- | --- |\n" + "".join(
            "| %s | %s |\n" % (s, PIRATE[s]) for s in bc.BF_COMMANDS)
        self.assertEqual(bc.parse_markdown("# Language: Foo\n" + table).name, "Foo")
        self.assertEqual(bc.parse_markdown("Name: Bar\n" + table).name, "Bar")
        self.assertEqual(bc.parse_markdown(table, "baz").name, "baz")

    def test_line_format_fallback(self):
        md = "# LineLang\n\n" + "".join(
            "`%s` = %s\n" % (s, PIRATE[s]) for s in bc.BF_COMMANDS)
        lang = bc.parse_markdown(md)
        self.assertEqual(lang.bf_to_token, PIRATE)

    def test_incomplete_chart_raises(self):
        md = "| Brainfuck | X |\n| --- | --- |\n| > | right |\n"
        with self.assertRaises(bc.LanguageError) as ctx:
            bc.parse_markdown(md)
        self.assertIn("missing", str(ctx.exception))

    def test_pipe_in_token(self):
        mapping = dict(PIRATE)
        mapping["+"] = "a|b"
        md = bc.render_language_md("PipeLang", mapping)
        lang = bc.parse_markdown(md)
        self.assertEqual(lang.bf_to_token["+"], "a|b")

    def test_quoted_tokens(self):
        md = "| Brainfuck | X |\n| --- | --- |\n" + "".join(
            '| %s | "%s" |\n' % (s, PIRATE[s]) for s in bc.BF_COMMANDS)
        self.assertEqual(bc.parse_markdown(md).bf_to_token, PIRATE)

    def test_load_language_error_mentions_path(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write("# nothing here\n")
            path = fh.name
        try:
            with self.assertRaises(bc.LanguageError) as ctx:
                bc.load_language(path)
            self.assertIn(path, str(ctx.exception))
        finally:
            os.unlink(path)


class TestConversion(unittest.TestCase):
    def test_roundtrip_all_builtin_programs(self):
        lang = make_lang()
        for name, src, data, expected in bc.TESTS:
            with self.subTest(name=name):
                prog = bc.bf_to_lang(src, lang.bf_to_token)
                back = bc.lang_to_bf(prog, lang.token_to_bf)
                self.assertEqual(back, src)
                self.assertEqual(bc.run_bf(back, data), expected)

    def test_roundtrip_with_comments_in_lang_program(self):
        lang = make_lang()
        src = bc.TESTS[0][1]
        prog = bc.bf_to_lang(src, lang.bf_to_token)
        commented = "Ahoy, matey! " + prog + " ...and that be Hello World."
        self.assertEqual(bc.run_bf(bc.tokenize(commented, lang.token_to_bf)),
                         b"Hello World!\n")

    def test_bf_to_lang_skips_non_commands(self):
        self.assertEqual(bc.bf_to_lang("a+b", {">": "R", "+": "U"}), "U")


class TestRendering(unittest.TestCase):
    def test_render_parse_roundtrip(self):
        mapping = dict(OOK)  # tokens with spaces and shared prefixes
        md = bc.render_language_md("Ook Clone", mapping)
        lang = bc.parse_markdown(md)
        self.assertEqual(lang.name, "Ook Clone")
        self.assertEqual(lang.bf_to_token, mapping)

    def test_template_is_valid_language(self):
        lang = bc.parse_markdown(bc.TEMPLATE_MD)
        self.assertEqual(len(lang.bf_to_token), 8)
        self.assertEqual(lang.name, "MyLanguage")
        self.assertEqual(lang.extension, ".mylanguage")

    def test_slugify(self):
        self.assertEqual(bc.slugify("PirateScript"), "piratescript")
        self.assertEqual(bc.slugify("Ook! Clone 2"), "ook_clone_2")
        self.assertEqual(bc.slugify("!!!"), "language")


class TestWizard(unittest.TestCase):
    def _run_wizard(self, answers, path):
        with mock.patch("builtins.input", side_effect=answers), \
                contextlib.redirect_stdout(io.StringIO()):
            return bc.wizard(path)

    def test_wizard_creates_parseable_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wiz.md")
            answers = ["WizardLang", "wiz", "1000", "16", "east", "west", "up", "down",
                       "say", "hear", "begin", "end"]
            self._run_wizard(answers, path)
            lang = bc.load_language(path)
            self.assertEqual(lang.name, "WizardLang")
            self.assertEqual(lang.extension, ".wiz")
            self.assertEqual(lang.tape_cells, 1000)
            self.assertEqual(lang.cell_bits, 16)
            self.assertEqual(lang.bf_to_token[">"], "east")
            self.assertEqual(lang.bf_to_token["]"], "end")

    def test_wizard_defaults_and_retry_on_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wiz.md")
            # Empty name retried; duplicate token retried; rest are defaults.
            answers = ["", "DefaultLang", "", "", "", "same", "same", "west"] + [""] * 6
            self._run_wizard(answers, path)
            lang = bc.load_language(path)
            self.assertEqual(lang.name, "DefaultLang")
            self.assertEqual(lang.extension, ".defaultlang")
            self.assertEqual(lang.tape_cells, bc.DEFAULT_TAPE_CELLS)
            self.assertEqual(lang.cell_bits, bc.DEFAULT_CELL_BITS)
            self.assertEqual(lang.bf_to_token[">"], "same")
            self.assertEqual(lang.bf_to_token["<"], "west")
            self.assertEqual(lang.bf_to_token["+"], bc.DEFAULT_TOKENS["+"])

    def test_wizard_retries_invalid_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wiz.md")
            answers = ["ExtLang", "bad ext", "hwf", "", ""] + [""] * 8
            self._run_wizard(answers, path)
            lang = bc.load_language(path)
            self.assertEqual(lang.extension, ".hwf")

    def test_wizard_refuses_overwrite_without_yes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wiz.md")
            with open(path, "w") as fh:
                fh.write("original")
            answers = ["X", "", "", ""] + [""] * 8 + ["n"]
            with self.assertRaises(bc.LanguageError):
                self._run_wizard(answers, path)
            with open(path) as fh:
                self.assertEqual(fh.read(), "original")


class TestTapeConfig(unittest.TestCase):
    def test_defaults(self):
        lang = bc.Language("L", dict(bc.DEFAULT_TOKENS))
        self.assertEqual(lang.tape_cells, 30000)
        self.assertEqual(lang.cell_bits, 8)

    def test_parse_config_lines(self):
        md = bc.render_language_md("L", dict(bc.DEFAULT_TOKENS), tape_cells=5000, cell_bits=16)
        lang = bc.parse_markdown(md)
        self.assertEqual(lang.tape_cells, 5000)
        self.assertEqual(lang.cell_bits, 16)

    def test_absent_lines_use_defaults(self):
        md = bc.render_language_md("L", dict(bc.DEFAULT_TOKENS))
        md = "\n".join(l for l in md.splitlines()
                       if not l.startswith(("Tape-Cells:", "Cell-Bits:")))
        lang = bc.parse_markdown(md)
        self.assertEqual(lang.tape_cells, 30000)
        self.assertEqual(lang.cell_bits, 8)

    def test_invalid_config_rejected(self):
        for bad in ("0", "-5", "abc"):
            with self.assertRaises(bc.LanguageError):
                bc.clean_tape_cells(bad)
        for bad in ("7", "12", "64", "abc"):
            with self.assertRaises(bc.LanguageError):
                bc.clean_cell_bits(bad)

    def test_generated_interpreter_bakes_config(self):
        lang = bc.Language("Wide", dict(bc.DEFAULT_TOKENS), tape_cells=100, cell_bits=16)
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                bc.generate(lang, tmp, verbose=False)
            interp = os.path.join(tmp, "wide_interpreter.py")
            with open(interp) as fh:
                text = fh.read()
            self.assertIn("TAPE_CELLS = 100", text)
            self.assertIn("CELL_BITS = 16", text)
            # Tape wraps at 100: cell0=1, move right 100 -> back to cell0 -> prints 1.
            prog = os.path.join(tmp, "wrap.wide")
            with open(prog, "w") as fh:
                fh.write("plus " + "right " * 100 + "print")
            p = subprocess.run([sys.executable, interp, prog], capture_output=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(p.stdout, b"\x01")
            # 16-bit: 256 is nonzero, so [.-] emits 256 bytes (8-bit would emit none).
            prog2 = os.path.join(tmp, "bits.wide")
            with open(prog2, "w") as fh:
                fh.write("plus " * 256 + "open print minus close")
            p = subprocess.run([sys.executable, interp, prog2], capture_output=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(len(p.stdout), 256)

    def test_run_uses_language_config_and_flag_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = os.path.join(tmp, "wide.md")
            with open(md, "w") as fh:
                fh.write(bc.render_language_md("Wide", dict(bc.DEFAULT_TOKENS), cell_bits=16))
            prog = os.path.join(tmp, "p.wide")
            with open(prog, "w") as fh:
                fh.write("plus " * 256 + "open print minus close")
            # Language config (16-bit): 256 nonzero -> 256 bytes.
            p = subprocess.run([sys.executable, bc.__file__, "run", md, prog],
                               capture_output=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(len(p.stdout), 256)
            # Flag override to 8-bit: 256 wraps to 0 -> loop skipped -> empty.
            p = subprocess.run([sys.executable, bc.__file__, "run", md, prog, "--cell-bits", "8"],
                               capture_output=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(p.stdout, b"")


class TestGeneratedToolkit(unittest.TestCase):
    """End-to-end: generated files must work standalone via subprocess."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.outdir = os.path.join(cls.tmp.name, "piratescript")
        cls.lang = make_lang()
        with contextlib.redirect_stdout(io.StringIO()):
            bc.generate(cls.lang, cls.outdir, verbose=False)
        cls.interp = os.path.join(cls.outdir, "piratescript_interpreter.py")
        cls.bf_interp = os.path.join(cls.outdir, "brainfuck_interpreter.py")
        cls.converter = os.path.join(cls.outdir, "converter.py")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _run(self, script, args, data=b""):
        proc = subprocess.run([sys.executable, script] + args,
                              input=data, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        return proc.stdout

    def test_generated_interpreter_all_tests(self):
        for name, _src, data, expected in bc.TESTS:
            with self.subTest(name=name):
                path = os.path.join(self.outdir, "tests", name + ".piratescript")
                self.assertEqual(self._run(self.interp, [path], data), expected)

    def test_generated_bf_interpreter_all_tests(self):
        for name, src, data, expected in bc.TESTS:
            with self.subTest(name=name):
                path = os.path.join(self.outdir, "tests", name + ".bf")
                self.assertEqual(self._run(self.bf_interp, [path], data), expected)

    def test_generated_converter_roundtrip(self):
        src_path = os.path.join(self.outdir, "hello_world.bf")
        lang_path = os.path.join(self.tmp.name, "hello.piratescript")
        back_path = os.path.join(self.tmp.name, "hello.bf")
        self._run(self.converter, ["to-lang", src_path, "-o", lang_path])
        self._run(self.converter, ["to-bf", lang_path, "-o", back_path])
        with open(back_path) as fh:
            self.assertEqual(fh.read().strip(), bc.TESTS[0][1])
        self.assertEqual(self._run(self.bf_interp, [back_path]), b"Hello World!\n")

    def test_generated_interpreter_inline_code(self):
        self.assertEqual(self._run(self.interp, ["-c", "shout"]), b"\x00")

    def test_generated_interpreter_stdin_input(self):
        path = os.path.join(self.outdir, "tests", "echo.piratescript")
        self.assertEqual(self._run(self.interp, [path], b"ahoy!\n"), b"ahoy!\n")

    def test_verify_passes(self):
        outdir = os.path.join(self.tmp.name, "verify")
        with contextlib.redirect_stdout(io.StringIO()):
            ok = bc.verify(self.lang, outdir, verbose=True)
        self.assertTrue(ok)

    def test_generated_files_are_self_contained(self):
        # No import of bf_converter anywhere in the generated toolkit.
        for name in os.listdir(self.outdir):
            if name.endswith(".py"):
                with open(os.path.join(self.outdir, name), encoding="utf-8") as fh:
                    self.assertNotIn("bf_converter", fh.read().split('"""')[2])

    def _assert_no_stdin_block(self, script, program, expected):
        # Regression: interpreters used to read ALL of stdin up front and hung
        # on interactive terminals even for programs without ','. Keep the
        # stdin pipe OPEN: a correct interpreter finishes without reading it.
        proc = subprocess.Popen(
            [sys.executable, script, program],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail("%s blocked reading stdin for a program without ','" % script)
        out, err = proc.communicate()
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out, expected)

    def test_lang_interpreter_no_input_does_not_block_on_open_stdin(self):
        self._assert_no_stdin_block(
            self.interp, os.path.join(self.outdir, "hello_world.piratescript"),
            b"Hello World!\n")

    def test_bf_interpreter_no_input_does_not_block_on_open_stdin(self):
        self._assert_no_stdin_block(
            self.bf_interp, os.path.join(self.outdir, "hello_world.bf"),
            b"Hello World!\n")

    def test_echo_reads_input_on_demand(self):
        path = os.path.join(self.outdir, "tests", "echo.piratescript")
        proc = subprocess.Popen(
            [sys.executable, self.interp, path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.stdin.write(b"hi\n")
        proc.stdin.flush()
        proc.stdin.close()  # EOF -> ',' stores 0 -> loop exits
        out, err = proc.communicate(timeout=10)
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out, b"hi\n")


class TestCLI(unittest.TestCase):
    def _cli(self, args, data=b""):
        return subprocess.run([sys.executable, bc.__file__] + args,
                              input=data, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=60)

    def test_template_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.md")
            proc = self._cli(["template", path])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            lang = bc.load_language(path)
            self.assertEqual(len(lang.bf_to_token), 8)

    def test_template_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.md")
            self.assertEqual(self._cli(["template", path]).returncode, 0)
            self.assertNotEqual(self._cli(["template", path]).returncode, 0)

    def test_convert_both_directions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "add.pirate")
            proc = self._cli(["convert", "examples/pirate.md", "programs/add.bf",
                              "--to", "lang", "-o", out])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc = self._cli(["convert", "examples/pirate.md", out, "--to", "bf"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.decode().strip(), bc.TESTS[1][1])

    def test_run_with_input_flag(self):
        proc = self._cli(["run", "examples/pirate.md",
                          "generated/piratescript/tests/add_input.piratescript",
                          "--input", "23"])
        # Fall back to generating on the fly if the demo toolkit is absent.
        if proc.returncode != 0:
            with tempfile.TemporaryDirectory() as tmp:
                self._cli(["generate", "examples/pirate.md", "-o", tmp])
                proc = self._cli(["run", "examples/pirate.md",
                                  os.path.join(tmp, "tests", "add_input.piratescript"),
                                  "--input", "23"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, b"5")

    def test_run_bf_stdin(self):
        proc = self._cli(["run-bf", "programs/echo.bf"], data=b"ship ahoy\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, b"ship ahoy\n")

    def test_run_bf_does_not_block_on_open_stdin(self):
        proc = subprocess.Popen(
            [sys.executable, bc.__file__, "run-bf", "programs/hello_world.bf"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail("run-bf blocked reading stdin for a program without ','")
        out, err = proc.communicate()
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out, b"Hello World!\n")

    def test_bad_definition_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.md")
            with open(path, "w") as fh:
                fh.write("# no chart\n")
            proc = self._cli(["generate", path])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn(b"error:", proc.stderr)


class TestExtension(unittest.TestCase):
    def test_clean_extension_valid_forms(self):
        for value, expected in [("hwf", "hwf"), (".hwf", "hwf"), ("`hwf`", "hwf"),
                                ('"hwf"', "hwf"), ("my-lang", "my-lang"),
                                ("v2.lang", "v2.lang"), ("..hwf", "hwf")]:
            with self.subTest(value=value):
                self.assertEqual(bc.clean_extension(value), expected)

    def test_clean_extension_invalid(self):
        for value in ["", "   ", ".", "...", "a b", "a/b", "a\\b", "hwf!"]:
            with self.subTest(value=value):
                with self.assertRaises(bc.LanguageError):
                    bc.clean_extension(value)

    def test_language_default_and_custom(self):
        lang = make_lang()
        self.assertEqual(lang.extension, ".piratescript")
        lang = bc.Language("Hello World Fuck", PIRATE, extension=".hwf")
        self.assertEqual(lang.extension, ".hwf")
        # Toolkit dir/interpreter keep the name slug; only program files change.
        self.assertEqual(lang.slug, "hello_world_fuck")

    def test_parse_extension_line(self):
        md = bc.render_language_md("ExtLang", PIRATE, extension="hwf")
        self.assertEqual(bc.parse_markdown(md).extension, ".hwf")
        # Absent Extension line -> slug default (backward compatible).
        md2 = "\n".join(l for l in md.splitlines() if not l.startswith("Extension:"))
        self.assertEqual(bc.parse_markdown(md2).extension, ".extlang")

    def test_parse_invalid_extension_raises(self):
        md = bc.render_language_md("ExtLang", PIRATE)
        md = md.replace("Extension: .extlang", "Extension: bad ext")
        with self.assertRaises(bc.LanguageError):
            bc.parse_markdown(md)

    def test_render_parse_roundtrip_with_extension(self):
        md = bc.render_language_md("Hello World Fuck", OOK, extension="hwf")
        lang = bc.parse_markdown(md)
        self.assertEqual(lang.name, "Hello World Fuck")
        self.assertEqual(lang.bf_to_token, OOK)
        self.assertEqual(lang.extension, ".hwf")

    def test_generated_files_use_custom_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            lang = bc.Language("Hello World Fuck", PIRATE, extension="hwf")
            with contextlib.redirect_stdout(io.StringIO()):
                bc.generate(lang, tmp, verbose=False)
            self.assertTrue(os.path.exists(os.path.join(tmp, "hello_world.hwf")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "tests", "echo.hwf")))
            self.assertFalse(os.path.exists(os.path.join(tmp, "hello_world.hello_world_fuck")))
            interp = os.path.join(tmp, "hello_world_fuck_interpreter.py")
            proc = subprocess.run(
                [sys.executable, interp, os.path.join(tmp, "hello_world.hwf")],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, b"Hello World!\n")


class TestExamples(unittest.TestCase):
    """Bundled example definitions must parse and stay runnable."""

    def test_examples_parse_and_embedded_hello_matches(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        paths = sorted(glob.glob(os.path.join(root, "examples", "*.md")))
        self.assertTrue(paths, "no example definitions found")
        for path in paths:
            with self.subTest(example=os.path.basename(path)):
                lang = bc.load_language(path)
                self.assertEqual(len(lang.bf_to_token), 8)
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                m = re.search(r"```text\n(.*?)\n```", text, re.S)
                self.assertIsNotNone(m, "example must embed a Hello World block")
                expected = bc.bf_to_lang(bc.TESTS[0][1], lang.bf_to_token, lang.seq_to_token)
                self.assertEqual(m.group(1).strip(), expected)
                self.assertEqual(
                    bc.run_bf(bc.tokenize(m.group(1), lang.token_to_bf)),
                    b"Hello World!\n")


class TestGeneratedRootReadme(unittest.TestCase):
    def test_helper_documents_folder_and_all_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = bc.write_generated_root_readme(tmp)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            for name, _src, _data, _expected in bc.TESTS:
                self.assertIn("`%s`" % name, text)
                self.assertIn(bc.TEST_INFO[name], text)
            self.assertIn("gitignored", text)
            self.assertIn("24 checks", text)

    def test_cli_default_output_writes_root_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            lang_path = os.path.abspath(os.path.join("examples", "pirate.md"))
            proc = subprocess.run(
                [sys.executable, bc.__file__, "generate", lang_path],
                cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(os.path.exists(os.path.join(tmp, "generated", "README.md")))
            self.assertTrue(os.path.exists(
                os.path.join(tmp, "generated", "piratescript", "converter.py")))

    def test_cli_custom_output_skips_root_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            lang_path = os.path.abspath(os.path.join("examples", "pirate.md"))
            outdir = os.path.join(tmp, "mytoolkit")
            proc = subprocess.run(
                [sys.executable, bc.__file__, "generate", lang_path, "-o", outdir],
                cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(os.path.exists(os.path.join(tmp, "generated")))
            self.assertFalse(os.path.exists(os.path.join(tmp, "README.md")))


class TestReadmeDocs(unittest.TestCase):
    def test_readme_documents_every_builtin_test(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "README.md"), encoding="utf-8") as fh:
            text = fh.read()
        for name, _src, _data, _expected in bc.TESTS:
            with self.subTest(test=name):
                self.assertIn("`%s`" % name, text)
                self.assertIn(bc.TEST_INFO[name], text)


class TestRandomLanguage(unittest.TestCase):
    def test_seeded_determinism(self):
        self.assertEqual(bc.random_language("corporate", seed=42),
                         bc.random_language("corporate", seed=42))

    def test_all_themes_draw_valid_languages(self):
        for theme in sorted(bc.THEMES):
            for seed in range(5):
                with self.subTest(theme=theme, seed=seed):
                    name, mapping, ext = bc.random_language(theme, seed=seed)
                    self.assertTrue(name)
                    bc.validate_tokens(mapping)
                    self.assertEqual(bc.token_warnings(mapping), [])
                    self.assertEqual(bc.clean_extension(ext), ext)

    def test_name_override(self):
        name, _mapping, _ext = bc.random_language("cat", name="KittyCore", seed=1)
        self.assertEqual(name, "KittyCore")

    def test_unknown_theme_raises(self):
        with self.assertRaises(bc.LanguageError):
            bc.random_language("nope")

    def test_cli_random_init_and_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "corp.md")
            args = [sys.executable, bc.__file__, "init", path,
                    "--random", "--theme", "corporate", "--seed", "7"]
            proc = subprocess.run(args, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            lang = bc.load_language(path)
            bc.validate_tokens(lang.bf_to_token)
            again = subprocess.run(args, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=60)
            self.assertNotEqual(again.returncode, 0)  # refuses overwrite
            forced = subprocess.run(args + ["--force"], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=60)
            self.assertEqual(forced.returncode, 0, forced.stderr)

    def test_cli_list_themes(self):
        proc = subprocess.run([sys.executable, bc.__file__, "init", "--list-themes"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for theme in bc.THEMES:
            self.assertIn(theme.encode(), proc.stdout)


class TestBragSheet(unittest.TestCase):
    def test_brag_sheet_counts_and_tokens(self):
        lang = make_lang()
        text = bc.brag_sheet(lang)
        for tok in PIRATE.values():
            self.assertIn(tok, text)
        total = sum(len(bc.bf_filter(s)) for _n, s, _d, _e in bc.TESTS)
        self.assertIn(format(total, ","), text)
        self.assertIn("tokens per byte", text)

    def test_verify_prints_brag_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                ok = bc.verify(make_lang(), tmp, verbose=True)
            self.assertTrue(ok)
            self.assertIn("Brag sheet", buf.getvalue())


class TestWikiExport(unittest.TestCase):
    def test_render_wiki_declaration_and_chart(self):
        lang = make_lang()
        text = bc.render_wiki(lang)
        expected_args = ", ".join('"%s"' % PIRATE[s] for s in bc.BF_COMMANDS)
        self.assertIn("TrivialBrainfuckSubstitution(%s)" % expected_args, text)
        self.assertIn("'''PirateScript'''", text)
        for sym in bc.BF_COMMANDS:
            self.assertIn("<nowiki>%s</nowiki>" % sym, text)
        self.assertIn("[[Trivial brainfuck substitution", text)

    def test_cli_export_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "wiki.txt")
            proc = subprocess.run(
                [sys.executable, bc.__file__, "export", "examples/pirate.md", "--wiki", "-o", out],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with open(out, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn('TrivialBrainfuckSubstitution("starboard"', text)


class TestPoetryMode(unittest.TestCase):
    def test_poem_preserves_program(self):
        lang = make_lang()
        src = bc.TESTS[0][1]
        toks = [lang.bf_to_token[c] for c in src]
        text = bc.poem(lang, toks, "corporate")
        self.assertEqual(bc.tokenize(text, lang.token_to_bf), src)
        self.assertEqual(bc.run_bf(bc.tokenize(text, lang.token_to_bf)), b"Hello World!\n")
        self.assertIn("Hi team,", text)

    def test_poem_auto_theme_matches_tokens(self):
        self.assertEqual(bc.pick_flavor_theme(make_lang()), "pirate")

    def test_poem_unsafe_tokens_fallback(self):
        # Single-letter tokens make nearly all prose unsafe -> fallback.
        mapping = dict(zip(bc.BF_COMMANDS, ["e", "t", "a", "o", "i", "n", "s", "r"]))
        lang = bc.Language("Lazy", mapping)
        toks = [lang.bf_to_token[c] for c in "+++."]
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            text = bc.poem(lang, toks, "corporate")
        self.assertEqual(bc.tokenize(text, lang.token_to_bf), "+++.")
        self.assertIn("warning", buf.getvalue())

    def test_poem_unknown_theme(self):
        with self.assertRaises(bc.LanguageError):
            bc.poem(make_lang(), ["hoist"], "nope")

    def test_poem_deterministic(self):
        lang = make_lang()
        toks = [lang.bf_to_token[c] for c in bc.TESTS[1][1]]
        self.assertEqual(bc.poem(lang, toks, "pirate"), bc.poem(lang, toks, "pirate"))

    def test_cli_flavor_convert_and_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "email.corp")
            proc = subprocess.run(
                [sys.executable, bc.__file__, "convert", "examples/corporate.md",
                 "programs/add.bf", "--to", "lang", "--flavor", "corporate", "-o", out],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            lang = bc.load_language("examples/corporate.md")
            with open(out, encoding="utf-8") as fh:
                code = bc.tokenize(fh.read(), lang.token_to_bf)
            self.assertEqual(bc.run_bf(code), b"5")

    def test_cli_flavor_rejected_for_bf(self):
        proc = subprocess.run(
            [sys.executable, bc.__file__, "convert", "examples/pirate.md",
             "programs/add.bf", "--to", "bf", "--flavor"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(b"--flavor", proc.stderr)


class TestFamousPrograms(unittest.TestCase):
    """The bundled classics must produce their canonical outputs."""

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _run_famous(self, name):
        path = os.path.join(self.ROOT, "programs", "famous", name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            return bc.run_bf(bc.bf_filter(fh.read()))

    def test_bottles(self):
        out = self._run_famous("bottles.bf")
        self.assertTrue(out.startswith(b"99 Bottles of beer on the wall\r\n"))
        self.assertTrue(out.endswith(b"0 Bottles of beer on the wall\r\n\r\n"))
        self.assertEqual(out.count(b"Take one down and pass it around"), 99)
        self.assertEqual(out.count(b"of beer on the wall"), 198)

    def test_fizzbuzz(self):
        out = self._run_famous("fizzbuzz.bf").decode("utf-8")
        expected = "\n".join("FizzBuzz" if n % 15 == 0 else "Fizz" if n % 3 == 0
                             else "Buzz" if n % 5 == 0 else str(n)
                             for n in range(1, 101)) + "\n"
        self.assertEqual(out, expected)

    def test_hanoi(self):
        out = self._run_famous("hanoi.bf").decode("utf-8")
        moves = re.findall(r"von Turm (\w) auf Turm (\w)", out)

        def hanoi(n, a, c, b):
            if n == 0:
                return []
            return hanoi(n - 1, a, b, c) + [(a, c)] + hanoi(n - 1, b, c, a)

        self.assertEqual(moves, hanoi(3, "a", "c", "b"))

    @unittest.skipUnless(os.environ.get("BF_SLOW_TESTS") == "1",
                         "set BF_SLOW_TESTS=1 to run the multi-minute mandelbrot check")
    def test_mandelbrot(self):
        out = self._run_famous("mandelbrot.bf")
        ref = os.path.join(self.ROOT, "programs", "famous", "mandelbrot_expected.txt")
        with open(ref, "rb") as fh:
            self.assertEqual(out, fh.read())


class TestGallery(unittest.TestCase):
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_gallery_converts_all_and_roundtrips(self):
        lang = bc.load_language(os.path.join(self.ROOT, "examples", "pirate.md"))
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                written = bc.gallery(lang, tmp, verbose=True)
            self.assertEqual(len(written), len(bc.FAMOUS))
            for (key, filename, _t, _n, _s), out_path in zip(bc.FAMOUS, written):
                with self.subTest(program=key):
                    self.assertTrue(out_path.endswith(key + ".piratescript"))
                    with open(os.path.join(self.ROOT, "programs", "famous", filename),
                              encoding="utf-8", errors="replace") as fh:
                        original = bc.bf_filter(fh.read())
                    with open(out_path, encoding="utf-8") as fh:
                        self.assertEqual(bc.tokenize(fh.read(), lang.token_to_bf), original)

    def test_gallery_bottles_runs(self):
        lang = bc.load_language(os.path.join(self.ROOT, "examples", "pirate.md"))
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                written = bc.gallery(lang, tmp, verbose=False)
            with open(written[0], encoding="utf-8") as fh:
                code = bc.tokenize(fh.read(), lang.token_to_bf)
            out = bc.run_bf(code)
            self.assertTrue(out.startswith(b"99 Bottles of beer on the wall"))

    def test_cli_gallery(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, bc.__file__, "gallery", "examples/pirate.md", "-o", tmp],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            for key, _f, _t, _n, _s in bc.FAMOUS:
                self.assertTrue(os.path.exists(os.path.join(tmp, key + ".piratescript")))


class TestIdioms(unittest.TestCase):
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _lang(self):
        return bc.Language("ShortcutScript", dict(bc.DEFAULT_TOKENS),
                           idioms={"clear": "[-]", "move": "[->+<]"})

    def test_parse_idiom_chart(self):
        lang = bc.load_language(os.path.join(self.ROOT, "examples", "idioms.md"))
        self.assertEqual(lang.idioms, {"clear": "[-]", "move": "[->+<]"})
        self.assertEqual(lang.seq_to_token, {"[-]": "clear", "[->+<]": "move"})
        self.assertEqual(lang.token_to_bf["move"], "[->+<]")

    def test_greedy_conversion_and_roundtrip(self):
        lang = self._lang()
        self.assertEqual(
            bc.bf_to_lang("+++[-][->+<]", lang.bf_to_token, lang.seq_to_token),
            "plus plus plus clear move")
        self.assertEqual(bc.tokenize("plus plus plus clear move", lang.token_to_bf),
                         "+++[-][->+<]")

    def test_longest_sequence_wins(self):
        lang = bc.Language("L", dict(bc.DEFAULT_TOKENS),
                           idioms={"short": "[-]", "long": "[-]+"})
        self.assertEqual(bc.bf_to_lang("[-]+", lang.bf_to_token, lang.seq_to_token), "long")
        self.assertEqual(bc.bf_to_lang("[-]", lang.bf_to_token, lang.seq_to_token), "short")

    def test_idiom_token_collision_rejected(self):
        with self.assertRaises(bc.LanguageError):
            bc.Language("L", dict(bc.DEFAULT_TOKENS), idioms={"plus": "[-]"})

    def test_bad_sequence_rejected(self):
        with self.assertRaises(bc.LanguageError):
            bc.Language("L", dict(bc.DEFAULT_TOKENS), idioms={"x": "+"})
        with self.assertRaises(bc.LanguageError):
            bc.Language("L", dict(bc.DEFAULT_TOKENS), idioms={"x": "[-]a"})

    def test_render_parse_roundtrip_with_idioms(self):
        lang = self._lang()
        md = bc.render_language_md(lang.name, lang.bf_to_token, idioms=lang.idioms)
        back = bc.parse_markdown(md)
        self.assertEqual(back.idioms, lang.idioms)
        self.assertEqual(back.bf_to_token, lang.bf_to_token)

    def test_generated_toolkit_with_idioms(self):
        lang = self._lang()
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                bc.generate(lang, tmp, verbose=False)
            src = os.path.join(tmp, "src.bf")
            with open(src, "w") as fh:
                fh.write("+++[-][->+<]")
            proc = subprocess.run(
                [sys.executable, os.path.join(tmp, "converter.py"), "to-lang", src],
                capture_output=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.decode().strip(), "plus plus plus clear move")
            demo = os.path.join(tmp, "demo" + lang.extension)
            with open(demo, "w") as fh:
                fh.write("plus " * 65 + "move right print")
            proc = subprocess.run(
                [sys.executable, os.path.join(tmp, lang.slug + "_interpreter.py"), demo],
                capture_output=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, b"A")


class TestRepl(unittest.TestCase):
    def _session(self, text):
        return subprocess.run(
            [sys.executable, bc.__file__, "repl", "examples/idioms.md"],
            input=text.encode(), capture_output=True, timeout=60)

    def test_repl_persistent_state_and_bf(self):
        p = self._session("plus plus plus\n:bf >++.\n:tape\n:reset\n:quit\n")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(b"output: b'\\x02'", p.stdout)
        self.assertIn(b"ptr=1", p.stdout)
        self.assertIn(b"tape reset", p.stdout)
        self.assertIn(b"bye", p.stdout)

    def test_repl_input_queue(self):
        p = self._session(":input AB\n:bf ,.\n:quit\n")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(b"output: b'A'", p.stdout)

    def test_repl_error_recovery(self):
        p = self._session(":bf [\nplus\n:quit\n")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(b"error:", p.stdout)
        self.assertIn(b"ptr=0", p.stdout)


class TestTraceAndSemantics(unittest.TestCase):
    def _runbf(self, code, *flags):
        return subprocess.run(
            [sys.executable, bc.__file__, "run-bf", "/dev/stdin"] + list(flags),
            input=code.encode(), capture_output=True, timeout=60)

    def test_trace_stderr_clean_stdout(self):
        p = subprocess.run(
            [sys.executable, bc.__file__, "run-bf", "programs/wrap_down.bf", "--trace"],
            capture_output=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, b"\xff")
        self.assertIn(b"step 1: '-'", p.stderr)
        self.assertIn(b"step 2: '.'", p.stderr)

    def test_trace_every(self):
        p = subprocess.run(
            [sys.executable, bc.__file__, "run-bf", "programs/add.bf",
             "--trace", "--trace-every", "50"],
            capture_output=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn(b"step 1:", p.stderr)
        self.assertIn(b"step 50:", p.stderr)

    def test_cell_bits_16(self):
        p = self._runbf("+" * 300 + ".", "--cell-bits", "16")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, b"\x2c")  # 300 = 0x12C, low byte
        p = self._runbf("+" * 65536 + ".", "--cell-bits", "16")
        self.assertEqual(p.stdout, b"\x00")

    def test_eof_options(self):
        self.assertEqual(self._runbf(",.", "--eof", "minus-one").stdout, b"\xff")
        self.assertEqual(self._runbf("+++++++,.", "--eof", "keep").stdout, b"\x07")
        self.assertEqual(self._runbf(",.").stdout, b"\x00")

    def test_fixed_tape_wraps(self):
        self.assertEqual(self._runbf("+>>>>.", "--tape-size", "4").stdout, b"\x01")
        self.assertEqual(self._runbf("+<.", "--tape-size", "4").stdout, b"\x00")


class TestGalleryDocAndPackaging(unittest.TestCase):
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_gallery_doc_fresh(self):
        with open(os.path.join(self.ROOT, "GALLERY.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), bc.render_gallery_doc())

    def test_pyproject_consistent(self):
        try:
            import tomllib
        except ImportError:
            self.skipTest("tomllib requires Python 3.11+")
        with open(os.path.join(self.ROOT, "pyproject.toml"), "rb") as fh:
            data = tomllib.load(fh)
        self.assertEqual(data["project"]["version"], bc.__version__)
        self.assertEqual(data["project"]["scripts"]["bf-converter"], "bf_converter:main")
        self.assertTrue(callable(bc.main))


if __name__ == "__main__":
    unittest.main()
