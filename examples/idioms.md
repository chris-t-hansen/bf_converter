# ShortcutScript

A [Trivial brainfuck substitution](https://esolangs.org/wiki/Trivial_brainfuck_substitution): each brainfuck command is
replaced by the token below. All other text in a program is ignored.

Extension: .short

## Commands

| Brainfuck | ShortcutScript | Description |
| --- | --- | --- |
| `>` | right | Move the data pointer one cell to the right |
| `<` | left | Move the data pointer one cell to the left |
| `+` | plus | Increment the byte in the current cell (255 wraps to 0) |
| `-` | minus | Decrement the byte in the current cell (0 wraps to 255) |
| `.` | print | Output the byte in the current cell as a character |
| `,` | read | Read one byte of input into the current cell (end of input stores 0) |
| `[` | open | If the current byte is 0, jump forward past the matching ] |
| `]` | close | If the current byte is not 0, jump back to the matching [ |

## Idioms

Sequence shortcuts: when converting brainfuck into this language,
the longest matching sequence becomes its shortcut token.

| Sequence | ShortcutScript |
| --- | --- |
| `[-]` | clear |
| `[->+<]` | move |

## Semantics

- Cells are 8-bit bytes: `+` wraps 255 to 0, `-` wraps 0 to 255.
- The tape starts at one cell and grows to the right; moving left of
  the first cell is an error.
- `,` reads one byte of input; at end of input it stores 0.
- `.` writes the current byte to standard output.

## Example

Hello World (no idioms needed), plus a shortcut demo: 65 `plus` commands
followed by `[->+<]>.` become `move right print` — the whole copy-loop is
one word, and it prints `A`.

```text
plus plus plus plus plus plus plus plus open right plus plus plus plus open right plus plus right plus plus plus right plus plus plus right plus left left left left minus close right plus right plus right minus right right plus open left close left minus close right right print right minus minus minus print plus plus plus plus plus plus plus print print plus plus plus print right right print left minus print left print plus plus plus print minus minus minus minus minus minus print minus minus minus minus minus minus minus minus print right right plus print right plus plus print
```

## Try it

```sh
python3 bf_converter.py generate examples/idioms.md
python3 bf_converter.py verify examples/idioms.md
python3 generated/shortcutscript/shortcutscript_interpreter.py \
    generated/shortcutscript/hello_world.short
```
