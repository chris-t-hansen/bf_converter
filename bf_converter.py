#!/usr/bin/env python3
"""bf_converter — Trivial brainfuck substitution generator.

Automates the creation of languages from the "Trivial brainfuck substitution"
family (https://esolangs.org/wiki/Trivial_brainfuck_substitution): you define
8 replacement tokens for the 8 brainfuck commands in a Markdown file, and this
tool generates a standalone interpreter for the new language, bidirectional
converters (brainfuck <-> new language), a standalone brainfuck interpreter,
and verifies everything against a built-in test suite.

Subcommands:
  init      Interactively create a language definition Markdown file.
  template  Write a fill-in Markdown template (also usable as-is).
  generate  Generate interpreter + converters + docs from a definition file.
  convert   Convert a program between brainfuck and the new language.
  run       Run a program written in the new language.
  run-bf    Run a native brainfuck program.
  verify    Generate the language toolkit and run the built-in test suite.

Standard library only. Compatible with Python 3.8+.
"""

import argparse
import os
import re
import string
import subprocess
import sys
import tempfile

__version__ = "1.0.0"

BF_COMMANDS = "><+-.,[]"

# (symbol, description) in canonical order. Descriptions are shown in the
# wizard, the Markdown template, and generated documentation.
COMMANDS = [
    (">", "Move the data pointer one cell to the right"),
    ("<", "Move the data pointer one cell to the left"),
    ("+", "Increment the byte in the current cell (255 wraps to 0)"),
    ("-", "Decrement the byte in the current cell (0 wraps to 255)"),
    (".", "Output the byte in the current cell as a character"),
    (",", "Read one byte of input into the current cell (end of input stores 0)"),
    ("[", "If the current byte is 0, jump forward past the matching ]"),
    ("]", "If the current byte is not 0, jump back to the matching ["),
]
COMMAND_DESC = dict(COMMANDS)

DEFAULT_TOKENS = {
    ">": "right", "<": "left", "+": "plus", "-": "minus",
    ".": "print", ",": "read", "[": "open", "]": "close",
}

WIKI_URL = "https://esolangs.org/wiki/Trivial_brainfuck_substitution"


class LanguageError(ValueError):
    """Invalid language definition (bad Markdown, missing/duplicate tokens)."""


class BFError(RuntimeError):
    """Brainfuck runtime error (unmatched bracket, pointer underflow, ...)."""


# ---------------------------------------------------------------------------
# Brainfuck core
# ---------------------------------------------------------------------------

def bf_filter(source):
    """Keep only the 8 brainfuck commands; everything else is a comment."""
    return "".join(c for c in source if c in BF_COMMANDS)


def build_jumps(code):
    """Precompute the matching-bracket jump table for filtered bf code."""
    jumps = {}
    stack = []
    for i, c in enumerate(code):
        if c == "[":
            stack.append(i)
        elif c == "]":
            if not stack:
                raise BFError("unmatched ']' at position %d" % i)
            j = stack.pop()
            jumps[i] = j
            jumps[j] = i
    if stack:
        raise BFError("unmatched '[' at position %d" % stack[-1])
    return jumps


def run_bf(code, data=b"", max_steps=None, input_iter=None):
    """Execute filtered brainfuck code, returning the output bytes.

    Semantics: 8-bit wrapping cells, tape grows to the right, moving left of
    cell 0 is an error, ',' stores 0 at end of input. Input comes from data,
    or lazily from input_iter (an iterator of byte values) when given — so
    programs without ',' never touch stdin.
    """
    jumps = build_jumps(code)
    tape = bytearray(1)
    ptr = 0
    pc = 0
    out = bytearray()
    inp = input_iter if input_iter is not None else iter(data)
    steps = 0
    n = len(code)
    while pc < n:
        if max_steps is not None and steps >= max_steps:
            raise BFError("step limit exceeded (%d steps)" % max_steps)
        steps += 1
        c = code[pc]
        if c == ">":
            ptr += 1
            if ptr == len(tape):
                tape.append(0)
        elif c == "<":
            ptr -= 1
            if ptr < 0:
                raise BFError("pointer moved left of the first cell")
        elif c == "+":
            tape[ptr] = (tape[ptr] + 1) & 0xFF
        elif c == "-":
            tape[ptr] = (tape[ptr] - 1) & 0xFF
        elif c == ".":
            out.append(tape[ptr])
        elif c == ",":
            tape[ptr] = next(inp, 0)
        elif c == "[":
            if tape[ptr] == 0:
                pc = jumps[pc]
        elif c == "]":
            if tape[ptr] != 0:
                pc = jumps[pc]
        pc += 1
    return bytes(out)


def _stdin_bytes():
    """Yield stdin bytes on demand; programs without ',' never read stdin."""
    while True:
        b = sys.stdin.buffer.read(1)
        if not b:
            return
        yield b[0]


# ---------------------------------------------------------------------------
# Substitution tokenizing / conversion
# ---------------------------------------------------------------------------

def tokenize(program, token_to_bf):
    """Convert a new-language program to brainfuck code.

    Scans left to right, always matching the longest token first (so tokens
    that are prefixes of other tokens, or contain spaces like Ook!'s
    "Ook. Ook?", work). Characters that match no token are ignored, exactly
    like non-command characters in brainfuck.
    """
    tokens = sorted(token_to_bf, key=len, reverse=True)
    out = []
    i = 0
    n = len(program)
    while i < n:
        for tok in tokens:
            if program.startswith(tok, i):
                out.append(token_to_bf[tok])
                i += len(tok)
                break
        else:
            i += 1  # not part of any token: comment
    return "".join(out)


def bf_to_lang(source, bf_to_token):
    """Convert brainfuck source to the new language (space-separated tokens)."""
    return " ".join(bf_to_token[c] for c in source if c in bf_to_token)


def lang_to_bf(program, token_to_bf):
    """Convert a new-language program back to brainfuck."""
    return tokenize(program, token_to_bf)


def token_warnings(bf_to_token):
    """Non-fatal warnings about a token set (prefix collisions)."""
    warns = []
    toks = list(bf_to_token.values())
    for a in toks:
        for b in toks:
            if a != b and b.startswith(a):
                warns.append(
                    "token %r is a prefix of %r; longest-match tokenization "
                    "will always prefer %r" % (a, b, b))
    return warns


def validate_tokens(bf_to_token):
    """Raise LanguageError if the token set cannot work."""
    seen = {}
    for sym in BF_COMMANDS:
        tok = bf_to_token.get(sym)
        if tok is None:
            raise LanguageError("missing replacement for brainfuck command %r" % sym)
        if not tok or not tok.strip():
            raise LanguageError("replacement for %r must not be empty" % sym)
        if any(ch in tok for ch in "\r\n\t"):
            raise LanguageError(
                "replacement for %r must be a single line without tabs: %r" % (sym, tok))
        if tok in seen:
            raise LanguageError(
                "token %r is used for both %r and %r; tokens must be unique"
                % (tok, seen[tok], sym))
        seen[tok] = sym


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "language"


def clean_extension(value):
    """Normalize and validate a program file extension; return it without dot.

    Accepts 'hwf', '.hwf', and backticked or quoted forms. Rejects empty
    values, whitespace, and characters unsafe in filenames.
    """
    ext = value.strip()
    if len(ext) >= 2 and ext.startswith("`") and ext.endswith("`"):
        ext = ext[1:-1].strip()
    if len(ext) >= 2 and ext[0] == ext[-1] and ext[0] in "\"'":
        ext = ext[1:-1].strip()
    ext = ext.lstrip(".").strip()
    if not ext:
        raise LanguageError("file extension must not be empty")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", ext):
        raise LanguageError(
            "invalid file extension %r: use letters, digits, dots, hyphens, "
            "and underscores; no spaces or path separators" % value)
    return ext


# ---------------------------------------------------------------------------
# Language definition (Markdown) parsing
# ---------------------------------------------------------------------------

class Language:
    def __init__(self, name, bf_to_token, extension=None):
        self.name = name
        self.slug = slugify(name)
        self.bf_to_token = dict(bf_to_token)
        self.token_to_bf = {t: s for s, t in self.bf_to_token.items()}
        self.custom_extension = clean_extension(extension) if extension else None

    @property
    def extension(self):
        """Program file extension with leading dot (custom, or slug-based)."""
        return "." + (self.custom_extension or self.slug)


def _clean_cell(cell):
    """Normalize a Markdown table cell: escapes, backticks, quotes."""
    s = cell.strip()
    s = s.replace("\\|", "|")
    s = re.sub(r"\\([><+\-.,\[\]])", r"\1", s)  # markdown escapes: \> \[ \]
    if len(s) >= 2 and s.startswith("`") and s.endswith("`"):
        s = s[1:-1].strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1]
    return s.strip()


def _split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)]


def _is_separator_row(cells):
    return bool(cells) and all(re.fullmatch(r":?-+:?", c) for c in cells if c != "")


def _extract_tables(text):
    tables = []
    cur = []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            cur.append(line)
        elif cur:
            tables.append(cur)
            cur = []
    if cur:
        tables.append(cur)
    return tables


_DESC_HEADER = re.compile(r"description|meaning|effect|action|note|comment", re.I)


def _mapping_from_table(rows):
    """Try to read a bf->token mapping out of one Markdown table.

    The brainfuck column is detected by content (cells that are exactly one
    of the 8 symbols), so column order and extra description columns do not
    matter. Returns a partial mapping (possibly empty).
    """
    if len(rows) < 2:
        return {}
    header, data = rows[0], [r for r in rows[1:] if not _is_separator_row(r)]
    if not data:
        return {}
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, data = rows[0], [r for r in rows[1:] if not _is_separator_row(r)]

    # Which column holds the brainfuck symbols?
    scores = []
    for col in range(width):
        score = sum(1 for r in data if _clean_cell(r[col]) in BF_COMMANDS)
        scores.append(score)
    bf_col = max(range(width), key=lambda c: scores[c])
    if scores[bf_col] == 0:
        return {}

    # Which column holds the replacements? Prefer non-description columns.
    candidates = [c for c in range(width) if c != bf_col]
    named = [c for c in candidates
             if not _DESC_HEADER.search(header[c] if c < len(header) else "")]
    token_col = None
    for col in named + candidates:
        if any(_clean_cell(r[col]) for r in data):
            token_col = col
            break
    if token_col is None:
        return {}

    mapping = {}
    for r in data:
        sym = _clean_cell(r[bf_col])
        tok = _clean_cell(r[token_col])
        if sym in BF_COMMANDS and tok:
            mapping[sym] = tok
    return mapping


_LINE_DEF = re.compile(
    r"^\s*(?:[-*]\s+)?`?([><+\-.,\[\]])`?\s*(?:=|->|→|:)\s*(.+?)\s*$")


def _mapping_from_lines(text):
    """Fallback format: one '> = token' style definition per line."""
    mapping = {}
    for line in text.splitlines():
        m = _LINE_DEF.match(line)
        if m:
            mapping[m.group(1)] = _clean_cell(m.group(2))
    return mapping


def _extract_name(text, fallback):
    m = re.search(r"^#\s+(.+?)\s*$", text, re.M)
    if m:
        name = m.group(1).strip()
        name = re.sub(r"^language\s*[:\-]\s*", "", name, flags=re.I)
        name = name.strip("`*_ ").strip()
        if name:
            return name
    m = re.search(r"^\s*(?:language\s+)?name\s*[:=]\s*(.+?)\s*$", text, re.M | re.I)
    if m:
        return m.group(1).strip("`*_ ").strip()
    return fallback


def _extract_extension(text):
    """Optional 'Extension: .hwf' line; None means use the name slug."""
    m = re.search(r"^\s*extension\s*[:=]\s*(.+?)\s*$", text, re.M | re.I)
    if m:
        return clean_extension(m.group(1))
    return None


def parse_markdown(text, fallback_name="language"):
    """Parse a language definition Markdown document into a Language."""
    mapping = {}
    for table in _extract_tables(text):
        rows = [_split_row(line) for line in table]
        found = _mapping_from_table(rows)
        if len(found) > len(mapping):
            mapping = found
        if len(mapping) == 8:
            break
    if len(mapping) < 8:
        line_map = _mapping_from_lines(text)
        if len(line_map) > len(mapping):
            mapping = line_map
    if len(mapping) < 8:
        missing = [s for s in BF_COMMANDS if s not in mapping]
        raise LanguageError(
            "could not find a complete command chart in the Markdown file; "
            "missing replacements for: %s (expected a Markdown table with a "
            "brainfuck column and a replacement column, or '> = token' lines)"
            % " ".join(repr(s) for s in missing))
    validate_tokens(mapping)
    name = _extract_name(text, fallback_name)
    return Language(name, mapping, _extract_extension(text))


def load_language(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    fallback = os.path.splitext(os.path.basename(path))[0]
    try:
        return parse_markdown(text, fallback)
    except LanguageError as exc:
        raise LanguageError("%s: %s" % (path, exc))


# ---------------------------------------------------------------------------
# Markdown rendering (template + wizard output)
# ---------------------------------------------------------------------------

def _md_escape_token(tok):
    return tok.replace("|", "\\|")


def render_language_md(name, bf_to_token, instructions=False, extension=None):
    ext = clean_extension(extension) if extension else slugify(name)
    lines = []
    if instructions:
        lines += [
            "<!--",
            "Language definition template for bf_converter.py.",
            "1. Replace 'MyLanguage' below with your language's name.",
            "2. Replace each token in the second column with your own command.",
            "   Tokens may be words, symbols, or phrases containing spaces",
            "   (like Ook!'s 'Ook. Ook?'). They must be unique, single-line,",
            "   and are case-sensitive. Anything in a program that is not a",
            "   token is ignored, so you can freely add comments.",
            "3. Optionally change the 'Extension:' line to the file extension",
            "   your programs should use (e.g. '.ml'). It defaults to the",
            "   language name slug.",
            "4. Run: python3 bf_converter.py generate this_file.md",
            "-->",
            "",
        ]
    lines += [
        "# %s" % name,
        "",
        "A [Trivial brainfuck substitution](%s): each brainfuck command is" % WIKI_URL,
        "replaced by the token below. All other text in a program is ignored.",
        "",
        "Extension: .%s" % ext,
        "",
        "## Commands",
        "",
        "| Brainfuck | %s | Description |" % name,
        "| --- | --- | --- |",
    ]
    for sym, desc in COMMANDS:
        lines.append("| `%s` | %s | %s |" % (sym, _md_escape_token(bf_to_token[sym]), desc))
    lines += [
        "",
        "## Semantics",
        "",
        "- Cells are 8-bit bytes: `+` wraps 255 to 0, `-` wraps 0 to 255.",
        "- The tape starts at one cell and grows to the right; moving left of",
        "  the first cell is an error.",
        "- `,` reads one byte of input; at end of input it stores 0.",
        "- `.` writes the current byte to standard output.",
        "",
    ]
    return "\n".join(lines)


TEMPLATE_MD = render_language_md("MyLanguage", DEFAULT_TOKENS, instructions=True)


# ---------------------------------------------------------------------------
# Interactive wizard
# ---------------------------------------------------------------------------

def _ask(prompt):
    try:
        return input(prompt)
    except EOFError:
        raise LanguageError("input ended while asking: %s" % prompt.strip())


def wizard(output_path=None, force=False):
    """Interactively build a language definition file. Returns its path."""
    print("Trivial brainfuck substitution — language definition wizard")
    print("Each of the 8 brainfuck commands gets a replacement token of your")
    print("choice. Tokens may contain spaces, must be unique, and are")
    print("case-sensitive. Press Enter to accept the [default].")
    print()
    while True:
        name = _ask("Language name: ").strip()
        if name:
            break
        print("  Please enter a non-empty name.")
    slug = slugify(name)
    if output_path is None:
        output_path = slug + ".md"

    print()
    print("Programs in your language will be saved with a file extension")
    print("(letters, digits, dots, hyphens, underscores; no spaces).")
    while True:
        answer = _ask("File extension [%s]: " % slug).strip()
        try:
            ext = clean_extension(answer) if answer else slug
            break
        except LanguageError as exc:
            print("    %s" % exc)

    mapping = {}
    for sym, desc in COMMANDS:
        print()
        print("  %s  —  %s." % (sym, desc))
        while True:
            answer = _ask("    Replacement for '%s' [%s]: " % (sym, DEFAULT_TOKENS[sym])).strip()
            tok = answer or DEFAULT_TOKENS[sym]
            if not tok:
                print("    Token must not be empty.")
                continue
            if any(ch in tok for ch in "\r\n\t"):
                print("    Token must be a single line without tabs.")
                continue
            if tok in mapping.values():
                owner = [s for s, t in mapping.items() if t == tok][0]
                print("    %r is already used for '%s'; tokens must be unique." % (tok, owner))
                continue
            mapping[sym] = tok
            break

    for warn in token_warnings(mapping):
        print("warning: %s" % warn)

    if os.path.exists(output_path) and not force:
        answer = _ask("\n%s exists. Overwrite? [y/N]: " % output_path).strip().lower()
        if answer not in ("y", "yes"):
            raise LanguageError("aborted; %s was not modified" % output_path)

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(render_language_md(name, mapping, extension=ext))
    print()
    print("Wrote %s" % output_path)
    print("Next steps:")
    print("  python3 bf_converter.py generate %s" % output_path)
    print("  python3 bf_converter.py verify %s" % output_path)
    return output_path


# ---------------------------------------------------------------------------
# Code generation templates (standalone, stdlib-only artifacts)
# ---------------------------------------------------------------------------

_GENERATED_HEADER = (
    "Generated by bf_converter.py v__version__ (Trivial brainfuck substitution\n"
    "generator). Language: $lang_name. Regenerate instead of editing by hand."
).replace("__version__", __version__)

_BF_CORE = '''\
def build_jumps(code):
    """Precompute the matching-bracket jump table."""
    jumps = {}
    stack = []
    for i, c in enumerate(code):
        if c == "[":
            stack.append(i)
        elif c == "]":
            if not stack:
                raise RuntimeError("unmatched ']' at position %d" % i)
            j = stack.pop()
            jumps[i] = j
            jumps[j] = i
    if stack:
        raise RuntimeError("unmatched '[' at position %d" % stack[-1])
    return jumps


def run_bf(code, data=b"", max_steps=None, input_iter=None):
    """Execute brainfuck code (only ><+-.,[] characters), return output bytes.

    8-bit wrapping cells, tape grows to the right, pointer underflow is an
    error, ',' stores 0 at end of input. Input comes from data, or lazily
    from input_iter (an iterator of byte values) when given — so programs
    without ',' never touch stdin.
    """
    jumps = build_jumps(code)
    tape = bytearray(1)
    ptr = 0
    pc = 0
    out = bytearray()
    inp = input_iter if input_iter is not None else iter(data)
    steps = 0
    n = len(code)
    while pc < n:
        if max_steps is not None and steps >= max_steps:
            raise RuntimeError("step limit exceeded (%d steps)" % max_steps)
        steps += 1
        c = code[pc]
        if c == ">":
            ptr += 1
            if ptr == len(tape):
                tape.append(0)
        elif c == "<":
            ptr -= 1
            if ptr < 0:
                raise RuntimeError("pointer moved left of the first cell")
        elif c == "+":
            tape[ptr] = (tape[ptr] + 1) & 0xFF
        elif c == "-":
            tape[ptr] = (tape[ptr] - 1) & 0xFF
        elif c == ".":
            out.append(tape[ptr])
        elif c == ",":
            tape[ptr] = next(inp, 0)
        elif c == "[":
            if tape[ptr] == 0:
                pc = jumps[pc]
        elif c == "]":
            if tape[ptr] != 0:
                pc = jumps[pc]
        pc += 1
    return bytes(out)


def _stdin_bytes():
    """Yield stdin bytes on demand; programs without ',' never read stdin."""
    while True:
        b = sys.stdin.buffer.read(1)
        if not b:
            return
        yield b[0]
'''

_INTERPRETER_TEMPLATE = string.Template('''\
#!/usr/bin/env python3
"""$lang_name interpreter.

$header

$lang_name is a Trivial brainfuck substitution: every brainfuck command is
written as a token instead. Characters that are not part of any token are
ignored (comments). Run a program:

    python3 $interpreter PROGRAM.$ext
    python3 $interpreter -c 'print print print'   # inline program
    echo hi | python3 $interpreter PROGRAM.$ext  # input for the ',' command

Input is read only when the ',' command executes, so programs without input
never touch stdin (interactive terminals work). It can also be supplied with
--input TEXT. Cells are 8-bit wrapping bytes; ',' stores 0 at end of input.
"""

import argparse
import sys

LANG_NAME = "$lang_name"

# Token -> brainfuck command.
TOKEN_TO_BF = $token_map

_TOKENS = sorted(TOKEN_TO_BF, key=len, reverse=True)


def tokenize(source):
    """Longest-match scan; anything that is not a token is ignored."""
    out = []
    i = 0
    n = len(source)
    while i < n:
        for tok in _TOKENS:
            if source.startswith(tok, i):
                out.append(TOKEN_TO_BF[tok])
                i += len(tok)
                break
        else:
            i += 1
    return "".join(out)


$bf_core

def main(argv=None):
    ap = argparse.ArgumentParser(description="$lang_name interpreter (Trivial brainfuck substitution)")
    ap.add_argument("program", nargs="?", help="program file written in $lang_name")
    ap.add_argument("-c", "--code", help="run an inline program instead of a file")
    ap.add_argument("--input", help="input bytes for the ',' command (default: read stdin)")
    args = ap.parse_args(argv)
    if args.code is None and args.program is None:
        ap.error("give a program file or -c CODE")
    try:
        if args.code is not None:
            source = args.code
        else:
            with open(args.program, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        code = tokenize(source)
        if args.input is not None:
            out = run_bf(code, args.input.encode("utf-8"))
        else:
            out = run_bf(code, input_iter=_stdin_bytes())
    except (OSError, RuntimeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
''')

_CONVERTER_TEMPLATE = string.Template('''\
#!/usr/bin/env python3
"""$lang_name <-> brainfuck converter.

$header

Usage:
    python3 converter.py to-lang PROGRAM.bf [-o OUTPUT.$ext]
    python3 converter.py to-bf PROGRAM.$ext [-o OUTPUT.bf]

Output goes to stdout when -o is omitted. Conversion ignores comments: in
brainfuck, every character except ><+-.,[] ; in $lang_name, every character
that is not part of a token.
"""

import argparse
import sys

LANG_NAME = "$lang_name"

BF_TO_TOKEN = $bf_to_token
TOKEN_TO_BF = $token_map

_TOKENS = sorted(TOKEN_TO_BF, key=len, reverse=True)


def to_lang(source):
    """brainfuck -> $lang_name (space-separated tokens)."""
    return " ".join(BF_TO_TOKEN[c] for c in source if c in BF_TO_TOKEN)


def to_bf(source):
    """$lang_name -> brainfuck (longest-match token scan)."""
    out = []
    i = 0
    n = len(source)
    while i < n:
        for tok in _TOKENS:
            if source.startswith(tok, i):
                out.append(TOKEN_TO_BF[tok])
                i += len(tok)
                break
        else:
            i += 1
    return "".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="$lang_name <-> brainfuck converter")
    ap.add_argument("direction", choices=["to-lang", "to-bf"])
    ap.add_argument("input", help="input program file")
    ap.add_argument("-o", "--output", help="output file (default: stdout)")
    args = ap.parse_args(argv)
    try:
        with open(args.input, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except OSError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    result = to_lang(source) if args.direction == "to-lang" else to_bf(source)
    result += "\\n"
    try:
        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(result)
        else:
            sys.stdout.write(result)
    except OSError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
''')

_BF_INTERPRETER_TEMPLATE = string.Template('''\
#!/usr/bin/env python3
"""Standalone brainfuck interpreter.

$header

Use it to check native brainfuck programs before converting them:

    python3 brainfuck_interpreter.py PROGRAM.bf
    python3 brainfuck_interpreter.py -c '+++++[>+++++[>++<-]<-]>>.'
    echo hi | python3 brainfuck_interpreter.py cat.bf

Input is read only when the ',' command executes, so programs without input
never touch stdin (interactive terminals work). It can also be supplied with
--input TEXT. Cells are 8-bit wrapping bytes; ',' stores 0 at end of input;
every character except ><+-.,[] is a comment.
"""

import argparse
import sys

BF_COMMANDS = "><+-.,[]"


$bf_core

def main(argv=None):
    ap = argparse.ArgumentParser(description="Standalone brainfuck interpreter")
    ap.add_argument("program", nargs="?", help="brainfuck program file")
    ap.add_argument("-c", "--code", help="run an inline program instead of a file")
    ap.add_argument("--input", help="input bytes for the ',' command (default: read stdin)")
    args = ap.parse_args(argv)
    if args.code is None and args.program is None:
        ap.error("give a program file or -c CODE")
    try:
        if args.code is not None:
            source = args.code
        else:
            with open(args.program, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        code = "".join(c for c in source if c in BF_COMMANDS)
        if args.input is not None:
            out = run_bf(code, args.input.encode("utf-8"))
        else:
            out = run_bf(code, input_iter=_stdin_bytes())
    except (OSError, RuntimeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
''')

_README_TEMPLATE = string.Template('''\
# $lang_name

A [Trivial brainfuck substitution]($wiki_url) generated with `bf_converter.py`.
Every brainfuck command is written as a token; all other text is ignored, so
you can comment freely.

## Command chart

$table

## Files

| File | Purpose |
| --- | --- |
| `$interpreter` | Standalone interpreter for $lang_name programs |
| `converter.py` | Convert brainfuck -> $lang_name and back |
| `brainfuck_interpreter.py` | Standalone brainfuck interpreter for checking native programs |
| `hello_world.bf` / `hello_world.$ext` | The same Hello World in both languages |
| `tests/` | Built-in verification programs in both languages |

## Usage

```sh
# Run a program written in $lang_name (input for ',' comes from stdin):
python3 $interpreter hello_world.$ext
echo 23 | python3 $interpreter tests/add_input.$ext

# Convert any brainfuck program to $lang_name:
python3 converter.py to-lang program.bf -o program.$ext

# Convert back to brainfuck:
python3 converter.py to-bf program.$ext -o program.bf

# Check a native brainfuck program:
python3 brainfuck_interpreter.py program.bf
```

## Semantics

- Cells are 8-bit bytes: `+` wraps 255 to 0, `-` wraps 0 to 255.
- The tape starts at one cell and grows to the right; moving left of the
  first cell is an error.
- `,` reads one byte of input; at end of input it stores 0.
- Tokens are matched longest-first and are case-sensitive; anything that is
  not a token is ignored.

## Hello World

brainfuck:

```brainfuck
$hello_bf
```

$lang_name:

```text
$hello_lang
```
''')


def generate(lang, outdir, verbose=True):
    """Write the standalone toolkit for lang into outdir. Returns file list."""
    os.makedirs(outdir, exist_ok=True)
    header = string.Template(_GENERATED_HEADER).substitute(lang_name=lang.name)
    interpreter_name = lang.slug + "_interpreter.py"

    artifacts = {
        interpreter_name: _INTERPRETER_TEMPLATE.substitute(
            lang_name=lang.name, slug=lang.slug, ext=lang.extension[1:], header=header,
            interpreter=interpreter_name,
            token_map=repr(lang.token_to_bf), bf_core=_BF_CORE),
        "converter.py": _CONVERTER_TEMPLATE.substitute(
            lang_name=lang.name, slug=lang.slug, ext=lang.extension[1:], header=header,
            bf_to_token=repr(lang.bf_to_token), token_map=repr(lang.token_to_bf)),
        "brainfuck_interpreter.py": _BF_INTERPRETER_TEMPLATE.substitute(header=header, bf_core=_BF_CORE),
    }

    hello_bf = TESTS[0][1]
    hello_lang = bf_to_lang(hello_bf, lang.bf_to_token)
    table = "\n".join(
        "| `%s` | `%s` | %s |" % (sym, _md_escape_token(lang.bf_to_token[sym]), desc)
        for sym, desc in COMMANDS)
    artifacts["README.md"] = _README_TEMPLATE.substitute(
        lang_name=lang.name, slug=lang.slug, ext=lang.extension[1:],
        wiki_url=WIKI_URL, table=table,
        interpreter=interpreter_name, hello_bf=hello_bf, hello_lang=hello_lang)
    artifacts["hello_world.bf"] = hello_bf + "\n"
    artifacts["hello_world" + lang.extension] = hello_lang + "\n"

    written = []
    for name, content in artifacts.items():
        path = os.path.join(outdir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(path)

    tests_dir = os.path.join(outdir, "tests")
    os.makedirs(tests_dir, exist_ok=True)
    for tname, bf_src, _data, _expected in TESTS:
        bf_path = os.path.join(tests_dir, tname + ".bf")
        lang_path = os.path.join(tests_dir, tname + lang.extension)
        with open(bf_path, "w", encoding="utf-8") as fh:
            fh.write(bf_src + "\n")
        with open(lang_path, "w", encoding="utf-8") as fh:
            fh.write(bf_to_lang(bf_src, lang.bf_to_token) + "\n")
        written += [bf_path, lang_path]

    if verbose:
        print("Generated %s toolkit in %s:" % (lang.name, outdir))
        for path in written:
            print("  %s" % path)
        print()
        print("Try it:")
        print("  python3 %s %s" % (os.path.join(outdir, interpreter_name),
                                   os.path.join(outdir, "hello_world" + lang.extension)))
    return written


# ---------------------------------------------------------------------------
# Built-in verification suite
# ---------------------------------------------------------------------------

# (name, brainfuck source, input bytes, expected output bytes)
TESTS = [
    ("hello_world",
     "++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]>>.>---.+++++++..+++.>>.<-.<.+++.------.--------.>>+.>++.",
     b"", b"Hello World!\n"),
    ("add",
     "++>+++[<+>-]<++++++++++++++++++++++++++++++++++++++++++++++++.",
     b"", b"5"),
    ("add_input",
     ",>,[<+>-]<------------------------------------------------.",
     b"23", b"5"),
    ("echo", ",[.,]", b"Meow!\n", b"Meow!\n"),
    ("alphabet",
     "++++++++++++++++++++++++++>+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++<[>.+<-]",
     b"", b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    ("multiply", "++++++>+++++++++++<[->[->+>+<<]>>[-<<+>>]<<<]>>.", b"", b"B"),
    ("wrap_down", "-.", b"", b"\xff"),
    ("wrap_up", "+" * 256 + ".", b"", b"\x00"),
]


def _run_tool(script, args, data, timeout=30):
    """Run a generated script; return (ok, stdout_bytes, detail)."""
    try:
        proc = subprocess.run(
            [sys.executable, script] + args,
            input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, b"", "timed out after %ss" % timeout
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip() or "exit code %d" % proc.returncode
        return False, proc.stdout, detail
    return True, proc.stdout, ""


def verify(lang, outdir, verbose=True):
    """Generate the toolkit, then check every built-in test end to end.

    Each test runs three ways: native bf on the generated bf interpreter,
    converted lang program on the generated lang interpreter, and the
    round-trip (lang -> bf) on the generated bf interpreter again.
    Returns True when everything passes.
    """
    generate(lang, outdir, verbose=False)
    interp = os.path.join(outdir, lang.slug + "_interpreter.py")
    bf_interp = os.path.join(outdir, "brainfuck_interpreter.py")
    converter = os.path.join(outdir, "converter.py")
    tests_dir = os.path.join(outdir, "tests")

    if verbose:
        print("Verifying %s (toolkit in %s)" % (lang.name, outdir))
    all_ok = True
    checks = 0
    for tname, bf_src, data, expected in TESTS:
        bf_path = os.path.join(tests_dir, tname + ".bf")
        lang_path = os.path.join(tests_dir, tname + lang.extension)
        rt_path = os.path.join(tests_dir, tname + ".roundtrip.bf")
        results = []

        ok, out, detail = _run_tool(bf_interp, [bf_path], data)
        ok = ok and out == expected
        results.append(("bf", ok, out, detail))

        ok, out, detail = _run_tool(interp, [lang_path], data)
        ok = ok and out == expected
        results.append(("lang", ok, out, detail))

        conv_ok, _out, conv_detail = _run_tool(converter, ["to-bf", lang_path, "-o", rt_path], b"")
        if conv_ok:
            ok, out, detail = _run_tool(bf_interp, [rt_path], data)
            ok = ok and out == expected
        else:
            ok, out, detail = False, b"", conv_detail
        results.append(("roundtrip", ok, out, detail))

        checks += len(results)
        test_ok = all(ok for _label, ok, _out, _detail in results)
        all_ok = all_ok and test_ok
        if verbose:
            marks = "  ".join("%s: %s" % (label, "PASS" if ok else "FAIL")
                              for label, ok, _out, _detail in results)
            print("  %-12s %s" % (tname, marks))
            for label, ok, out, detail in results:
                if not ok:
                    print("      %s expected %r, got %r%s"
                          % (label, expected, out, (" (%s)" % detail) if detail else ""))
    if verbose:
        print("%s (%d checks)" % ("ALL TESTS PASSED" if all_ok else "FAILURES DETECTED", checks))
    return all_ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_program(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _run_with_input(code, args):
    """Run code, reading stdin lazily only when the ',' command executes."""
    if getattr(args, "input", None) is not None:
        return run_bf(code, args.input.encode("utf-8"))
    return run_bf(code, input_iter=_stdin_bytes())


def _write_out(text, out_path):
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="bf_converter.py",
        description="Trivial brainfuck substitution generator: define 8 replacement "
                    "tokens in Markdown, get a working interpreter, converters, and tests.",
        epilog="Reference: " + WIKI_URL)
    ap.add_argument("--version", action="version", version="bf_converter " + __version__)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="interactively create a language definition Markdown file")
    p.add_argument("output", nargs="?", help="output .md path (default: <language_slug>.md)")
    p.add_argument("--force", action="store_true", help="overwrite an existing file without asking")

    p = sub.add_parser("template", help="write a fill-in Markdown template (usable as-is)")
    p.add_argument("output", nargs="?", default="language_template.md", help="output path")

    p = sub.add_parser("generate", help="generate interpreter, converters, and docs from a definition")
    p.add_argument("lang_md", help="language definition Markdown file")
    p.add_argument("-o", "--output", help="output directory (default: generated/<slug>)")

    p = sub.add_parser("convert", help="convert a program between brainfuck and the new language")
    p.add_argument("lang_md", help="language definition Markdown file")
    p.add_argument("input", help="program file to convert")
    p.add_argument("--to", choices=["lang", "bf"], required=True, help="conversion direction")
    p.add_argument("-o", "--output", help="output file (default: stdout)")

    p = sub.add_parser("run", help="run a program written in the new language")
    p.add_argument("lang_md", help="language definition Markdown file")
    p.add_argument("program", help="program file written in the new language")
    p.add_argument("--input", help="input bytes for the ',' command (default: read stdin)")

    p = sub.add_parser("run-bf", help="run a native brainfuck program")
    p.add_argument("program", help="brainfuck program file")
    p.add_argument("--input", help="input bytes for the ',' command (default: read stdin)")

    p = sub.add_parser("verify", help="generate the toolkit and run the built-in test suite")
    p.add_argument("lang_md", help="language definition Markdown file")
    p.add_argument("-o", "--output", help="output directory (default: generated/<slug>)")

    args = ap.parse_args(argv)

    try:
        if args.command == "init":
            wizard(args.output, args.force)
        elif args.command == "template":
            if os.path.exists(args.output):
                raise LanguageError("%s already exists; remove it or choose another path" % args.output)
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(TEMPLATE_MD)
            print("Wrote %s — edit the tokens, then: python3 bf_converter.py generate %s"
                  % (args.output, args.output))
        elif args.command == "generate":
            lang = load_language(args.lang_md)
            outdir = args.output or os.path.join("generated", lang.slug)
            generate(lang, outdir)
        elif args.command == "convert":
            lang = load_language(args.lang_md)
            source = _read_program(args.input)
            if args.to == "lang":
                result = bf_to_lang(source, lang.bf_to_token)
            else:
                result = lang_to_bf(source, lang.token_to_bf)
            _write_out(result + "\n", args.output)
        elif args.command == "run":
            lang = load_language(args.lang_md)
            code = tokenize(_read_program(args.program), lang.token_to_bf)
            sys.stdout.buffer.write(_run_with_input(code, args))
        elif args.command == "run-bf":
            code = bf_filter(_read_program(args.program))
            sys.stdout.buffer.write(_run_with_input(code, args))
        elif args.command == "verify":
            lang = load_language(args.lang_md)
            outdir = args.output or os.path.join("generated", lang.slug)
            if not verify(lang, outdir):
                return 1
    except (LanguageError, BFError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except OSError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
