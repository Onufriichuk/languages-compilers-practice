# Languages and Compilers Design — Practice 2

This project implements Practice 2 for the Languages and Compilers Design course.

## Features

- hand-written lexer implemented as a byte-by-byte state machine
- tokens with kind, text, line and column
- support for `i32`, `mut`, and `exit`
- mandatory initializers
- assignments using `:=`
- arithmetic operations with `+`, `-`, `*`
- declaration-before-use checks
- const/mut checks
- LLVM IR generation using `llvmlite.ir`
- automated valid and invalid tests

## Run

Compile the source file with `python3 compiler.py input.txt output.ll`.

Run the generated LLVM IR with `lli output.ll`.

Run all tests with `python3 run_tests.py`.

Show lexer tokens with `python3 show_tokens.py input.txt`.

## Example

Example input:

i32 x{0}
i32 mut y{10}
i32 z{2+5}
i32 mut t { x + 10 }
t := t * z
exit t

Expected output:

Program exit with result 70

## Tests

The project contains valid and invalid tests covering constant and mutable declarations, arithmetic initializers, exit with a constant, unusual spacing and blank lines, unknown bytes, unterminated `{`, assignment to a const variable, use before declaration, and missing initializers.

Current test result: 10/10 tests passed.

## Git

Practice 1 is stored in the `main` branch.

Practice 2 is implemented in the `practice-2` branch.
