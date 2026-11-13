# EXTRAS.md — idea backlog & design sketches

The core tool is complete and well-tested; everything here is **optional
dessert**. This file is the project's ideas/skills backlog: each entry has a
status, a design sketch concrete enough to implement from, and an effort
estimate (S = an hour-ish, M = an afternoon, L = multi-day).

Status legend: ✅ shipped · 🚧 in progress · 💡 planned · ⏸️ deferred by owner

When a feature ships, update its status here and note the commit.

---

## 1. Random / themed language generator — ✅ shipped

`init --random [--theme THEME] [--name NAME] [--seed N]` generates a complete
language definition non-interactively from themed word banks; `--list-themes`
shows the themes. `--seed` makes results reproducible (used by tests).

- Themes: corporate, cat, dog, food, pirate, genz, emoji, shakespeare.
- Each theme: name pool (e.g. CorporateFuck, SynergyScript), short extension
  pool (e.g. `.corp`), and a token pool of ≥ 8 words/phrases.
- Draw 8 distinct tokens; reject draws with prefix collisions and redraw.
- Writes the same `render_language_md` output as the wizard; refuses to
  overwrite without `--force`.
- Effort: S. Delight: maximum.

## 2. Famous programs gallery — ✅ shipped

Bundle classic brainfuck programs (99 Bottles of Beer, FizzBuzz, Mandelbrot,
Towers of Hanoi) under `programs/famous/`, converted into every example
language via the `gallery` command. Doubles as a heavy stress test
(Mandelbrot exercises everything). Sources verified with `run-bf` before
bundling; attribution and licensing in `programs/famous/README.md`.
Shipped notes: hanoi is Roland Illig's GPL 3-disk version (German output);
Mandelbrot takes several minutes, so its full-output test is opt-in via
`BF_SLOW_TESTS=1` with reference output in `mandelbrot_expected.txt`.

### 2b. Owner's spin: famous programs AS commands — ✅ shipped

Shipped as the **FamousFuck** example (`examples/famous.md`): the 8 commands
are named after famous programs (Hello World, FizzBuzz, Towers of Hanoi,
Mandelbrot, 99 Bottles of Beer, Game of Life, Quine, Turing Machine), per the
owner's direction. The full **macro expansion** (a token running an entire
program, tape-isolated) is now also shipped as the self-contained `macros/`
companion (`macros/macro_lang.py`), kept in its own folder so the core layout
stays untouched.

## 3. Esolangs wiki export — ✅ shipped

`export LANG.md --wiki` renders the exact esolangs.org format: the
`TrivialBrainfuckSubstitution("a","b","c","d","e","f","g","h")` declaration
plus the standard `| Brainfuck | Substitution Argument | Description |`
chart, ready to paste into a new wiki page. Reference:
https://esolangs.org/wiki/Trivial_brainfuck_substitution — effort S,
gives the community a one-command contribution path.

## 4. Poetry mode conversion — ✅ shipped

`convert --to lang --flavor [THEME]` sprinkles themed comment prose between
tokens. Non-token text is ignored by design, so the output is a readable
story that still runs. Prose banks (`FLAVOR`) are separate from the token
pools; every fragment is substring-checked against the active tokens and the
finished text is re-tokenized to prove it equals the original program
(catches boundary-spanning matches). Unsafe token sets fall back to plain
tokens with a warning. Deterministic — no LLM needed. Effort: S.

## 5. Silly statistics (brag sheet) — ✅ shipped

`verify` ends with a brag sheet computed from the test suite: per-token
utterance counts across all 8 programs, total tokens, total output bytes,
tokens-per-byte "efficiency", and the most-uttered command
("the suite is 70% bark"). Pure function `brag_sheet(lang)` over `TESTS`;
no runtime measurement needed. Effort: S.

## 6. Sequence idioms (BF-RLE) — ✅ shipped

The esolangs page notes many family members replace common *sequences* with
one token (`[-]` → "clear", `[->+<]` → "move"). Design: optional second chart
in the md (`| Sequence | Token |`); `token_to_bf` values become multi-command
strings (the longest-match tokenizer already supports this); bf→lang
conversion greedily matches known idioms before falling back to single
commands. Round-trip tests must cover idiom overlap. Effort: M.
Prerequisite for #2b.

## 7. REPL — ✅ shipped

`repl LANG.md`: interactive prompt accepting tokens or bf, with a live tape
view (cell window around the pointer), persistent state between lines,
`:reset`, `:tape`, `:help`. Reuse `run_bf` with a step hook or run each line
as a program fragment against a persistent tape. Effort: M.

## 8. Debug / trace mode — ✅ shipped

`run --trace` / `--step N`: print the tape window and pointer after each
command (or every N commands), optionally to stderr so output stays clean.
Hypnotic with dog sounds. Effort: M (needs a step callback in `run_bf`,
kept in sync between core and `_BF_CORE`).

## 9. Practical growth — ✅ shipped

- pip/pipx packaging (`pyproject.toml`, console entry point `bf-converter`).
- Configurable semantics for bf purists: cell size (8/16/32-bit), EOF
  behavior (0 / −1 / unchanged), fixed vs growing tape. Must stay consistent
  across core, `_BF_CORE`, docs, and tests (see AGENTS.md).
- GALLERY.md or GitHub Pages showcasing community languages.

## 10. Party tricks (already work today) — ✅ no effort needed

- **Language laundering**: chain converters pirate → dog speak →
  Hello World Fuck; semantics survive every hop.
- **Programs as prose**: any non-token text is a comment, so a love letter
  where only the dog sounds matter is a valid program.

## 11. Per-language tape configuration — ✅ shipped

Language definitions can set `Tape-Cells:` (default 30,000 — the classic
brainfuck tape size) and `Cell-Bits:` (default 8; allowed 8/16/32). The wizard
asks for both; the values are baked into the generated interpreter and used
by `run` (CLI flags override). The tape is fixed-size with a wrapping pointer.
The native `run-bf` engine keeps its growing-tape default, so existing
behavior is unchanged. Requested by the owner after the macro work.
