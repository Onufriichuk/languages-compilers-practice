## Practice 10 — A Real Program and C Integration

### Overview

In Practice 10, I extended my compiler from Practice 9 to compile and run a real program as an executable binary.

The main program works with three points, calculates their squared distances from the origin, and finds points that match a distance entered by the user.

I also implemented the additional task, which allows programs written in our language to call external C functions using `extern fn`.

### Task 1 — Points Program

The program is located in `tests/io/points.txt`.

It uses:

- A `Point` structure with `x` and `y` fields
- A member function `d2()` to calculate the squared distance
- A function `report()` to check and print matching points
- `read()` to receive user input
- `print()` to display the results

The compiler supports printing structures by going through their fields. This works for different structures without adding special code for `Point`.

### Building an Executable Binary

The compiler generates LLVM IR using `llvmlite.ir`. The generated LLVM IR can be converted into an object file and then linked into an executable binary.

Commands:

```bash
python3 compiler.py tests/io/points.txt points.ll
llc-18 -filetype=obj -relocation-model=pic points.ll -o points.o
clang -fPIE points.o -o points
./points < tests/io/points.sheet.in
```

The program can also be started manually:

```bash
./points
```

### Input and Output Tests

I added three test sessions in `tests/io`:

- `points.sheet` checks two matching points.
- `points.none` checks a case without matching points.
- `points.all` checks three matching points with negative coordinates.

Each session has an `.in` file with input values and an `.expected` file with the expected output.

### Additional Task — Calling C Functions

I implemented support for external C functions using `extern fn`.

The compiler can now call functions such as `abs` from the C standard library and `isqrt` from `tests/ffi/geometry.c`.

The implementation includes:

- Parsing external function declarations
- Checking parameter and return types
- Supporting `i32` and `i64` in external function signatures
- Generating LLVM function declarations using their original C names
- Linking the generated object file with C code
- Checking invalid external function declarations
- Supporting external functions with `--remove-unused`

The bonus program is located in `tests/ffi/geometry.txt`.

Commands:

```bash
python3 compiler.py tests/ffi/geometry.txt geometry.ll
llc-18 -filetype=obj -relocation-model=pic geometry.ll -o geometry.o
clang -fPIE geometry.o tests/ffi/geometry.c -o geometry
./geometry < tests/ffi/geometry.sheet.in
```

The `tests/err` directory also contains tests for invalid `extern fn` declarations.

### Testing

I added `run_tests_practice10.py` to test the new functionality and check that previous features still work.

The script tests programs with and without the `--remove-unused` optimization.

To run all tests:

```bash
python3 run_tests_practice10.py --all
```

To run only the new tests:

```bash
python3 run_tests_practice10.py --all --new-only
```

### Verified Results

I ran the complete Practice 10 test script in my Ubuntu virtual machine after activating the Python virtual environment.

**Result: 238/238 tests passed.**

The tests include previous compiler functionality, optimization tests, input/output sessions, and external C function tests.

### Documentation

- `reflection.md` contains my personal course reflection.
- `ai_usage.txt` describes how AI tools were used during the practice.

The implementation builds on the previous practices and preserves the existing compiler functionality.
