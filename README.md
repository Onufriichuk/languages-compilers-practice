# Languages and Compilers Design — Practice 7

## Overview

This project implements a compiler for a small programming language using Python and `llvmlite`.

Practice 7 extends the compiler from the previous practices by adding member functions inside structures, field access and mutation rules, built-in input/output operations, and chained function calls.

The compiler generates LLVM IR, which can be executed using `lli`.

## Features

The compiler supports:

- Basic types: `i32`, `i64`, and `bool`.
- User-defined structures with typed fields.
- Mutable (`mut`) and immutable variables and fields.
- Variable declarations and assignments.
- Arithmetic and comparison operations.
- Conditional statements (`if`, `else`) and `while` loops.
- Global functions with parameters and return values.
- Member functions declared inside structures.
- Member function calls and nested field access.
- Type checking and mutation rules.
- Built-in `read()` and `print()` operations.
- Chained calls on temporary structure values (additional task).
- AST output using `--ast`.
- LLVM IR generation using `llvmlite.ir`.

## Practice 7 Implementation

### Task 1 — Member Functions

Structures can contain member functions after their field declarations.

Member functions are called on structure objects using dot notation.

Example:

```text
struct Point
{
    i32 mut x
    i32 mut y

    fn d2 := () -> i32
    {
        i32 r{x * x + y * y}
        exit r
    }
}

Point p{3, 4}
i32 result{p.d2()}
exit result
```

Expected output:

```text
Program exit with result 25
```

The compiler supports member function calls on nested structure fields, such as `c.center.d2()`.

### Task 2 — Name Resolution, Mutation and Code Generation

Inside a member function, parameters and local variables take priority over structure fields.

Member functions can access fields of their object directly and call other member functions of the same structure.

Mutating member functions can only be called through mutable objects and mutable field chains.

The compiler checks these rules during semantic analysis.

In LLVM IR, a member function receives a pointer to its object as an implicit first argument (`this`).

For example, `Point_shift` uses the object's address to modify its fields.

LLVM IR is generated with `llvmlite.ir`.

### Task 3 — Built-in Input and Output

The compiler supports two built-in operations:

- `read()` reads an `i32` value from standard input.
- `print()` prints a value followed by a newline.

The `print()` statement supports integers, booleans, string literals, and structure objects.

Example:

```text
i32 a{read()}
print("Input value:")
print(a)
exit a
```

With input `5`, the expected output is:

```text
Input value:
5
Program exit with result 5
```

Input and output are implemented through LLVM calls to `scanf` and `printf`.

### Additional Task — Chained Calls

The compiler supports member calls and field access after functions that return structures.

Examples:

```text
p.moved(1).shift(2)
c.grown(3).radius
origin().moved(7).x
```

Function results are treated as temporary values. Their fields can be read and their member functions can be called, but their fields cannot be assignment targets.

## Project Structure

```text
languages-compilers-practice/
├── src/
│   └── compiler.py
├── tests/
│   ├── ok/
│   └── err/
├── run_tests_practice7.py
├── run_tests_practice6.py
├── README.md
└── ai_usage.txt
```

The `tests/ok` directory contains valid programs and their expected outputs. The `tests/err` directory contains programs that must be rejected with compilation errors.

Programs requiring standard input use corresponding `.in` files.

## Requirements

- Python 3
- `llvmlite`
- LLVM tools (`lli`)
- Python virtual environment (recommended)

## Running the Compiler

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Generate LLVM IR from a source program:

```bash
python3 src/compiler.py input.txt output.ll
```

Execute the generated program:

```bash
lli output.ll
```

Display the Abstract Syntax Tree:

```bash
python3 src/compiler.py --ast input.txt
```

## Running Tests

Run the Practice 7 test suite:

```bash
python3 run_tests_practice7.py
```

Run the previous Practice 6 tests to check backward compatibility:

```bash
python3 run_tests_practice6.py
```

At the time of local testing, the Practice 7 test suite passed 61 out of 61 tests, and the Practice 6 suite passed 15 out of 15 tests.

## Error Handling

The compiler reports errors with source line and column information.

Examples of detected errors include:

- Duplicate fields or member functions.
- Invalid member function declarations.
- Unknown fields or member functions.
- Incorrect numbers or types of arguments.
- Mutation through immutable objects or fields.
- Assignment to constant fields.
- Incorrect return types.
- Invalid usage of `read()` or `print()`.
- Invalid chained calls and assignments to temporary values.

## AI Usage

Information about AI assistance, including tools, prompts, generated code, modifications, and testing, is documented in `ai_usage.txt`.
