#!/usr/bin/env python3
"""Macro languages — each command runs a whole program, tape-isolated.

A companion to bf_converter.py, kept in its own folder so the core project
layout stays untouched. Where a Trivial brainfuck substitution replaces the
8 commands with tokens, a MACRO language replaces whole PROGRAMS with
tokens: writing "FizzBuzz" runs the entire FizzBuzz program. Each macro runs
on its own fresh tape, so programs never clobber each other.

Usage:
    python3 macros/macro_lang.py list
    python3 macros/macro_lang.py run MACRO.md PROGRAM [--input TEXT]
    python3 macros/macro_lang.py run MACRO.md -c "Hello World FizzBuzz"
    python3 macros/macro_lang.py generate MACRO.md [-o DIR]
    python3 macros/macro_lang.py verify MACRO.md [--slow]
    python3 macros/macro_lang.py template [OUT.md]

Reuses bf_converter's brainfuck engine; nothing in the core tool is modified.
"""

import argparse
import os
import string
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import bf_converter as bc  # noqa: E402

PROGRAM_DIRS = [os.path.join(_ROOT, "programs", "famous"),
                os.path.join(_ROOT, "programs")]

# Programs too slow to run in a default verify pass.
SLOW_PROGRAMS = {"mandelbrot"}

_CODE_CACHE = {}


def available_programs():
    """key -> path for every bundled .bf program (famous programs first)."""
    progs = {}
    for d in PROGRAM_DIRS:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".bf"):
                progs.setdefault(fn[:-3], os.path.join(d, fn))
    return progs


def load_program_code(key):
    """Filtered brainfuck source for a program key (cached)."""
    if key not in _CODE_CACHE:
        progs = available_programs()
        if key not in progs:
            raise bc.LanguageError(
                "unknown program %r; available: %s" % (key, ", ".join(sorted(progs))))
        with open(progs[key], encoding="utf-8", errors="replace") as fh:
            _CODE_CACHE[key] = bc.bf_filter(fh.read())
    return _CODE_CACHE[key]


class MacroLang:
    def __init__(self, name, token_to_key):
        self.name = name
        self.slug = bc.slugify(name)
        self.token_to_key = dict(token_to_key)
        if not self.token_to_key:
            raise bc.LanguageError("a macro language needs at least one macro")
        for key in self.token_to_key.values():
            load_program_code(key)  # raises on unknown program
        self.key_to_token = {k: t for t, k in self.token_to_key.items()}

    @property
    def extension(self):
        return "." + self.slug


def _macros_from_table(rows):
    """Read a | Token | Program | chart; the Program column holds known keys."""
    if len(rows) < 2:
        return {}
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, data = rows[0], [r for r in rows[1:] if not bc._is_separator_row(r)]
    if not data:
        return {}
    progs = available_programs()
    scores = [sum(1 for r in data if bc._clean_cell(r[c]) in progs)
              for c in range(width)]
    pcol = max(range(width), key=lambda c: scores[c])
    if scores[pcol] == 0:
        return {}
    candidates = [c for c in range(width) if c != pcol]
    named = [c for c in candidates
             if not bc._DESC_HEADER.search(header[c] if c < len(header) else "")]
    tcol = None
    for c in named + candidates:
        if any(bc._clean_cell(r[c]) for r in data):
            tcol = c
            break
    if tcol is None:
        return {}
    mapping = {}
    for r in data:
        key = bc._clean_cell(r[pcol])
        tok = bc._clean_cell(r[tcol])
        if key in progs and tok:
            mapping[tok] = key
    return mapping


def parse_macro_md(text, fallback="macros"):
    name = bc._extract_name(text, fallback)
    mapping = {}
    for table in bc._extract_tables(text):
        rows = [bc._split_row(line) for line in table]
        found = _macros_from_table(rows)
        if len(found) > len(mapping):
            mapping = found
    if not mapping:
        raise bc.LanguageError(
            "no macro chart found (expected a | Token | Program | table whose "
            "Program column names bundled programs; see 'list')")
    return MacroLang(name, mapping)


def load_macro_lang(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    fallback = os.path.splitext(os.path.basename(path))[0]
    try:
        return parse_macro_md(text, fallback)
    except bc.LanguageError as exc:
        raise bc.LanguageError("%s: %s" % (path, exc))


def tokenize_macros(text, token_to_key):
    """Longest-match scan -> ordered list of program keys (non-tokens ignored)."""
    tokens = sorted(token_to_key, key=len, reverse=True)
    out = []
    i, n = 0, len(text)
    while i < n:
        for tok in tokens:
            if text.startswith(tok, i):
                out.append(token_to_key[tok])
                i += len(tok)
                break
        else:
            i += 1
    return out


def run_macros(lang, text, data=b"", input_iter=None):
    """Run each macro on its OWN fresh tape; concatenate the outputs."""
    out = bytearray()
    for key in tokenize_macros(text, lang.token_to_key):
        out.extend(bc.run_bf(load_program_code(key), data, input_iter=input_iter))
    return bytes(out)


def render_macro_md(name, token_to_key):
    lines = [
        "# %s" % name,
        "",
        "A macro language: each command runs an entire program on its own fresh",
        "tape. Write a program by naming programs; non-token text is ignored.",
        "",
        "## Macros",
        "",
        "| Token | Program |",
        "| --- | --- |",
    ]
    for tok, key in token_to_key.items():
        lines.append("| %s | %s |" % (tok, key))
    lines += [""]
    return "\n".join(lines)


_MACRO_INTERP_TEMPLATE = string.Template('''\
#!/usr/bin/env python3
"""$name macro interpreter — generated by macros/macro_lang.py.

Each token runs a whole program on its own fresh tape; outputs concatenate.
$header
"""

import argparse
import sys

LANG_NAME = "$name"
TOKEN_TO_CODE = $token_map
_TOKENS = sorted(TOKEN_TO_CODE, key=len, reverse=True)

$bf_core

def expand(source):
    out, i, n = [], 0, len(source)
    while i < n:
        for tok in _TOKENS:
            if source.startswith(tok, i):
                out.append(TOKEN_TO_CODE[tok])
                i += len(tok)
                break
        else:
            i += 1
    return out


def run_macros(source, data=b"", input_iter=None):
    out = bytearray()
    for code in expand(source):
        out.extend(run_bf(code, data, input_iter=input_iter))
    return bytes(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="$name macro interpreter")
    ap.add_argument("program", nargs="?", help="macro program file")
    ap.add_argument("-c", "--code", help="run an inline macro program")
    ap.add_argument("--input", help="input bytes for macros that read ',' (default: stdin)")
    args = ap.parse_args(argv)
    if args.code is None and args.program is None:
        ap.error("give a program file or -c CODE")
    try:
        if args.code is not None:
            source = args.code
        else:
            with open(args.program, encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        if args.input is not None:
            out = run_macros(source, args.input.encode("utf-8"))
        else:
            out = run_macros(source, input_iter=_stdin_bytes())
    except (OSError, RuntimeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
''')


def generate_macro(lang, outdir=None, verbose=True):
    """Write a standalone macro interpreter for lang. Returns its path."""
    if outdir is None:
        outdir = os.path.join("generated", lang.slug)
    os.makedirs(outdir, exist_ok=True)
    token_map = {tok: load_program_code(key) for tok, key in lang.token_to_key.items()}
    header = ("Generated by macros/macro_lang.py (bf_converter v%s). "
              "Language: %s." % (bc.__version__, lang.name))
    content = _MACRO_INTERP_TEMPLATE.substitute(
        name=lang.name, header=header, token_map=repr(token_map), bf_core=bc._BF_CORE)
    path = os.path.join(outdir, lang.slug + "_macro_interpreter.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    if verbose:
        print("Generated %s macro interpreter: %s" % (lang.name, path))
        print("Try it:")
        print("  python3 %s -c '%s'" % (path, next(iter(lang.token_to_key))))
    return path


def verify_macros(lang, slow=False, verbose=True):
    """Check each macro reproduces its program's native output, plus a composite."""
    if verbose:
        print("Verifying %s (macro language):" % lang.name)
    ok = True
    fast_tokens, parts = [], []
    for tok, key in lang.token_to_key.items():
        if key in SLOW_PROGRAMS and not slow:
            if verbose:
                print("  %-18s SKIP (slow; use --slow)" % tok)
            continue
        expected = bc.run_bf(load_program_code(key))
        got = run_macros(lang, tok)
        good = got == expected
        ok = ok and good
        if verbose:
            print("  %-18s %s" % (tok, "PASS" if good else "FAIL"))
        if good:
            fast_tokens.append(tok)
            parts.append(expected)
    if len(fast_tokens) >= 2:
        got = run_macros(lang, " ".join(fast_tokens))
        good = got == b"".join(parts)
        ok = ok and good
        if verbose:
            print("  %-18s %s" % ("[composite]", "PASS" if good else "FAIL"))
    if verbose:
        print("ALL TESTS PASSED" if ok else "FAILURES DETECTED")
    return ok


def _write_out(text, out_path):
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="macro_lang.py",
        description="Macro languages: each command runs a whole program, tape-isolated.")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list available programs usable as macros")

    p = sub.add_parser("run", help="run a macro program")
    p.add_argument("lang_md", help="macro definition Markdown file")
    p.add_argument("program", nargs="?", help="macro program file")
    p.add_argument("-c", "--code", help="run an inline macro program")
    p.add_argument("--input", help="input bytes for macros that read ',' (default: stdin)")

    p = sub.add_parser("generate", help="generate a standalone macro interpreter")
    p.add_argument("lang_md", help="macro definition Markdown file")
    p.add_argument("-o", "--output", help="output directory (default: generated/<slug>)")

    p = sub.add_parser("verify", help="check each macro against its program's native output")
    p.add_argument("lang_md", help="macro definition Markdown file")
    p.add_argument("--slow", action="store_true", help="also run slow programs (mandelbrot)")

    p = sub.add_parser("template", help="write a macro definition template")
    p.add_argument("output", nargs="?", default="macro_template.md", help="output path")

    args = ap.parse_args(argv)
    try:
        if args.command == "list":
            progs = available_programs()
            print("Available programs (use as the Program column):")
            for key in sorted(progs):
                note = "  [SLOW]" if key in SLOW_PROGRAMS else ""
                print("  %-16s %s%s" % (key, progs[key], note))
        elif args.command == "run":
            lang = load_macro_lang(args.lang_md)
            if args.code is not None:
                source = args.code
            elif args.program:
                with open(args.program, encoding="utf-8", errors="replace") as fh:
                    source = fh.read()
            else:
                ap.error("give a program file or -c CODE")
            if args.input is not None:
                out = run_macros(lang, source, args.input.encode("utf-8"))
            else:
                out = run_macros(lang, source, input_iter=bc._stdin_bytes())
            sys.stdout.buffer.write(out)
            sys.stdout.buffer.flush()
        elif args.command == "generate":
            generate_macro(load_macro_lang(args.lang_md), args.output)
        elif args.command == "verify":
            if not verify_macros(load_macro_lang(args.lang_md), slow=args.slow):
                return 1
        elif args.command == "template":
            if os.path.exists(args.output):
                raise bc.LanguageError("%s already exists" % args.output)
            progs = available_programs()
            picks = ["hello_world", "fizzbuzz", "hanoi", "bottles", "alphabet", "mandelbrot"]
            mapping = {}
            for key in picks:
                if key in progs:
                    mapping[key.replace("_", " ").title()] = key
            _write_out(render_macro_md("MyMacros", mapping), args.output)
            print("Wrote %s" % args.output)
    except (bc.LanguageError, bc.BFError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except OSError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
