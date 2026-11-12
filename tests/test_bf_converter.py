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
            answers = ["WizardLang", "wiz", "east", "west", "up", "down",
                       "say", "hear", "begin", "end"]
            self._run_wizard(answers, path)
            lang = bc.load_language(path)
            self.assertEqual(lang.name, "WizardLang")
            self.assertEqual(lang.extension, ".wiz")
            self.assertEqual(lang.bf_to_token[">"], "east")
            self.assertEqual(lang.bf_to_token["]"], "end")

    def test_wizard_defaults_and_retry_on_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wiz.md")
            # Empty name retried; duplicate token retried; rest are defaults.
            answers = ["", "DefaultLang", "", "same", "same", "west"] + [""] * 6
            self._run_wizard(answers, path)
            lang = bc.load_language(path)
            self.assertEqual(lang.name, "DefaultLang")
            self.assertEqual(lang.extension, ".defaultlang")
            self.assertEqual(lang.bf_to_token[">"], "same")
            self.assertEqual(lang.bf_to_token["<"], "west")
            self.assertEqual(lang.bf_to_token["+"], bc.DEFAULT_TOKENS["+"])

    def test_wizard_retries_invalid_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wiz.md")
            answers = ["ExtLang", "bad ext", "hwf"] + [""] * 8
            self._run_wizard(answers, path)
            lang = bc.load_language(path)
            self.assertEqual(lang.extension, ".hwf")

    def test_wizard_refuses_overwrite_without_yes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wiz.md")
            with open(path, "w") as fh:
                fh.write("original")
            answers = ["X", ""] + [""] * 8 + ["n"]
            with self.assertRaises(bc.LanguageError):
                self._run_wizard(answers, path)
            with open(path) as fh:
                self.assertEqual(fh.read(), "original")


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
                expected = bc.bf_to_lang(bc.TESTS[0][1], lang.bf_to_token)
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


if __name__ == "__main__":
    unittest.main()
