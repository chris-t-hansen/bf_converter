# CorporateFuck

A [Trivial brainfuck substitution](https://esolangs.org/wiki/Trivial_brainfuck_substitution):
the only language approved by absolutely no one's HR department. Every
command is a meeting that could have been an email. Programs read like a
quarterly review; the output is still just bytes.

Extension: .corp

## Commands

| Brainfuck | CorporateFuck | Description |
| --- | --- | --- |
| `>` | synergy | Move the data pointer one cell to the right |
| `<` | walk it back | Move the data pointer one cell to the left |
| `+` | circle back | Increment the byte in the current cell (255 wraps to 0) |
| `-` | deprioritize | Decrement the byte in the current cell (0 wraps to 255) |
| `.` | ping me | Output the byte in the current cell as a character |
| `,` | touch base | Read one byte of input into the current cell (end of input stores 0) |
| `[` | let's take this offline | If the current byte is 0, jump forward past the matching ] |
| `]` | per my last email | If the current byte is not 0, jump back to the matching [ |

## Example

Hello World, per my last email:

```text
circle back circle back circle back circle back circle back circle back circle back circle back let's take this offline synergy circle back circle back circle back circle back let's take this offline synergy circle back circle back synergy circle back circle back circle back synergy circle back circle back circle back synergy circle back walk it back walk it back walk it back walk it back deprioritize per my last email synergy circle back synergy circle back synergy deprioritize synergy synergy circle back let's take this offline walk it back per my last email walk it back deprioritize per my last email synergy synergy ping me synergy deprioritize deprioritize deprioritize ping me circle back circle back circle back circle back circle back circle back circle back ping me ping me circle back circle back circle back ping me synergy synergy ping me walk it back deprioritize ping me walk it back ping me circle back circle back circle back ping me deprioritize deprioritize deprioritize deprioritize deprioritize deprioritize ping me deprioritize deprioritize deprioritize deprioritize deprioritize deprioritize deprioritize deprioritize ping me synergy synergy circle back ping me synergy circle back circle back ping me
```

## Try it

```sh
python3 bf_converter.py generate examples/corporate.md
python3 bf_converter.py verify examples/corporate.md
python3 generated/corporatefuck/corporatefuck_interpreter.py \
    generated/corporatefuck/hello_world.corp
```
