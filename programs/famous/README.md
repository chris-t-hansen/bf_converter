# Famous programs gallery

Classic brainfuck programs, bundled as a gallery and stress test for generated
languages. Convert them all into any language with:

```sh
python3 bf_converter.py gallery LANG.md
```

Every program here was verified with `run-bf` against its canonical output
before bundling (see `TestFamousPrograms` in the test suite).

| File | Program | Author / Source | License | Verified output |
| --- | --- | --- | --- | --- |
| `bottles.bf` | 99 Bottles of Beer | Ben Olmstead; [brainfuck archive](http://esoteric.sange.fi/brainfuck/bf-source/prog/99botles.bf) | Classic, widely redistributed; attribution preserved | 99 verses, 99 down to 0 (CRLF) |
| `fizzbuzz.bf` | FizzBuzz | [esolangs wiki FizzBuzz page](https://esolangs.org/wiki/FizzBuzz), compiled using BFFuck | CC0 (wiki content) | Exact canonical 1..100 |
| `hanoi.bf` | Towers of Hanoi | Roland Illig, 2002; [brainfuck archive](http://esoteric.sange.fi/brainfuck/bf-source/prog/bfide-examples/hanoi.b) | GPL (header preserved in the file) | 7 optimal moves, 3 disks, in German |
| `mandelbrot.bf` | Mandelbrot set | Erik Bosman; [brainfuck archive](http://esoteric.sange.fi/brainfuck/bf-source/prog/mandelbrot.b) | Classic, widely redistributed; attribution preserved | ASCII fractal (`mandelbrot_expected.txt`) |

## Notes

- `hanoi.bf` is GPL-licensed by its author and included **unmodified** as a
  separate program (mere aggregation); the rest of this repository is MIT.
- `hanoi.bf` prints its moves in German: "Lege die oberste Scheibe von Turm a
  auf Turm c." The test parses the move sequence and checks it against the
  optimal 3-disk solution.
- `mandelbrot.bf` is the heavyweight: it takes **about 25 minutes** on this
  naive interpreter (measured: 1434s for the full 6240-byte fractal). Its
  full-output check is opt-in:

  ```sh
  BF_SLOW_TESTS=1 python3 -m unittest discover -s tests
  ```

- `mandelbrot_expected.txt` is the verified reference output used by that test.
- Sources are kept as received (headers and comments intact); brainfuck ignores
  everything except `><+-.,[]`, so the attribution travels with the program.
- **Attribution headers must contain no brainfuck command characters**
  (`><+-.,[]`): prose periods and commas execute as commands. The FizzBuzz
  header therefore points to this README instead of embedding a URL — the
  dots in a domain name are `.` output commands!
