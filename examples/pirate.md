# PirateScript

A [Trivial brainfuck substitution](https://esolangs.org/wiki/Trivial_brainfuck_substitution)
for scallywags. Every brainfuck command is spoken like a pirate; all other
text is ignored, so ye can annotate yer programs with whatever commentary ye
like.

## Commands

| Brainfuck | PirateScript | Description |
| --- | --- | --- |
| `>` | starboard | Move the data pointer one cell to the right |
| `<` | port | Move the data pointer one cell to the left |
| `+` | hoist | Increment the byte in the current cell (255 wraps to 0) |
| `-` | lower | Decrement the byte in the current cell (0 wraps to 255) |
| `.` | shout | Output the byte in the current cell as a character |
| `,` | parrot | Read one byte of input into the current cell (end of input stores 0) |
| `[` | ahoy | If the current byte is 0, jump forward past the matching ] |
| `]` | avast | If the current byte is not 0, jump back to the matching [ |

## Example

Hello World, pirate style:

```text
hoist hoist hoist hoist hoist hoist hoist hoist ahoy starboard hoist hoist hoist hoist ahoy starboard hoist hoist starboard hoist hoist hoist starboard hoist hoist hoist starboard hoist port port port port lower avast starboard hoist starboard hoist starboard lower starboard starboard hoist ahoy port avast port lower avast starboard starboard shout starboard lower lower lower shout hoist hoist hoist hoist hoist hoist hoist shout shout hoist hoist hoist shout starboard starboard shout port lower shout port shout hoist hoist hoist shout lower lower lower lower lower lower shout lower lower lower lower lower lower lower lower shout starboard starboard hoist shout starboard hoist hoist shout
```

## Try it

```sh
python3 bf_converter.py generate examples/pirate.md
python3 bf_converter.py verify examples/pirate.md
python3 generated/piratescript/piratescript_interpreter.py generated/piratescript/hello_world.piratescript
```
