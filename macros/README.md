# Macro languages

A companion to the core `bf_converter` tool, kept in its own folder so the
main project layout stays untouched. Nothing in `bf_converter.py` is
modified — this reuses its brainfuck engine.

## The idea

A Trivial brainfuck substitution replaces the **8 commands** with tokens.
A **macro language** replaces whole **programs** with tokens: writing
`FizzBuzz` runs the entire FizzBuzz program. A program is just a sequence of
program names:

```text
Hello World FizzBuzz
```

runs Hello World, then FizzBuzz, and concatenates their output.

## Tape isolation

Each macro runs on its **own fresh tape**. Famous programs assume they start
at cell 0 with a zeroed tape, so running them on a shared tape would let them
clobber each other. Isolation means `Hello World FizzBuzz` always behaves
exactly like running the two programs separately, in order.

## Usage

```sh
python3 macros/macro_lang.py list                 # programs usable as macros
python3 macros/macro_lang.py run macros/examples/famous_macros.md -c "Hello World"
python3 macros/macro_lang.py run macros/examples/famous_macros.md program.famousmacros
python3 macros/macro_lang.py generate macros/examples/famous_macros.md
python3 macros/macro_lang.py verify macros/examples/famous_macros.md
python3 macros/macro_lang.py template my_macros.md
```

`run` reads input for macros that use `,` from stdin (lazily) or `--input`.
`generate` writes a standalone, stdlib-only macro interpreter to
`generated/<slug>/`. `verify` checks each macro against its program's native
output and runs a composite; slow programs (Mandelbrot, ~25 min) are skipped
unless you pass `--slow`.

## Definition format

A Markdown file with a name heading and a `| Token | Program |` chart. The
Program column names bundled programs (see `list`); the Token column is what
you write in programs. Tokens may contain spaces and are matched
longest-first; non-token text is ignored.

```markdown
# MyMacros

| Token | Program |
| --- | --- |
| Hello World | hello_world |
| FizzBuzz | fizzbuzz |
```

## Where programs come from

Macros expand to the bundled brainfuck sources in `programs/famous/` (the
verified classics) and `programs/` (the built-in test programs). Add a new
`.bf` file there and it becomes available as a macro automatically.

## Tests

```sh
python3 -m unittest discover -s tests -v   # includes tests/test_macros.py
```
