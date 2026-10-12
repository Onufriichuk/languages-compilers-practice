## Practice 5 — if/else, scopes and basic blocks

Practice 5 adds control flow, nested scopes, logical negation, and LLVM basic blocks.

### Implemented features

- `if` statements
- optional `else` blocks
- nested `if` statements
- multi-line `{ ... }` blocks
- logical negation with `!`
- block scope stack
- variable shadowing, including shadowing with a different type
- boolean type checking for `if` conditions
- boolean type checking for `!`
- LLVM `then`, `else`, and `merge` basic blocks
- conditional branches with `cbranch`
- entry-block `alloca` instructions
- `exit` inside an if/else arm
- LLVM `mem2reg` support producing phi nodes
- additional `while` loop implementation with condition, body, and end blocks

### Running the compiler

Compile a program:

```bash
python3 compiler.py input.txt output.ll
