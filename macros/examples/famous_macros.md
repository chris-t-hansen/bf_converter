# FamousMacros

A macro language: each command runs an entire famous program on its own
fresh tape. Write a program by naming programs; any other text is ignored.

## Macros

| Token | Program |
| --- | --- |
| Hello World | hello_world |
| FizzBuzz | fizzbuzz |
| Towers of Hanoi | hanoi |
| 99 Bottles | bottles |
| Alphabet | alphabet |
| Mandelbrot | mandelbrot |

## Example

```text
Hello World FizzBuzz
```

runs Hello World, then FizzBuzz — each on a clean tape, outputs concatenated.

## Try it

```sh
python3 macros/macro_lang.py run macros/examples/famous_macros.md -c "Hello World"
python3 macros/macro_lang.py verify macros/examples/famous_macros.md
python3 macros/macro_lang.py generate macros/examples/famous_macros.md
```
