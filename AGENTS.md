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
- `examples/` — example definitions: `pirate.md` (PirateScript),
  `hello_world_fuck.md` (Hello World Fuck — every token starts with
  "Hello World"; shared prefixes are safe, no token is a prefix of another),
  `dog_speak.md` (dog speak — wizard-created, every token is a dog sound,
  extension `.ds`), and `corporate.md` (CorporateFuck — every token is
  corporate jargon, extension `.corp`).
- `programs/*.bf` — sample brainfuck programs; generated from `TESTS` (the
  single source of truth). If you change `TESTS`, regenerate these.
- `tests/test_bf_converter.py` — unittest suite (unit + subprocess end-to-end).
- `EXTRAS.md` — ideas backlog with design sketches and statuses; update the
  status entry when a feature ships.
- `generated/` — gitignored output of `generate`/`verify`; safe to delete.
  At the default output root, `generate`/`verify` also (re)write
  `generated/README.md` describing the folder and the test suite (built
  from `TESTS` + `TEST_INFO` — keep the two in sync). Custom `-o` targets
  never write a README outside the chosen directory.

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
- **CLI input is lazy**: `run_bf(..., input_iter=_stdin_bytes())` reads stdin
  one byte at a time, only when `,` executes. Never read all of stdin up front
  — that hung interactive terminals even for programs without `,` (a past bug;
  regression tests keep an open stdin pipe and require the process to finish).
- **Tokenizer**: longest-match-first scan over the raw program text; tokens
  may contain spaces (Ook! style); non-token characters are comments; tokens
  are case-sensitive. `validate_tokens` rejects empty/duplicate/multiline
  tokens; prefix collisions are a warning, not an error.
- **Markdown parsing** must keep accepting: 3-column tables with backticked
  and backslash-escaped symbols (`\>`, `\[`, `\]`), 2-column tables, reordered
  columns, extra description columns, `Name:` lines, the `` `>` = token ``
  line fallback, and an optional `Extension: .hwf` line (validated by
  `clean_extension`; absent → slug default, for backward compatibility).
  `render_language_md` output must always re-parse to the same language,
  including its extension (roundtrip test). Tokens containing `|` are escaped
  as `\|`.
- **File extension**: `Language.extension` (custom or slug-based) applies to
  *program files only* — generated demos, tests, and doc examples (`$ext` in
  templates). The toolkit directory and `<slug>_interpreter.py` keep the name
  slug. Wizard flow: name → extension → 8 tokens.
- **Random generator**: `THEMES` banks (names / extensions / token pools) +
  `random_language(theme, name, seed)` — seeded for reproducibility, redraws
  on prefix collisions; CLI `init --random/--theme/--name/--seed/--list-themes`.
  `brag_sheet(lang)` computes token-utterance stats from `TESTS` and is
  printed at the end of `verify`.
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
- Every example's embedded Hello World block must stay equal to
  `bf_to_lang(TESTS[0][1], its_mapping)` — enforced by `TestExamples`;
  regenerate the blocks if `TESTS` change.
- The main README's built-in test table must stay in sync with `TESTS` +
  `TEST_INFO` — enforced by `TestReadmeDocs`; regenerate it from
  `bc.test_table_rows()` if `TESTS` change.
