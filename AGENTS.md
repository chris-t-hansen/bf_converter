# AGENTS.md

Guidance for AI agents working in this repository.

## Project

`bf_converter` automates the creation of
[Trivial brainfuck substitution](https://esolangs.org/wiki/Trivial_brainfuck_substitution)
languages: a Markdown definition (language name + chart of 8 replacement
tokens for the 8 brainfuck commands) is turned into a standalone Python
interpreter, bidirectional converters, a standalone brainfuck interpreter,
docs, and an end-to-end verification suite.

## Layout

- `bf_converter.py` — the entire tool, single file, stdlib only. Sections:
  bf core → tokenizer/conversion → Markdown parsing → Markdown rendering →
  wizard → generation templates (`string.Template`) → `TESTS` suite → CLI.
- `templates/language_template.md` — fill-in template; identical to
  `bc.TEMPLATE_MD` (regenerate with `python3 bf_converter.py template PATH`).
- `examples/pirate.md` — hand-written example definition (PirateScript).
- `programs/*.bf` — sample brainfuck programs; generated from `TESTS` (the
  single source of truth). If you change `TESTS`, regenerate these.
- `tests/test_bf_converter.py` — unittest suite (unit + subprocess end-to-end).
- `generated/` — gitignored output of `generate`/`verify`; safe to delete.

## Commands

```sh
python3 -m unittest discover -s tests -v      # full test suite (run from repo root)
python3 bf_converter.py verify examples/pirate.md   # end-to-end demo (24 checks)
python3 bf_converter.py --help
```

There is no build step, no dependency install, no linter config.

## Hard conventions

- **Python 3.8+ compatible, standard library only** — both the tool and every
  generated artifact. Generated files must never import `bf_converter` or
  anything outside the stdlib (a unit test enforces this).
- **Semantics are fixed and shared** by the core (`run_bf`) and all generated
  interpreters: 8-bit wrapping cells, tape grows right, pointer underflow is
  an error, `,` stores 0 at EOF, unmatched brackets are errors. If you change
  semantics, change `_BF_CORE` (used by generated files) **and** `run_bf`
  (used by the tool) together, plus the docs and `TESTS` expectations.
- **Tokenizer**: longest-match-first scan over the raw program text; tokens
  may contain spaces (Ook! style); non-token characters are comments; tokens
  are case-sensitive. `validate_tokens` rejects empty/duplicate/multiline
  tokens; prefix collisions are a warning, not an error.
- **Markdown parsing** must keep accepting: 3-column tables with backticked
  and backslash-escaped symbols (`\>`, `\[`, `\]`), 2-column tables, reordered
  columns, extra description columns, `Name:` lines, and the `` `>` = token ``
  line fallback. `render_language_md` output must always re-parse to the same
  language (roundtrip test). Tokens containing `|` are escaped as `\|`.
- **Templates** use `string.Template` (`$placeholders`). Every template that
  contains `$bf_core` must be substituted with `bf_core=_BF_CORE` — a missing
  kwarg raises `KeyError` at generation time. Generated code contains no `$`.
- `TESTS` entries are `(name, bf_source, input_bytes, expected_output_bytes)`.
  Input-dependent tests must pass their input bytes everywhere (a past bug).
  `verify` runs each test three ways via subprocess against the *generated*
  artifacts: native bf, converted lang, and lang→bf roundtrip.

## Pitfalls

- Run tests from the repo root: CLI tests use relative paths
  (`examples/pirate.md`, `programs/*.bf`).
- `bf_converter.py template` refuses to overwrite; `init` asks (or `--force`).
- The wizard reads via `input()`, so it can be driven by piped stdin; tests
  mock `builtins.input`.
- Don't hand-edit files in `generated/`; regenerate them.
- The pirate example's embedded Hello World block must stay equal to
  `bf_to_lang(TESTS[0][1], pirate_mapping)` — regenerate it if `TESTS` change.
