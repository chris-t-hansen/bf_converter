# FamousFuck

A [Trivial brainfuck substitution](https://esolangs.org/wiki/Trivial_brainfuck_substitution)
where every command is named after a famous program. Saying "Towers of Hanoi"
increments a cell; "99 Bottles of Beer" prints one. The names are pure
decoration — underneath, it is still the eight humble brainfuck commands.

Extension: .fame

## Commands

| Brainfuck | FamousFuck | Description |
| --- | --- | --- |
| `>` | Hello World | Move the data pointer one cell to the right |
| `<` | FizzBuzz | Move the data pointer one cell to the left |
| `+` | Towers of Hanoi | Increment the byte in the current cell (255 wraps to 0) |
| `-` | Mandelbrot | Decrement the byte in the current cell (0 wraps to 255) |
| `.` | 99 Bottles of Beer | Output the byte in the current cell as a character |
| `,` | Game of Life | Read one byte of input into the current cell (end of input stores 0) |
| `[` | Quine | If the current byte is 0, jump forward past the matching ] |
| `]` | Turing Machine | If the current byte is not 0, jump back to the matching [ |

## Example

Hello World, featuring an all-star cast:

```text
Towers of Hanoi Towers of Hanoi Towers of Hanoi Towers of Hanoi Towers of Hanoi Towers of Hanoi Towers of Hanoi Towers of Hanoi Quine Hello World Towers of Hanoi Towers of Hanoi Towers of Hanoi Towers of Hanoi Quine Hello World Towers of Hanoi Towers of Hanoi Hello World Towers of Hanoi Towers of Hanoi Towers of Hanoi Hello World Towers of Hanoi Towers of Hanoi Towers of Hanoi Hello World Towers of Hanoi FizzBuzz FizzBuzz FizzBuzz FizzBuzz Mandelbrot Turing Machine Hello World Towers of Hanoi Hello World Towers of Hanoi Hello World Mandelbrot Hello World Hello World Towers of Hanoi Quine FizzBuzz Turing Machine FizzBuzz Mandelbrot Turing Machine Hello World Hello World 99 Bottles of Beer Hello World Mandelbrot Mandelbrot Mandelbrot 99 Bottles of Beer Towers of Hanoi Towers of Hanoi Towers of Hanoi Towers of Hanoi Towers of Hanoi Towers of Hanoi Towers of Hanoi 99 Bottles of Beer 99 Bottles of Beer Towers of Hanoi Towers of Hanoi Towers of Hanoi 99 Bottles of Beer Hello World Hello World 99 Bottles of Beer FizzBuzz Mandelbrot 99 Bottles of Beer FizzBuzz 99 Bottles of Beer Towers of Hanoi Towers of Hanoi Towers of Hanoi 99 Bottles of Beer Mandelbrot Mandelbrot Mandelbrot Mandelbrot Mandelbrot Mandelbrot 99 Bottles of Beer Mandelbrot Mandelbrot Mandelbrot Mandelbrot Mandelbrot Mandelbrot Mandelbrot Mandelbrot 99 Bottles of Beer Hello World Hello World Towers of Hanoi 99 Bottles of Beer Hello World Towers of Hanoi Towers of Hanoi 99 Bottles of Beer
```

## Try it

```sh
python3 bf_converter.py generate examples/famous.md
python3 bf_converter.py verify examples/famous.md
python3 generated/famousfuck/famousfuck_interpreter.py \
    generated/famousfuck/hello_world.fame
```
