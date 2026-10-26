
# Languages and Compilers — Practice 8

## Overview

Practice 8 extends the compiler with callable objects, lambdas, and mutable captures. The compiler is implemented in Python using `llvmlite.ir`.

## Task 1 — Callable Objects

- Structures with a `call` member function can be called directly: `obj(args)` is equivalent to `obj.call(args)`.
- Callable fields are supported.
- Argument types, name conflicts, and mutation rules are checked.
- Invalid calls produce compilation errors.

## Task 2 — Lambdas

- Lambdas are declared using `fn name := [captures](params) -> type`.
- Variables are captured by value.
- Lambdas can be declared inside functions, loops, and other blocks.
- Each lambda is transformed into a structure with captured fields and a `call` method.
- Invalid captures and lambda usage produce compilation errors.
- `--ast-checked` displays the AST after semantic transformations.

## Additional Task — Mutable Captures

- `[mut variable]` creates a mutable copy of a captured variable.
- Changes to the captured copy do not affect the original.
- Nested mutable lambdas and mutation checks are supported.

## Running

Activate the environment:

```bash
source .venv/bin/activate
```

Compile and run:

```bash
python3 src/compiler.py input.txt output.ll
lli-18 output.ll
```

Display the checked AST:

```bash
python3 src/compiler.py --ast-checked input.txt
```

## Testing

Run the tests:

```bash
python3 run_tests_practice8.py
python3 run_tests_practice6.py
python3 run_tests_practice7.py
```

Verified results on Ubuntu:

- Practice 8: 29/29 passed
- Practice 6: 15/15 passed
- Practice 7 regression runner: 90/90 passed

All Practice 8 features, including the additional task, passed the implemented tests. Previous functionality remains compatible with the tested cases.

## AI Usage

ChatGPT was used for implementation assistance, debugging, and test creation. Details are documented in `ai_usage.txt`.
