# bf_converter — Trivial brainfuck substitution generator

Automates the creation of languages from the
[Trivial brainfuck substitution](https://esolangs.org/wiki/Trivial_brainfuck_substitution)
family (Ook!, Alphuck, Pewlang, …): you pick 8 replacement tokens for the 8
brainfuck commands, and this tool turns that definition into a working
language — interpreter, converters, documentation, and a verification suite.

Pure Python standard library, no dependencies, Python 3.8+.

## What it does

1. **Generates the new language** — a standalone interpreter written in Python
   that runs programs using your tokens.
2. **Converts brainfuck → your language** — any brainfuck program.
3. **Converts your language → brainfuck** — the reverse direction.
4. **Verifies everything** — runs Hello World, addition (with and without
   input), echo, alphabet, multiplication, and cell-wrap tests through the
   generated tools and checks the outputs.
5. **Creates the definition file for you** — an interactive wizard that asks
   what each of the 8 commands should be and explains what each one does.

It also generates a **standalone brainfuck interpreter** for checking native
brainfuck programs, and ships a **fill-in Markdown template**
([templates/language_template.md](templates/language_template.md)).

## Quickstart

### Option A — let the wizard build your definition

```sh
python3 bf_converter.py init
```

You'll be asked for a language name, then for a replacement token for each
command (with an explanation of what the command does and a sensible default):

```text
  >  —  Move the data pointer one cell to the right.
    Replacement for '>' [right]: starboard
  ...
```

### Option B — copy the template and edit it

```sh
python3 bf_converter.py template my_language.md
# edit the tokens in my_language.md, then:
python3 bf_converter.py generate my_language.md
```

### Option C — try the bundled examples

```sh
python3 bf_converter.py verify examples/pirate.md
python3 generated/piratescript/piratescript_interpreter.py \
    generated/piratescript/hello_world.piratescript
# -> Hello World!

# Or HelloWorldFuck, where every command begins with "Hello World":
python3 bf_converter.py verify examples/helloworldfuck.md
```

## The definition file

A Markdown file with the language name as its heading and a chart mapping the
8 brainfuck commands to your tokens (see
[examples/pirate.md](examples/pirate.md)):

```markdown
# PirateScript

| Brainfuck | PirateScript | Description |
| --- | --- | --- |
| `>` | starboard | Move the data pointer one cell to the right |
| `<` | port | Move the data pointer one cell to the left |
| `+` | hoist | Increment the byte in the current cell |
| `-` | lower | Decrement the byte in the current cell |
| `.` | shout | Output the byte in the current cell |
| `,` | parrot | Read one byte of input into the current cell |
| `[` | ahoy | Jump past the matching ] if the cell is 0 |
| `]` | avast | Jump back to the matching [ if the cell is not 0 |
```

The parser is flexible: column order doesn't matter, extra columns (like
Description) are fine, backticks and Markdown escapes (`\>`, `\[`) are handled,
and a simple `` `>` = starboard `` line format works as a fallback.

**Token rules**

- Tokens must be unique, single-line, and non-empty; they are case-sensitive.
- Tokens may contain spaces — Ook!'s `Ook. Ook?` style works. Matching is
  longest-first, so a token may be a prefix of another (you'll get a warning).
- Anything in a program that is not part of a token is ignored, so you can
  comment freely — exactly like non-command characters in brainfuck.

## CLI reference

| Command | Purpose |
| --- | --- |
| `init [out.md] [--force]` | Interactive wizard: create a language definition |
| `template [out.md]` | Write the fill-in template (valid as-is with default tokens) |
| `generate LANG.md [-o DIR]` | Generate the toolkit (default: `generated/<slug>/`) |
| `convert LANG.md FILE --to lang\|bf [-o OUT]` | Convert a program either direction |
| `run LANG.md PROGRAM [--input TEXT]` | Run a program in the new language |
| `run-bf PROGRAM [--input TEXT]` | Run a native brainfuck program |
| `verify LANG.md [-o DIR]` | Generate the toolkit and run all built-in tests |

Without `--input`, program input (the `,` command) is read from stdin.
Without `-o`, conversion output goes to stdout.

## What `generate` produces

Inside `generated/<slug>/`:

| File | Purpose |
| --- | --- |
| `<slug>_interpreter.py` | Standalone interpreter for your language (`-c CODE` for inline programs) |
| `converter.py` | Standalone `to-lang` / `to-bf` converter |
| `brainfuck_interpreter.py` | Standalone brainfuck interpreter |
| `README.md` | Your language's documentation, with a Hello World in both languages |
| `hello_world.bf`, `hello_world.<slug>` | Ready-to-run demo |
| `tests/` | All verification programs in both languages |

Every generated file is self-contained (stdlib only) — share the folder and
anyone can run your language without this tool.

## Semantics

- Cells are 8-bit bytes: `+` wraps 255 → 0, `-` wraps 0 → 255.
- The tape starts at one cell and grows to the right; moving left of the first
  cell is an error.
- `,` reads one byte; at end of input it stores 0 (so `,[.,]` cat programs
  terminate).
- `.` writes the raw byte to stdout.
- Unmatched brackets are errors.

## Sample programs

[programs/](programs/) contains the built-in test programs as plain brainfuck
(`hello_world.bf`, `add.bf`, `add_input.bf`, `echo.bf`, `alphabet.bf`,
`multiply.bf`, `wrap_down.bf`, `wrap_up.bf`). `add_input.bf` adds two
single-digit numbers read from input (sum must be ≤ 9):

```sh
printf 23 | python3 bf_converter.py run-bf programs/add_input.bf   # -> 5
```

## Development

```sh
python3 -m unittest discover -s tests -v   # 52 tests, incl. subprocess end-to-end
```

See [AGENTS.md](AGENTS.md) for architecture notes.
