# Languages and Compilers Design — Practice 3

This project implements Practice 3 for the Languages and Compilers Design course.

## Features

- hand-written lexer
- EBNF grammar in `grammar.ebnf`
- recursive-descent parser
- AST for statements and expressions
- `--ast` mode
- support for `i32`, `mut`, `exit`, and `:=`
- arithmetic expressions with `+`, `-`, `*`
- correct precedence and left associativity
- semantic checks for declarations and const/mut variables
- LLVM IR generation from the AST
- automated valid and invalid tests

## Compiler Pipeline

source code → lexer → parser → AST → code generation → LLVM IR

## Run

Compile: `python3 compiler.py input.txt output.ll`

Run: `lli output.ll`

Print AST: `python3 compiler.py --ast input.txt`

Run tests: `python3 run_tests.py`

## Example

Input:

`i32 x{2 + 3 * 4}`  
`i32 mut a{10 - 3 - 2}`  
`a := a * 2 - 1`  
`i32 z{x * a - 6}`  
`exit z`

Expected output:

`Program exit with result 120`

## Expressions

`*` has higher precedence than `+` and `-`.

`2 + 3 * 4` is parsed as `2 + (3 * 4)`.

Operators of equal precedence are left-associative.

`10 - 3 - 2` is parsed as `(10 - 3) - 2`.

## Tests

Tests cover valid expressions, precedence, assignments, parser errors, semantic errors, and Practice 2 compatibility.

Current result: `19/19 tests passed`

## Git

- Practice 1 — `main`
- Practice 2 — `practice-2`
- Practice 3 — `practice-3`
