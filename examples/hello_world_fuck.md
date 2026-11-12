# Hello World Fuck

A [Trivial brainfuck substitution](https://esolangs.org/wiki/Trivial_brainfuck_substitution)
in which **every single command begins with "Hello World"**. Programs are
glorious walls of near-identical phrases; the Hello World program below says
"Hello World" 106 times in order to print `Hello World!` once. Peak brainfuck.

All tokens share a prefix but none is a prefix of another, so longest-match
tokenization resolves every position unambiguously — no warnings, no surprises.
As always, any text that is not part of a token is ignored.

Extension: .hwf

## Commands

| Brainfuck | Hello World Fuck | Description |
| --- | --- | --- |
| `>` | Hello World right | Move the data pointer one cell to the right |
| `<` | Hello World left | Move the data pointer one cell to the left |
| `+` | Hello World plus | Increment the byte in the current cell (255 wraps to 0) |
| `-` | Hello World minus | Decrement the byte in the current cell (0 wraps to 255) |
| `.` | Hello World print | Output the byte in the current cell as a character |
| `,` | Hello World read | Read one byte of input into the current cell (end of input stores 0) |
| `[` | Hello World open | If the current byte is 0, jump forward past the matching ] |
| `]` | Hello World close | If the current byte is not 0, jump back to the matching [ |

## Example

Hello World, the Hello World Fuck way:

```text
Hello World plus Hello World plus Hello World plus Hello World plus Hello World plus Hello World plus Hello World plus Hello World plus Hello World open Hello World right Hello World plus Hello World plus Hello World plus Hello World plus Hello World open Hello World right Hello World plus Hello World plus Hello World right Hello World plus Hello World plus Hello World plus Hello World right Hello World plus Hello World plus Hello World plus Hello World right Hello World plus Hello World left Hello World left Hello World left Hello World left Hello World minus Hello World close Hello World right Hello World plus Hello World right Hello World plus Hello World right Hello World minus Hello World right Hello World right Hello World plus Hello World open Hello World left Hello World close Hello World left Hello World minus Hello World close Hello World right Hello World right Hello World print Hello World right Hello World minus Hello World minus Hello World minus Hello World print Hello World plus Hello World plus Hello World plus Hello World plus Hello World plus Hello World plus Hello World plus Hello World print Hello World print Hello World plus Hello World plus Hello World plus Hello World print Hello World right Hello World right Hello World print Hello World left Hello World minus Hello World print Hello World left Hello World print Hello World plus Hello World plus Hello World plus Hello World print Hello World minus Hello World minus Hello World minus Hello World minus Hello World minus Hello World minus Hello World print Hello World minus Hello World minus Hello World minus Hello World minus Hello World minus Hello World minus Hello World minus Hello World minus Hello World print Hello World right Hello World right Hello World plus Hello World print Hello World right Hello World plus Hello World plus Hello World print
```

## Try it

```sh
python3 bf_converter.py generate examples/hello_world_fuck.md
python3 bf_converter.py verify examples/hello_world_fuck.md
python3 generated/hello_world_fuck/hello_world_fuck_interpreter.py \
    generated/hello_world_fuck/hello_world.hwf
```
