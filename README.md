# Languages and Compilers — Practice 9

## Overview

Practice 9 extends the compiler from Practice 8 with an AST optimization pass that removes unused variables and global functions.
The optimization runs after semantic checking and before LLVM code generation. The compiler is written in Python and uses `llvmlite.ir` to generate LLVM IR.
The additional task implements effect analysis to identify function calls that can be safely removed when their results are unused.
All functionality from previous practices is preserved.

## Practice 9 — Optimizations

The compiler supports the `--remove-unused` flag. This flag enables optimization of the checked AST before code generation.
Without this flag, the compiler works as before. The flag can be placed anywhere in the command-line arguments.

### Task 1 — Unused Variables

`UseCounter` walks through the AST and counts how many times each variable is read.
Variables are tracked by their declaration identity using `id(decl)`, not just by their names. This allows the compiler to correctly handle variables with the same name in different scopes.
Assignment targets are not counted as reads.
`Pruner` removes unused variable declarations and assignments to those variables from the AST.
The optimization repeats until no more declarations can be removed.
Variables are preserved when their initializers or assignments contain observable side effects. Function parameters and structure fields are not removed.

### Task 2 — Unused Functions

The optimization also identifies global functions that are never called.
Unused global function definitions are removed together with their bodies.
The process repeats because removing one function may make another function unused.
Member functions and generated lambda methods are preserved.

### Task 3 — Tests and Memory Management

The `tests/opt` directory contains optimization tests covering:

- Unused variable chains
- Variable shadowing
- Unused global functions
- Variables inside `if` blocks
- Function calls with observable effects
- Programs where nothing should be removed
- Assignments to unused variables
- Additional bonus cases

Each test contains three files:

- `.txt` — source program
- `.astc` — expected optimized checked AST
- `.expected` — expected program output or exit result

The test runner checks the new optimization tests and previous programs in `tests/ok` and `tests/err` with and without the optimization flag.

### Memory Management

The compiler is implemented in Python, which uses reference counting and cyclic garbage collection.
AST nodes in this compiler do not store pointers to their parent nodes.
When the optimization removes a node from the AST and no other strong references remain, Python can release that object.
If parent pointers existed, they could create reference cycles that would require the cyclic garbage collector.
The `measure_practice9_gc.py` script uses `weakref.ref()` to check whether a removed AST node is released.
The experiment showed that the weak reference returned `None` after the removed node had no remaining strong references.
This concerns memory used by the compiler itself, not memory management in compiled programs.

### Known Limitations

A variable that only reads itself, for example `k := k + 1`, may remain because its own assignment counts as a read.
Two unused functions that call each other may also remain because each function has a call.
The optimization prefers keeping unnecessary code rather than removing code that might affect observable program behavior.

### Additional Task — Calls Without Effects

`EffectAnalyzer` checks whether function calls have observable effects.

The analysis considers:

- Functions that use `print()` or `read()`
- Member functions that modify their objects
- Functions containing `while` loops
- Recursive functions
- Functions that call other functions with effects

The effects are propagated through function calls until no new effects are discovered.
Calls without effects can be removed when their results are unused.
The bonus tests cover pure functions, mutating methods, recursion, loops, lambdas, and effects propagated through function calls.

## Running the Compiler

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Compile a program normally:

```bash
python3 compiler.py input.txt output.ll
```

Compile with optimization:

```bash
python3 compiler.py --remove-unused input.txt output.ll
```

Display the optimized checked AST:

```bash
python3 compiler.py --remove-unused --ast-checked input.txt
```

Execute the generated LLVM IR:

```bash
lli-18 output.ll
```

## Testing

Run all Practice 9 tests and regression checks:

```bash
python3 run_tests_practice9.py --all
```

Run the memory experiment:

```bash
python3 measure_practice9_gc.py
```

### Verified Results

Tests executed on Ubuntu:

- Practice 9 and regression checks: **206/206 passed**
- Practice 8: 29/29 passed
- Practice 6: 15/15 passed
- Practice 7 regression runner: 90/90 passed

The Practice 9 tests check optimized AST output and verify that program behavior is preserved with and without `--remove-unused`.
The memory experiment confirmed that the removed AST node was released after its remaining strong references were dropped.

## Previous Functionality — Practice 8

Practice 9 builds on the implementation from Practice 8.

### Callable Objects

- Structures with a `call` member function can be called directly using `obj(args)`.
- Callable fields are supported.
- Argument types and mutation rules are checked.
- Invalid calls produce compilation errors.

### Lambdas

- Lambdas use the syntax `fn name := [captures](params) -> type`.
- Variables can be captured by value.
- Lambdas can be declared inside functions, loops, and other blocks.
- Lambdas are transformed into structures with captured fields and a `call` method.
- Invalid captures and lambda usage produce compilation errors.

### Mutable Captures

- `[mut variable]` creates a mutable copy of a captured variable.
- Modifications to captured copies do not affect the original variables.
- Nested mutable lambdas and mutation checks are supported.

## AI Usage

ChatGPT was used to assist with implementation, debugging, writing tests, and documentation for Practice 9.
The prompts, implementation decisions, modifications, and verification details are documented in `ai_usage.txt`.
