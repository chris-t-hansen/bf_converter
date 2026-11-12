<!--
Language definition template for bf_converter.py.
1. Replace 'MyLanguage' below with your language's name.
2. Replace each token in the second column with your own command.
   Tokens may be words, symbols, or phrases containing spaces
   (like Ook!'s 'Ook. Ook?'). They must be unique, single-line,
   and are case-sensitive. Anything in a program that is not a
   token is ignored, so you can freely add comments.
3. Run: python3 bf_converter.py generate this_file.md
-->

# MyLanguage

A [Trivial brainfuck substitution](https://esolangs.org/wiki/Trivial_brainfuck_substitution): each brainfuck command is
replaced by the token below. All other text in a program is ignored.

## Commands

| Brainfuck | MyLanguage | Description |
| --- | --- | --- |
| `>` | right | Move the data pointer one cell to the right |
| `<` | left | Move the data pointer one cell to the left |
| `+` | plus | Increment the byte in the current cell (255 wraps to 0) |
| `-` | minus | Decrement the byte in the current cell (0 wraps to 255) |
| `.` | print | Output the byte in the current cell as a character |
| `,` | read | Read one byte of input into the current cell (end of input stores 0) |
| `[` | open | If the current byte is 0, jump forward past the matching ] |
| `]` | close | If the current byte is not 0, jump back to the matching [ |

## Semantics

- Cells are 8-bit bytes: `+` wraps 255 to 0, `-` wraps 0 to 255.
- The tape starts at one cell and grows to the right; moving left of
  the first cell is an error.
- `,` reads one byte of input; at end of input it stores 0.
- `.` writes the current byte to standard output.
