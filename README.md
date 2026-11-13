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
(e.g. `hwf` — defaults to the name slug), the **tape size** (default 30,000
cells) and **cell width** (default 8-bit), then for a replacement token for
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

# Or FamousFuck, where every command is named after a famous program:
python3 bf_converter.py verify examples/famous.md

# Or ShortcutScript, which adds sequence idioms ([-] = "clear"):
python3 bf_converter.py verify examples/idioms.md
```

See [GALLERY.md](GALLERY.md) for a showcase of all bundled languages.

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

Two more optional lines configure the machine: `Tape-Cells: 30000` (the number
of cells on the tape, default 30,000) and `Cell-Bits: 8` (the cell width —
8, 16, or 32, default 8). The tape is fixed-size with a pointer that wraps at
both ends. These are baked into the generated interpreter, and `run` uses
them too.

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
| `run LANG.md PROGRAM [--input TEXT] [options]` | Run a program in the new language |
| `run-bf PROGRAM [--input TEXT] [options]` | Run a native brainfuck program |
| `repl LANG.md` | Interactive REPL with a persistent tape |
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

### Macro languages

The [`macros/`](macros/) folder is a self-contained companion (the core tool
is untouched): a **macro language** replaces whole *programs* with tokens, so
writing `FizzBuzz` runs the entire FizzBuzz program. Each macro runs on its
own fresh tape, so `Hello World FizzBuzz` runs both cleanly, in order.

```sh
python3 macros/macro_lang.py run macros/examples/famous_macros.md -c "Hello World FizzBuzz"
python3 macros/macro_lang.py verify macros/examples/famous_macros.md
```

See [macros/README.md](macros/README.md) for the format and full CLI.

### Sequence idioms

A definition can include a second chart mapping **brainfuck sequences** to
shortcut tokens (BF-RLE style, like many esolangs family members):

```markdown
## Idioms

| Sequence | ShortcutScript |
| --- | --- |
| `[-]` | clear |
| `[->+<]` | move |
```

Converting brainfuck → your language matches the longest sequence first, so
`+++[-][->+<]` becomes `plus plus plus clear move`. Converting back expands
each idiom to its full sequence. Idiom tokens share the command namespace
(all tokens must be unique). See [examples/idioms.md](examples/idioms.md).

### REPL

```sh
python3 bf_converter.py repl examples/pirate.md
```

An interactive loop with a **persistent tape**: type tokens (or `:bf CODE`
for raw brainfuck) and watch the cells change. Commands: `:help`, `:reset`,
`:tape`, `:input TEXT` (queue bytes for `,`), `:bf CODE`, `:quit`. Errors
(like an unmatched bracket) leave the tape untouched.

### Execution options

`run` and `run-bf` accept the flags below. For `run`, the defaults come from
the language's `Tape-Cells:` / `Cell-Bits:` config; for `run-bf` (native bf)
the defaults are a growing tape and 8-bit cells. Explicit flags override either.

| Flag | Effect |
| --- | --- |
| `--trace` | Print a step trace to stderr (stdout stays clean) |
| `--trace-every N` | With `--trace`: trace every N steps |
| `--cell-bits 8\|16\|32` | Cell width (`.` emits the low byte) |
| `--eof zero\|minus-one\|keep` | `,` behavior at end of input |
| `--tape-size N` | Fixed tape of N cells with a wrapping pointer |

```sh
python3 bf_converter.py run-bf programs/hello_world.bf --trace --trace-every 20
```

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

These are the defaults; `run`/`run-bf` can override cell width, EOF behavior,
and tape size (see Execution options above). Generated interpreters use the
defaults.

## Sample programs

[programs/](programs/) contains the built-in test programs as plain brainfuck
(`hello_world.bf`, `add.bf`, `add_input.bf`, `echo.bf`, `alphabet.bf`,
`multiply.bf`, `wrap_down.bf`, `wrap_up.bf`). `add_input.bf` adds two
single-digit numbers read from input (sum must be ≤ 9):

```sh
printf 23 | python3 bf_converter.py run-bf programs/add_input.bf   # -> 5
```

## Party tricks

- **Language laundering**: chain converters across languages — pirate →
  dog speak → Hello World Fuck. Semantics survive every hop:

  ```sh
  python3 bf_converter.py convert examples/pirate.md programs/hello_world.bf --to lang -o a.piratescript
  python3 bf_converter.py convert examples/pirate.md a.piratescript --to bf -o b.bf
  python3 bf_converter.py convert examples/dog_speak.md b.bf --to lang -o c.ds
  python3 generated/dog_speak/dog_speak_interpreter.py c.ds   # -> Hello World!
  ```

- **Programs as prose**: any non-token text is a comment, so a love letter
  where only the dog sounds matter is a valid program. Poetry mode
  (`--flavor`) does this for you.

## Install as a command

The repo ships `pyproject.toml`, so you can install the CLI locally:

```sh
pipx install .        # or: pip install .
bf-converter --help
```

The installed command includes everything except the famous-program sources
(`gallery` needs the repo checkout; it says so if they're missing). Nothing
is published to PyPI — install from your clone.

## Development

```sh
python3 -m unittest discover -s tests -v   # 129 tests, incl. subprocess end-to-end
```

See [AGENTS.md](AGENTS.md) for architecture notes and [EXTRAS.md](EXTRAS.md)
for the ideas backlog (all shipped).
