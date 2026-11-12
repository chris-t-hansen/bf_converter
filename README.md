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

You'll be asked for a language name, a **file extension** for your programs
(e.g. `hwf` — defaults to the name slug), then for a replacement token for
each command (with an explanation of what the command does and a sensible
default):

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

# Or Hello World Fuck, where every command begins with "Hello World":
python3 bf_converter.py verify examples/hello_world_fuck.md

# Or dog speak, where every command is a dog sound (.ds files):
python3 bf_converter.py verify examples/dog_speak.md

# Or CorporateFuck, where every command is a meeting that could have been an email:
python3 bf_converter.py verify examples/corporate.md
```

### Option D — surprise me

```sh
python3 bf_converter.py init --list-themes        # corporate, cat, dog, emoji, ...
python3 bf_converter.py init --random --theme corporate
python3 bf_converter.py init --random --seed 42   # a reproducible surprise
```

The random generator draws a name, a short extension, and 8 collision-free
tokens from themed word banks and writes a ready-to-verify definition file.

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

An optional `Extension: .hwf` line anywhere in the file sets the **file
extension for programs** in your language (letters, digits, dots, hyphens,
underscores; no spaces). Without it, the extension defaults to the name slug
(e.g. `.piratescript`). The toolkit directory and interpreter filename always
use the name slug — only program files use the chosen extension.

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
| `init --random [--theme T] [--name N] [--seed S]` | Generate a random themed language (`--list-themes` to browse) |
| `template [out.md]` | Write the fill-in template (valid as-is with default tokens) |
| `generate LANG.md [-o DIR]` | Generate the toolkit (default: `generated/<slug>/`) |
| `convert LANG.md FILE --to lang\|bf [--flavor [THEME]] [-o OUT]` | Convert a program either direction; `--flavor` weaves in ignored prose |
| `export LANG.md [--wiki] [-o OUT]` | Paste-ready esolangs.org wiki markup for your language |
| `gallery LANG.md [-o DIR]` | Convert the famous programs gallery into your language |
| `run LANG.md PROGRAM [--input TEXT]` | Run a program in the new language |
| `run-bf PROGRAM [--input TEXT]` | Run a native brainfuck program |
| `verify LANG.md [-o DIR]` | Generate the toolkit and run all built-in tests |

Without `--input`, input for the `,` command is read from stdin **on demand** —
only when `,` actually executes. Programs without input never touch stdin, so
they run fine on interactive terminals; for input programs, type the input and
signal end-of-input (Ctrl-D on Linux/macOS, Ctrl-Z on Windows) or use `--input`.
Without `-o`, conversion output goes to stdout.

`verify` ends with a **brag sheet**: how many times your language uttered each
token across the test suite, total tokens per output byte, and its favorite
command.

### Poetry mode

`convert --to lang --flavor [THEME]` weaves the token stream into themed
prose — a corporate email, a pirate letter, a Shakespearean note — that the
interpreter ignores. No LLM needed: it's a deterministic formatter. Every
prose fragment is checked against your token set (substring-exact), and the
finished text is re-tokenized to prove it still equals the original program;
if nothing is safe, it falls back to plain tokens with a warning. Themes:
corporate, pirate, shakespeare, cat, dog, genz, food — omit the theme value
to auto-match your language.

```sh
python3 bf_converter.py convert examples/corporate.md programs/hello_world.bf \
    --to lang --flavor corporate -o email.corp
python3 generated/corporatefuck/corporatefuck_interpreter.py email.corp
# -> Hello World!  (the email is the program)
```

### Wiki export

`export LANG.md` renders paste-ready [esolangs.org](https://esolangs.org/wiki/Trivial_brainfuck_substitution)
markup — the `TrivialBrainfuckSubstitution(...)` declaration and the standard
command chart — so you can contribute your language to the wiki in one paste.

### Famous programs gallery

`gallery LANG.md` converts four verified classics — **99 Bottles of Beer**,
**FizzBuzz**, **Towers of Hanoi**, and the **Mandelbrot set** — into your
language (default output: `generated/<slug>/famous/`). Sources and attribution
live in [programs/famous/](programs/famous/); every program was checked against
its canonical output before bundling.

```sh
python3 bf_converter.py gallery examples/dog_speak.md
python3 generated/dog_speak/dog_speak_interpreter.py generated/dog_speak/famous/bottles.ds
```

Mandelbrot is the heavyweight: it takes about 25 minutes on this interpreter.
Its full-output test is opt-in via `BF_SLOW_TESTS=1`.

## What `generate` produces

Inside `generated/<slug>/`:

| File | Purpose |
| --- | --- |
| `<slug>_interpreter.py` | Standalone interpreter for your language (`-c CODE` for inline programs) |
| `converter.py` | Standalone `to-lang` / `to-bf` converter |
| `brainfuck_interpreter.py` | Standalone brainfuck interpreter |
| `README.md` | Your language's documentation, with a Hello World in both languages |
| `hello_world.bf`, `hello_world.<ext>` | Ready-to-run demo (`<ext>` = your chosen extension) |
| `tests/` | All verification programs in both languages |

Every generated file is self-contained (stdlib only) — share the folder and
anyone can run your language without this tool.

When you use the default output location, a `generated/README.md` is also
(re)written explaining the folder layout and what each built-in test does,
with its input and expected output.

### The built-in test suite

`verify` runs each program below **three ways** and compares the output: on
the generated brainfuck interpreter, on your language's interpreter, and
converted back to brainfuck again (8 programs × 3 paths = 24 checks). The
same programs are saved to `tests/` in both languages.

| Test | What it does | Input | Expected output |
| --- | --- | --- | --- |
| `hello_world` | The classic Hello World — nested loops build each character, then print it. | none | `Hello World!\n` |
| `add` | Adds 2 + 3 without input, converts the result to ASCII, and prints the digit 5. | none | `5` |
| `add_input` | Reads two single-digit characters, adds them, and prints the sum as a digit (sum must be 9 or less). | `23` | `5` |
| `echo` | Cat program: echoes input back until end of input, where ',' stores 0 and the loop ends. | `Meow!\n` | `Meow!\n` |
| `alphabet` | Prints A through Z using a counter cell and an incrementing character cell. | none | `ABCDEFGHIJKLMNOPQRSTUVWXYZ` |
| `multiply` | Multiplies 6 x 11 with nested copy-loops and prints the result byte as a character (B). | none | `B` |
| `wrap_down` | Cell underflow: decrements 0, which wraps to 255, and prints byte 0xFF. | none | 0xFF |
| `wrap_up` | Cell overflow: increments 256 times, wrapping back to 0, and prints byte 0x00. | none | 0x00 |

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
python3 -m unittest discover -s tests -v   # 93 tests, incl. subprocess end-to-end
```

See [AGENTS.md](AGENTS.md) for architecture notes.
