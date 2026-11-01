"""Repeatable weakref measurement for the Practice 9 README."""
import gc
import weakref
from pathlib import Path
from compiler import Parser, SemanticChecker, lex, remove_unused, DeclNode

source = b'i32 unused{42}\nexit 0\n'
tree = Parser(lex(source)).parse_program()
SemanticChecker().check(tree)
node = next(n for n in tree.statements if isinstance(n, DeclNode))
ref = weakref.ref(node)
print('Before removing:', ref() is not None)
del node
remove_unused(tree)
gc.collect()
print('After removing:', ref() is None)
assert ref() is None, 'Removed declaration still referenced'
