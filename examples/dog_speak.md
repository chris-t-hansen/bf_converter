# dog speak

A [Trivial brainfuck substitution](https://esolangs.org/wiki/Trivial_brainfuck_substitution): each brainfuck command is
replaced by the token below. All other text in a program is ignored.

Extension: .ds

## Commands

| Brainfuck | dog speak | Description |
| --- | --- | --- |
| `>` | aarf | Move the data pointer one cell to the right |
| `<` | woof | Move the data pointer one cell to the left |
| `+` | bark | Increment the byte in the current cell (255 wraps to 0) |
| `-` | ruff | Decrement the byte in the current cell (0 wraps to 255) |
| `.` | bow-wow | Output the byte in the current cell as a character |
| `,` | grrr | Read one byte of input into the current cell (end of input stores 0) |
| `[` | arooo | If the current byte is 0, jump forward past the matching ] |
| `]` | yip | If the current byte is not 0, jump back to the matching [ |

## Semantics

- Cells are 8-bit bytes: `+` wraps 255 to 0, `-` wraps 0 to 255.
- The tape starts at one cell and grows to the right; moving left of
  the first cell is an error.
- `,` reads one byte of input; at end of input it stores 0.
- `.` writes the current byte to standard output.

## Example

Hello World, spoken like a dog — eight barks, then a howl:

```text
bark bark bark bark bark bark bark bark arooo aarf bark bark bark bark arooo aarf bark bark aarf bark bark bark aarf bark bark bark aarf bark woof woof woof woof ruff yip aarf bark aarf bark aarf ruff aarf aarf bark arooo woof yip woof ruff yip aarf aarf bow-wow aarf ruff ruff ruff bow-wow bark bark bark bark bark bark bark bow-wow bow-wow bark bark bark bow-wow aarf aarf bow-wow woof ruff bow-wow woof bow-wow bark bark bark bow-wow ruff ruff ruff ruff ruff ruff bow-wow ruff ruff ruff ruff ruff ruff ruff ruff bow-wow aarf aarf bark bow-wow aarf bark bark bow-wow
```

## Try it

```sh
python3 bf_converter.py generate examples/dog_speak.md
python3 bf_converter.py verify examples/dog_speak.md
python3 generated/dog_speak/dog_speak_interpreter.py \
    generated/dog_speak/hello_world.ds
```
