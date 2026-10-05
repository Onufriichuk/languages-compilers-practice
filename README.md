# Practice 4

In this practice, the compiler was extended with new types and semantic checks.

Implemented:
- support for `i64` and `bool`
- boolean literals `true` and `false`
- comparison operators `==` and `!=`
- declaration types in the AST
- a separate `SemanticChecker`
- type checking for arithmetic, comparisons, declarations and assignments
- widening from `i32` to `i64`
- LLVM `sext` generation
- boolean values represented as `i1`
- boolean and integer support in `exit`

Testing:
- Practice 4 tests: 12/12 passed
- Previous tests: 19/19 passed

The compiler supports `--ast`, semantic validation before code generation, and LLVM IR generation for the new types and operations.
