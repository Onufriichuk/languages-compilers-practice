import sys
import os

from llvmlite import ir
import llvmlite.binding as llvm


I1 = ir.IntType(1)
I8 = ir.IntType(8)
I32 = ir.IntType(32)
I64 = ir.IntType(64)

class CompileError(Exception):
    pass

class Node:
    def __init__(self, line, column):
        self.line = line
        self.column = column

    def dump(self, indent=0):
        raise NotImplementedError


class ProgramNode(Node):
    def __init__(self, statements, exit_node):
        super().__init__(1, 1)
        self.statements = statements
        self.exit_node = exit_node

    def dump(self, indent=0):
        lines = [" " * indent + "Program"]

        for stmt in self.statements:
            lines.extend(stmt.dump(indent + 2))

        lines.extend(self.exit_node.dump(indent + 2))
        return lines


class StmtNode(Node):
    pass


class DeclNode(StmtNode):
    def __init__(self, line, column, name, type_name, mutable, init):
        super().__init__(line, column)
        self.name = name
        self.type_name = type_name
        self.mutable = mutable
        self.init = init

    def dump(self, indent=0):
        kind = "mut" if self.mutable else "const"

        lines = [
            " " * indent + f"Decl {self.name} {self.type_name} {kind}"
        ]

        lines.extend(self.init.dump(indent + 2))
        return lines


class AssignNode(StmtNode):
    def __init__(self, line, column, name, value):
        super().__init__(line, column)
        self.name = name
        self.value = value

    def dump(self, indent=0):
        lines = [
            " " * indent + f"Assign {self.name}"
        ]

        lines.extend(self.value.dump(indent + 2))
        return lines


class ExitNode(Node):
    def __init__(self, line, column, value):
        super().__init__(line, column)
        self.value = value

    def dump(self, indent=0):
        lines = [" " * indent + "Exit"]
        lines.extend(self.value.dump(indent + 2))
        return lines


class ExprNode(Node):
    pass


class BinOpNode(ExprNode):
    def __init__(
        self,
        line,
        column,
        op,
        left,
        right,
    ):
        super().__init__(line, column)
        self.op = op
        self.left = left
        self.right = right

    def dump(self, indent=0):
        lines = [
            " " * indent + f"BinOp {self.op}"
        ]

        lines.extend(self.left.dump(indent + 2))
        lines.extend(self.right.dump(indent + 2))
        return lines


class VarNode(ExprNode):
    def __init__(self, line, column, name):
        super().__init__(line, column)
        self.name = name

    def dump(self, indent=0):
        return [
            " " * indent + f"Var {self.name}"
        ]


class ConstNode(ExprNode):
    def __init__(self, line, column, value):
        super().__init__(line, column)
        self.value = value

    def dump(self, indent=0):
        return [
            " " * indent + f"Const {self.value}"
        ]

class BoolNode(ExprNode):
    def __init__(self, line, column, value):
        super().__init__(line, column)
        self.value = value

    def dump(self, indent=0):
        text = "true" if self.value else "false"

        return [
            " " * indent + f"Bool {text}"
        ]

class BlockNode(Node):
    def __init__(self, line, column, statements, exit_node=None):
        super().__init__(line, column)
        self.statements = statements
        self.exit_node = exit_node

    def dump(self, indent=0):
        lines = [" " * indent + "Block"]

        for stmt in self.statements:
            lines.extend(stmt.dump(indent + 2))

        if self.exit_node is not None:
            lines.extend(self.exit_node.dump(indent + 2))

        return lines


class IfNode(StmtNode):
    def __init__(self, line, column, condition, then_block, else_block=None):
        super().__init__(line, column)
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block

    def dump(self, indent=0):
        lines = [" " * indent + "If"]

        lines.extend(self.condition.dump(indent + 2))
        lines.extend(self.then_block.dump(indent + 2))

        if self.else_block is not None:
            lines.extend(self.else_block.dump(indent + 2))

        return lines

class WhileNode(StmtNode):
    def __init__(self, line, column, condition, body):
        super().__init__(line, column)
        self.condition = condition
        self.body = body

    def dump(self, indent=0):
        lines = [" " * indent + "While"]

        lines.extend(self.condition.dump(indent + 2))
        lines.extend(self.body.dump(indent + 2))

        return lines

class NotNode(ExprNode):
    def __init__(self, line, column, operand):
        super().__init__(line, column)
        self.operand = operand

    def dump(self, indent=0):
        lines = [" " * indent + "Not"]
        lines.extend(self.operand.dump(indent + 2))
        return lines

class Parser:
    def __init__(self, lines):
        self.lines = lines
        self.line_pos = 0
        self.toks = []
        self.pos = 0

    def peek(self):
        if self.pos < len(self.toks):
            return self.toks[self.pos]
        return None

    def eat(self):
        tok = self.peek()

        if tok is None:
            return None

        self.pos += 1
        return tok

    def expect_text(self, text, message):
        tok = self.peek()

        if tok is None:
            self.error_end(message)

        if tok.text != text:
            raise CompileError(
                f"line {tok.line}:{tok.column}: "
                f"{message}, got '{tok.text}'"
            )

        return self.eat()

    def expect_kind(self, kind, message):
        tok = self.peek()

        if tok is None:
            self.error_end(message)

        if tok.kind != kind:
            raise CompileError(
                f"line {tok.line}:{tok.column}: "
                f"{message}, got '{tok.text}'"
            )

        return self.eat()

    def error_end(self, message):
        if self.toks:
            last = self.toks[-1]
            column = last.column + len(last.text)
            line = last.line
        else:
            line = 1
            column = 1

        raise CompileError(
            f"line {line}:{column}: {message}"
        )

    def next_line(self):
        while self.line_pos < len(self.lines):
            toks = self.lines[self.line_pos]
            self.line_pos += 1

            if not toks:
                continue

            self.toks = toks
            self.pos = 0
            return True

        self.toks = []
        self.pos = 0
        return False

    def peek_line(self):
        pos = self.line_pos

        while pos < len(self.lines):
            toks = self.lines[pos]

            if toks:
                return toks

            pos += 1

        return None

    def parse_program(self):
        statements = []
        exit_node = None

        while self.next_line():
            first = self.peek()

            if (
                first.kind == "keyword"
                and first.text == "exit"
            ):
                exit_node = self.parse_exit()

                if self.peek() is not None:
                    tok = self.peek()
                    raise CompileError(
                        f"line {tok.line}:{tok.column}: "
                        f"unexpected '{tok.text}' after the statement"
                    )

                if self.peek_line() is not None:
                    tok = self.peek_line()[0]
                    raise CompileError(
                        f"line {tok.line}:{tok.column}: "
                        "code after exit is not allowed"
                    )

                break

            statements.append(
                self.parse_statement()
            )

            if self.peek() is not None:
                tok = self.peek()

                raise CompileError(
                    f"line {tok.line}:{tok.column}: "
                    f"unexpected '{tok.text}' after the statement"
                )

        if exit_node is None:
            raise CompileError(
                "line 1:1: program needs an exit statement"
            )

        return ProgramNode(
            statements,
            exit_node,
        )

    def parse_statement(self):
        tok = self.peek()

        if tok is None:
            self.error_end(
                "expected a statement"
            )

        if (
            tok.kind == "keyword"
            and tok.text in {"i32", "i64", "bool"}
        ):
            return self.parse_decl()

        if tok.kind == "identifier":
            return self.parse_assign()

        if (
            tok.kind == "keyword"
            and tok.text == "if"
        ):
            return self.parse_if()

        if (
            tok.kind == "keyword"
            and tok.text == "while"
        ):
            return self.parse_while()

        raise CompileError(
            f"line {tok.line}:{tok.column}: "
            f"cannot start a statement with '{tok.text}'"
        )

    def parse_if(self):
        if_tok = self.expect_text(
            "if",
            "expected 'if'"
        )

        condition = self.parse_expr()

        if self.peek() is not None:
            tok = self.peek()
            raise CompileError(
                f"line {tok.line}:{tok.column}: "
                f"unexpected '{tok.text}' after the statement"
            )

        if not self.next_line():
            raise CompileError(
                f"line {if_tok.line}:{if_tok.column}: "
                "expected '{' on its own line after 'if'"
            )

        tok = self.peek()

        if (
            tok is None
            or tok.kind != "lbrace"
            or len(self.toks) != 1
        ):
            got = tok.text if tok is not None else "end"
            raise CompileError(
                f"line {if_tok.line + 1}:1: "
                f"expected '{{' on its own line after 'if', got '{got}'"
            )

        then_block = self.parse_block()

        else_block = None

        next_tokens = self.peek_line()

        if (
            next_tokens is not None
            and len(next_tokens) == 1
            and next_tokens[0].kind == "keyword"
            and next_tokens[0].text == "else"
        ):
            self.next_line()

            if not self.next_line():
                raise CompileError(
                    f"line {if_tok.line}:1: "
                    "expected '{' after 'else'"
                )

            tok = self.peek()

            if (
                tok is None
                or tok.kind != "lbrace"
                or len(self.toks) != 1
            ):
                raise CompileError(
                    f"line {tok.line}:{tok.column}: "
                    "expected '{' on its own line after 'else'"
                )

            else_block = self.parse_block()

        return IfNode(
            if_tok.line,
            if_tok.column,
            condition,
            then_block,
            else_block,
        )

    def parse_while(self):
        while_tok = self.expect_text(
            "while",
            "expected 'while'"
        )

        condition = self.parse_expr()

        if self.peek() is not None:
            tok = self.peek()
            raise CompileError(
                f"line {tok.line}:{tok.column}: "
                f"unexpected '{tok.text}' after the statement"
            )

        if not self.next_line():
            raise CompileError(
                f"line {while_tok.line}:{while_tok.column}: "
                "expected '{' on its own line after 'while'"
            )

        tok = self.peek()

        if (
            tok is None
            or tok.kind != "lbrace"
            or len(self.toks) != 1
        ):
            got = tok.text if tok is not None else "end"
            raise CompileError(
                f"line {while_tok.line + 1}:1: "
                f"expected '{{' on its own line after 'while', got '{got}'"
            )

        body = self.parse_block()

        return WhileNode(
            while_tok.line,
            while_tok.column,
            condition,
            body,
        )

    def parse_block(self):
        open_tok = self.peek()

        self.eat()

        if self.peek() is not None:
            tok = self.peek()
            raise CompileError(
                f"line {tok.line}:{tok.column}: "
                "unexpected token after '{'"
            )

        statements = []
        exit_node = None

        while True:
            if not self.next_line():
                raise CompileError(
                    f"line {open_tok.line}:{open_tok.column}: "
                    "'{' is never closed"
                )

            first = self.peek()

            if (
                first.kind == "rbrace"
                and len(self.toks) == 1
            ):
                if not statements and exit_node is None:
                    raise CompileError(
                        f"line {open_tok.line}:{open_tok.column}: "
                        "empty block"
                    )

                self.eat()

                return BlockNode(
                    open_tok.line,
                    open_tok.column,
                    statements,
                    exit_node,
                )

            if exit_node is not None:
                raise CompileError(
                    f"line {first.line}:{first.column}: "
                    "statement after 'exit' in the same block"
                )

            if (
                first.kind == "keyword"
                and first.text == "exit"
            ):
                exit_node = self.parse_exit()
            else:
                statements.append(
                    self.parse_statement()
                )

            if self.peek() is not None:
                tok = self.peek()

                raise CompileError(
                    f"line {tok.line}:{tok.column}: "
                    f"unexpected '{tok.text}' after the statement"
                )

    def parse_decl(self):
        type_tok = self.eat()

        mutable = False

        tok = self.peek()

        if (
            tok is not None
            and tok.kind == "keyword"
            and tok.text == "mut"
        ):
            self.eat()
            mutable = True

        name = self.expect_kind(
            "identifier",
            "expected a variable name"
        )

        tok = self.peek()

        if (
            tok is None
            or tok.kind != "lbrace"
        ):
            raise CompileError(
                f"line {name.line}:{name.column}: "
                f"variable '{name.text}' needs an initialiser in {{}}"
            )

        open_brace = self.eat()

        init = self.parse_expr()

        tok = self.peek()

        if tok is None:
            raise CompileError(
                f"line {open_brace.line}:{open_brace.column}: "
                "'{' is not closed before the end of the line"
            )

        self.expect_kind(
            "rbrace",
            "expected '}'"
        )

        return DeclNode(
            name.line,
            name.column,
            name.text,
            type_tok.text,
            mutable,
            init,
        )

    def parse_assign(self):
        name = self.expect_kind(
            "identifier",
            "expected variable name"
        )

        tok = self.peek()

        if (
            tok is None
            or tok.kind != "operator"
            or tok.text != ":="
        ):
            if tok is None:
                self.error_end(
                    f"expected ':=' after '{name.text}'"
                )

            raise CompileError(
                f"line {tok.line}:{tok.column}: "
                f"expected ':=' after '{name.text}', "
                f"got '{tok.text}'"
            )

        self.eat()

        value = self.parse_expr()

        return AssignNode(
            name.line,
            name.column,
            name.text,
            value,
        )

    def parse_exit(self):
        exit_tok = self.expect_text(
            "exit",
            "expected 'exit'"
        )

        value = self.parse_factor()

        return ExitNode(
            exit_tok.line,
            exit_tok.column,
            value,
        )

    def parse_expr(self):
        node = self.parse_arith()

        tok = self.peek()

        if (
            tok is not None
            and tok.kind == "operator"
            and tok.text in {"==", "!="}
        ):
            self.eat()

            right = self.parse_arith()

            node = BinOpNode(
                tok.line,
                tok.column,
                tok.text,
                node,
                right,
            )

        return node

    def parse_arith(self):
        node = self.parse_term()

        while True:
            tok = self.peek()

            if (
                tok is None
                or tok.kind != "operator"
                or tok.text not in {"+", "-"}
            ):
                break

            self.eat()

            right = self.parse_term()

            node = BinOpNode(
                tok.line,
                tok.column,
                tok.text,
                node,
                right,
            )

        return node

    def parse_term(self):
        node = self.parse_factor()

        while True:
            tok = self.peek()

            if (
                tok is None
                or tok.kind != "operator"
                or tok.text != "*"
            ):
                break

            self.eat()

            right = self.parse_factor()

            node = BinOpNode(
                tok.line,
                tok.column,
                tok.text,
                node,
                right,
            )

        return node

    def parse_factor(self):
        tok = self.peek()

        if tok is None:
            self.error_end(
                "expected a constant or a variable"
            )

        if (
            tok.kind == "operator"
            and tok.text == "!"
        ):
            self.eat()

            operand = self.parse_factor()

            return NotNode(
                tok.line,
                tok.column,
                operand,
            )

        if tok.kind == "number":
            self.eat()

            return ConstNode(
                tok.line,
                tok.column,
                int(tok.text),
            )

        if (
           tok.kind == "keyword"
           and tok.text in {"true", "false"}
        ):
           self.eat()

           return BoolNode(
               tok.line,
               tok.column,
               tok.text == "true",
         )

        if tok.kind == "identifier":
            self.eat()

            return VarNode(
                tok.line,
                tok.column,
                tok.text,
            )

        raise CompileError(
            f"line {tok.line}:{tok.column}: "
            f"expected a constant or a variable, "
            f"got '{tok.text}'"
        )

class SemanticChecker:
    def __init__(self):
        self.scopes = [{}]

    def lookup(self, node, name):
        for frame in reversed(self.scopes):
            if name in frame:
                return frame[name]

        raise CompileError(
            f"line {node.line}:{node.column}: "
            f"variable '{name}' is used before its declaration"
        )

    def check(self, program):
        for stmt in program.statements:
            self.visit_stmt(stmt)

        self.visit_exit(program.exit_node)

    def visit_stmt(self, node):
        if isinstance(node, DeclNode):
            return self.visit_decl(node)

        if isinstance(node, AssignNode):
            return self.visit_assign(node)

        if isinstance(node, IfNode):
            return self.visit_if(node)

        if isinstance(node, WhileNode):
            return self.visit_while(node)

        raise CompileError(
            f"line {node.line}:{node.column}: unknown statement"
        )

    def visit_expr(self, node):
        if isinstance(node, ConstNode):
            return self.visit_const(node)

        if isinstance(node, BoolNode):
            return self.visit_bool(node)

        if isinstance(node, VarNode):
            return self.visit_var(node)

        if isinstance(node, BinOpNode):
            return self.visit_binop(node)

        if isinstance(node, NotNode):
            return self.visit_not(node)

        raise CompileError(
            f"line {node.line}:{node.column}: unknown expression"
        )

    def visit_const(self, node):
        if node.value <= 2147483647:
            node.type = "i32"
        elif node.value <= 9223372036854775807:
            node.type = "i64"
        else:
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"constant {node.value} does not fit in i64"
            )

        return node.type

    def visit_bool(self, node):
        node.type = "bool"
        return node.type

    def visit_var(self, node):
        node.decl = self.lookup(
            node,
            node.name,
        )

        node.type = node.decl.type_name
        return node.type

    def visit_decl(self, node):
        frame = self.scopes[-1]

        if node.name in frame:
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"variable '{node.name}' is already declared in this block"
            )

        self.visit_expr(node.init)

        self.check_assignable(
            node.init,
            node.type_name,
            node,
            f"initialise '{node.name}'"
        )

        frame[node.name] = node

    def visit_assign(self, node):
        decl = self.lookup(
            node,
            node.name,
        )

        if not decl.mutable:
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"cannot assign to '{node.name}': it is not mut"
            )

        node.decl = decl

        self.visit_expr(node.value)

        self.check_assignable(
            node.value,
            decl.type_name,
            node,
            f"assign to '{node.name}'"
        )

    def visit_block(self, node):
        self.scopes.append({})

        try:
            for stmt in node.statements:
                self.visit_stmt(stmt)

            if node.exit_node is not None:
                self.visit_exit(node.exit_node)
        finally:
            self.scopes.pop()

    def visit_if(self, node):
        condition_type = self.visit_expr(
            node.condition
        )

        if condition_type != "bool":
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"the condition of 'if' must be bool, got {condition_type}"
            )

        self.visit_block(
            node.then_block
        )

        if node.else_block is not None:
            self.visit_block(
                node.else_block
            )

    def visit_while(self, node):
        condition_type = self.visit_expr(
            node.condition
        )

        if condition_type != "bool":
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"the condition of 'while' must be bool, got {condition_type}"
            )

        self.visit_block(
            node.body
        )

    def visit_not(self, node):
        operand_type = self.visit_expr(
            node.operand
        )

        if operand_type != "bool":
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"cannot apply '!' to {operand_type}"
            )

        node.type = "bool"
        return node.type

    def visit_binop(self, node):
        left_type = self.visit_expr(node.left)
        right_type = self.visit_expr(node.right)

        if node.op in {"+", "-", "*"}:
            if left_type == "bool":
                raise CompileError(
                    f"line {node.line}:{node.column}: "
                    f"cannot apply '{node.op}' to bool"
                )

            if right_type == "bool":
                raise CompileError(
                    f"line {node.line}:{node.column}: "
                    f"cannot apply '{node.op}' to bool"
                )

            if left_type == "i64" or right_type == "i64":
                node.type = "i64"
            else:
                node.type = "i32"

            return node.type

        if node.op in {"==", "!="}:
            if left_type == "bool" and right_type == "bool":
                node.type = "bool"
                return node.type

            if (
                left_type in {"i32", "i64"}
                and right_type in {"i32", "i64"}
            ):
                node.type = "bool"
                return node.type

            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"cannot compare {left_type} with {right_type}"
            )

        raise CompileError(
            f"line {node.line}:{node.column}: "
            f"unknown operator '{node.op}'"
        )

    def check_assignable(self, expr, want, at, what):
        have = expr.type

        if isinstance(expr, ConstNode):
            if want == "i32" and expr.value > 2147483647:
                raise CompileError(
                    f"line {expr.line}:{expr.column}: "
                    f"constant {expr.value} does not fit in i32"
                )

        if have == want:
            return

        if have == "i32" and want == "i64":
            return

        raise CompileError(
            f"line {at.line}:{at.column}: "
            f"cannot {what} of type {want} "
            f"with a value of type {have}"
        )

    def visit_exit(self, node):
        self.visit_expr(node.value)

class CodeGen:
    def __init__(self, module, builder, printf, fmt):
        self.module = module
        self.builder = builder
        self.printf = printf
        self.fmt = fmt
        self.storage = {}

        self.bool_fmt = self.make_string(
            "fmt_bool",
            b"Program exit with result %s\n\0"
        )

        self.true_text = self.make_string(
            "true_text",
            b"true\0"
        )

        self.false_text = self.make_string(
            "false_text",
            b"false\0"
        )

    def make_string(self, name, data):
        string_type = ir.ArrayType(
            I8,
            len(data),
        )

        value = ir.GlobalVariable(
            self.module,
            string_type,
            name=name,
        )

        value.linkage = "private"
        value.global_constant = True

        value.initializer = ir.Constant(
            string_type,
            bytearray(data),
        )

        return value

    def llvm_type(self, type_name):
        if type_name == "i32":
            return I32

        if type_name == "i64":
            return I64

        if type_name == "bool":
            return I1

        raise CompileError(
            f"unknown type '{type_name}'"
        )

    def coerce(self, value, have, want):
        if have == want:
            return value

        if have == "i32" and want == "i64":
            return self.builder.sext(
                value,
                I64,
                name="wide",
            )

        return value

    def generate(self, program):
        for stmt in program.statements:
            self.visit_stmt(stmt)

        self.visit_exit(program.exit_node)

    def visit_stmt(self, node):
        if isinstance(node, DeclNode):
            return self.visit_decl(node)

        if isinstance(node, AssignNode):
            return self.visit_assign(node)

        if isinstance(node, IfNode):
            return self.visit_if(node)

        if isinstance(node, WhileNode):
            return self.visit_while(node)

        raise CompileError(
            f"line {node.line}:{node.column}: unknown statement"
        )

    def visit_expr(self, node):
        if isinstance(node, ConstNode):
            return ir.Constant(
                self.llvm_type(node.type),
                node.value,
            )

        if isinstance(node, BoolNode):
            return ir.Constant(
                I1,
                1 if node.value else 0,
            )

        if isinstance(node, VarNode):
            return self.visit_var(node)

        if isinstance(node, BinOpNode):
            return self.visit_binop(node)

        if isinstance(node, NotNode):
            return self.visit_not(node)

        raise CompileError(
            f"line {node.line}:{node.column}: unknown expression"
        )

    def visit_var(self, node):
        ptr = self.storage[node.decl]

        return self.builder.load(
            ptr,
            name=f"load_{node.name}",
        )

    def visit_not(self, node):
        value = self.visit_expr(node.operand)

        return self.builder.xor(
            value,
            ir.Constant(I1, 1),
            name="nottmp",
        )

    def visit_binop(self, node):
        left = self.visit_expr(node.left)
        right = self.visit_expr(node.right)

        if node.op in {"+", "-", "*"}:
            want = node.type

            left = self.coerce(
                left,
                node.left.type,
                want,
            )

            right = self.coerce(
                right,
                node.right.type,
                want,
            )

            if node.op == "+":
                return self.builder.add(
                    left,
                    right,
                    name="addtmp",
                )

            if node.op == "-":
                return self.builder.sub(
                    left,
                    right,
                    name="subtmp",
                )

            return self.builder.mul(
                left,
                right,
                name="multmp",
            )

        if node.op in {"==", "!="}:
            if (
                node.left.type in {"i32", "i64"}
                and node.right.type in {"i32", "i64"}
            ):
                if (
                    node.left.type == "i64"
                    or node.right.type == "i64"
                ):
                    want = "i64"
                else:
                    want = "i32"

                left = self.coerce(
                    left,
                    node.left.type,
                    want,
                )

                right = self.coerce(
                    right,
                    node.right.type,
                    want,
                )

            return self.builder.icmp_signed(
                node.op,
                left,
                right,
                name="cmptmp",
            )

        raise CompileError(
            f"line {node.line}:{node.column}: "
            f"unknown operator '{node.op}'"
        )

    def create_entry_alloca(self, type_name, name):
        current_block = self.builder.block
        function = current_block.function
        entry = function.entry_basic_block

        alloca_builder = ir.IRBuilder(entry)
        alloca_builder.position_at_start(entry)

        ptr = alloca_builder.alloca(
            self.llvm_type(type_name),
            name=name,
        )

        self.builder.position_at_end(
            current_block
        )

        return ptr

    def visit_decl(self, node):
        value = self.visit_expr(node.init)

        value = self.coerce(
            value,
            node.init.type,
            node.type_name,
        )

        ptr = self.create_entry_alloca(
            node.type_name,
            node.name,
        )

        self.builder.store(
            value,
            ptr,
        )

        self.storage[node] = ptr

    def visit_assign(self, node):
        value = self.visit_expr(node.value)

        value = self.coerce(
            value,
            node.value.type,
            node.decl.type_name,
        )

        self.builder.store(
            value,
            self.storage[node.decl],
        )

    def visit_block(self, node):
        for stmt in node.statements:
            self.visit_stmt(stmt)

        if node.exit_node is not None:
            self.visit_exit(node.exit_node)

    def visit_if(self, node):
        condition = self.visit_expr(
            node.condition
        )

        function = self.builder.block.function

        then_bb = function.append_basic_block(
            "then"
        )

        if node.else_block is not None:
            else_bb = function.append_basic_block(
                "else"
            )
        else:
            else_bb = None

        merge_bb = function.append_basic_block(
            "merge"
        )

        self.builder.cbranch(
            condition,
            then_bb,
            else_bb if else_bb is not None else merge_bb,
        )

        self.builder.position_at_end(
            then_bb
        )

        self.visit_block(
            node.then_block
        )

        if not self.builder.block.is_terminated:
            self.builder.branch(
                merge_bb
            )

        if else_bb is not None:
            self.builder.position_at_end(
                else_bb
            )

            self.visit_block(
                node.else_block
            )

            if not self.builder.block.is_terminated:
                self.builder.branch(
                    merge_bb
                )

        self.builder.position_at_end(
            merge_bb
        )

    def visit_while(self, node):
        function = self.builder.block.function

        cond_bb = function.append_basic_block(
            "while.cond"
        )
        body_bb = function.append_basic_block(
            "while.body"
        )
        end_bb = function.append_basic_block(
            "while.end"
        )

        self.builder.branch(
            cond_bb
        )

        self.builder.position_at_end(
            cond_bb
        )

        condition = self.visit_expr(
            node.condition
        )

        self.builder.cbranch(
            condition,
            body_bb,
            end_bb,
        )

        self.builder.position_at_end(
            body_bb
        )

        self.visit_block(
            node.body
        )

        if not self.builder.block.is_terminated:
            self.builder.branch(
                cond_bb
            )

        self.builder.position_at_end(
            end_bb
        )

    def visit_exit(self, node):
        value = self.visit_expr(node.value)

        if node.value.type in {"i32", "i64"}:
            value = self.coerce(
                value,
                node.value.type,
                "i64",
            )

            fmt_ptr = self.builder.bitcast(
                self.fmt,
                ir.PointerType(I8),
            )

            self.builder.call(
                self.printf,
                [fmt_ptr, value],
            )

        else:
            fmt_ptr = self.builder.bitcast(
                self.bool_fmt,
                ir.PointerType(I8),
            )

            true_ptr = self.builder.bitcast(
                self.true_text,
                ir.PointerType(I8),
            )

            false_ptr = self.builder.bitcast(
                self.false_text,
                ir.PointerType(I8),
            )

            text_ptr = self.builder.select(
                value,
                true_ptr,
                false_ptr,
                name="bool_text",
            )

            self.builder.call(
                self.printf,
                [fmt_ptr, text_ptr],
            )

        self.builder.ret(
            ir.Constant(I32, 0)
        )

class Token:
    def __init__(self, kind, text, line, column):
        self.kind = kind
        self.text = text
        self.line = line
        self.column = column

    def __repr__(self):
        return (
            f"Token(kind={self.kind!r}, "
            f"text={self.text!r}, "
            f"line={self.line}, "
            f"column={self.column})"
        )


KEYWORDS = {
    "i32": "keyword",
    "i64": "keyword",
    "bool": "keyword",
    "mut": "keyword",
    "exit": "keyword",
    "true": "keyword",
    "false": "keyword",
    "if": "keyword",
    "else": "keyword",
    "while": "keyword",
}


def is_alpha(b):
    return (
        ord("a") <= b <= ord("z")
        or ord("A") <= b <= ord("Z")
        or b == ord("_")
    )


def is_digit(b):
    return ord("0") <= b <= ord("9")


def lex(data: bytes):
    lines = []
    tokens = []

    state = "START"

    i = 0
    line = 1
    col = 1

    start = 0
    start_line = 1
    start_col = 1

    while i <= len(data):
        b = data[i] if i < len(data) else None

        if state == "START":
            if b is None:
                break

            if b in (32, 9):
                i += 1
                col += 1
                continue

            if b == 10:
                lines.append(tokens)
                tokens = []

                i += 1
                line += 1
                col = 1
                continue

            if is_alpha(b):
                state = "IDENT"
                start = i
                start_line = line
                start_col = col

                i += 1
                col += 1
                continue

            if is_digit(b):
                state = "NUMBER"
                start = i
                start_line = line
                start_col = col

                i += 1
                col += 1
                continue

            if b == ord("{"):
                tokens.append(
                    Token("lbrace", "{", line, col)
                )

                i += 1
                col += 1
                continue

            if b == ord("}"):

                tokens.append(
                    Token("rbrace", "}", line, col)
                )

                i += 1
                col += 1
                continue

            if b in (
                ord("+"),
                ord("-"),
                ord("*"),
            ):
                tokens.append(
                    Token(
                        "operator",
                        chr(b),
                        line,
                        col,
                    )
                )

                i += 1
                col += 1
                continue

            if b == ord(":"):
                state = "COLON"
                start_line = line
                start_col = col

                i += 1
                col += 1
                continue

            if b == ord("="):
                state = "EQUAL"
                start_line = line
                start_col = col

                i += 1
                col += 1
                continue

            if b == ord("!"):
                state = "BANG"
                start_line = line
                start_col = col

                i += 1
                col += 1
                continue

            if b > 127:
                raise CompileError(
                    f"line {line}:{col}: unexpected byte {b}"
                )

            raise CompileError(
                f"line {line}:{col}: unexpected byte '{chr(b)}'"
            )

        elif state == "IDENT":
            if (
                b is not None
                and (is_alpha(b) or is_digit(b))
            ):
                i += 1
                col += 1
                continue

            word = data[start:i].decode("ascii")

            kind = KEYWORDS.get(
                word,
                "identifier",
            )

            tokens.append(
                Token(
                    kind,
                    word,
                    start_line,
                    start_col,
                )
            )

            state = "START"
            continue

        elif state == "NUMBER":
            if b is not None and is_digit(b):
                i += 1
                col += 1
                continue

            if b is not None and is_alpha(b):
                raise CompileError(
                    f"line {start_line}:{start_col}: "
                    "letter inside number"
                )

            number = data[start:i].decode("ascii")

            tokens.append(
                Token(
                    "number",
                    number,
                    start_line,
                    start_col,
                )
            )

            state = "START"
            continue

        elif state == "COLON":
            if b == ord("="):
                tokens.append(
                    Token(
                        "operator",
                        ":=",
                        start_line,
                        start_col,
                    )
                )

                i += 1
                col += 1
                state = "START"
                continue

            raise CompileError(
                f"line {start_line}:{start_col}: "
                "':' must be followed by '='"
            )

        elif state == "EQUAL":
            if b == ord("="):
                tokens.append(
                    Token(
                        "operator",
                        "==",
                        start_line,
                        start_col,
                    )
                )

                i += 1
                col += 1
                state = "START"
                continue

            raise CompileError(
                f"line {start_line}:{start_col}: "
                "expected '==' (a single '=' is not an operator)"
            )

        elif state == "BANG":
            if b == ord("="):
                tokens.append(
                    Token(
                        "operator",
                        "!=",
                        start_line,
                        start_col,
                    )
                )

                i += 1
                col += 1
                state = "START"
                continue

            tokens.append(
                Token(
                    "operator",
                    "!",
                    start_line,
                    start_col,
                )
            )

            state = "START"
            continue

    if tokens:
        lines.append(tokens)

    return lines


def error(token, message):
    raise CompileError(
        f"line {token.line}:{token.column}: {message}"
    )


def load_variable(token, symbols, builder):
    name = token.text

    if name not in symbols:
        error(
            token,
            f"variable '{name}' is used before its declaration"
        )

    return builder.load(
        symbols[name]["ptr"],
        name=f"load_{name}",
    )


def operand_value(token, symbols, builder):
    if token.kind == "number":
        return ir.Constant(
            I32,
            int(token.text),
        )

    if token.kind == "identifier":
        return load_variable(
            token,
            symbols,
            builder,
        )

    error(
        token,
        "expected a number or variable"
    )


def parse_expression(tokens, symbols, builder):
    if len(tokens) == 1:
        return operand_value(
            tokens[0],
            symbols,
            builder,
        )

    if len(tokens) == 3:
        left_token = tokens[0]
        operator_token = tokens[1]
        right_token = tokens[2]

        if operator_token.kind != "operator":
            error(
                operator_token,
                "expected arithmetic operator"
            )

        if operator_token.text not in {"+", "-", "*"}:
            error(
                operator_token,
                "expected '+', '-' or '*'"
            )

        left = operand_value(
            left_token,
            symbols,
            builder,
        )

        right = operand_value(
            right_token,
            symbols,
            builder,
        )

        if operator_token.text == "+":
            return builder.add(
                left,
                right,
                name="addtmp",
            )

        if operator_token.text == "-":
            return builder.sub(
                left,
                right,
                name="subtmp",
            )

        return builder.mul(
            left,
            right,
            name="multmp",
        )

    token = tokens[0]

    error(
        token,
        "invalid expression"
    )


def parse_declaration(tokens, symbols, builder):
    type_token = tokens[0]

    index = 1
    mutable = False

    if (
        index < len(tokens)
        and tokens[index].kind == "keyword"
        and tokens[index].text == "mut"
    ):
        mutable = True
        index += 1

    if index >= len(tokens):
        error(
            type_token,
            "expected variable name"
        )

    name_token = tokens[index]

    if name_token.kind != "identifier":
        error(
            name_token,
            "expected variable name"
        )

    name = name_token.text
    index += 1

    if name in symbols:
        error(
            name_token,
            f"variable '{name}' is already declared"
        )

    if (
        index >= len(tokens)
        or tokens[index].kind != "lbrace"
    ):
        error(
            name_token,
            f"variable '{name}' needs an initialiser in {{}}"
        )

    index += 1

    expression_start = index

    while (
        index < len(tokens)
        and tokens[index].kind != "rbrace"
    ):
        index += 1

    if index >= len(tokens):
        error(
            tokens[expression_start - 1],
            "'{' is not closed"
        )

    expression_tokens = tokens[
        expression_start:index
    ]

    if not expression_tokens:
        error(
            tokens[index],
            "initialiser cannot be empty"
        )

    value = parse_expression(
        expression_tokens,
        symbols,
        builder,
    )

    index += 1

    if index != len(tokens):
        error(
            tokens[index],
            "extra tokens after declaration"
        )

    ptr = builder.alloca(
        I32,
        name=name,
    )

    builder.store(
        value,
        ptr,
    )

    symbols[name] = {
        "ptr": ptr,
        "mutable": mutable,
    }


def parse_assignment(tokens, symbols, builder):
    target_token = tokens[0]

    if target_token.kind != "identifier":
        error(
            target_token,
            "expected variable name"
        )

    name = target_token.text

    if name not in symbols:
        error(
            target_token,
            f"variable '{name}' is used before its declaration"
        )

    if not symbols[name]["mutable"]:
        error(
            target_token,
            f"cannot assign to '{name}': it is not mut"
        )

    if len(tokens) < 3:
        error(
            target_token,
            "assignment needs a value"
        )

    assignment_token = tokens[1]

    if (
        assignment_token.kind != "operator"
        or assignment_token.text != ":="
    ):
        error(
            assignment_token,
            "expected ':='"
        )

    expression_tokens = tokens[2:]

    value = parse_expression(
        expression_tokens,
        symbols,
        builder,
    )

    builder.store(
        value,
        symbols[name]["ptr"],
    )


def parse_exit(
    tokens,
    symbols,
    builder,
    printf,
    fmt,
):
    exit_token = tokens[0]

    if len(tokens) != 2:
        error(
            exit_token,
            "exit expects one constant or variable"
        )

    value_token = tokens[1]

    if value_token.kind == "number":
        value = ir.Constant(
            I32,
            int(value_token.text),
        )

    elif value_token.kind == "identifier":
        value = load_variable(
            value_token,
            symbols,
            builder,
        )

    else:
        error(
            value_token,
            "exit expects a constant or variable"
        )

    fmt_ptr = builder.bitcast(
        fmt,
        ir.PointerType(I8),
    )

    builder.call(
        printf,
        [fmt_ptr, value],
    )

    builder.ret(
        ir.Constant(I32, 0)
    )


def compile_program(source_path, output_path):
    with open(source_path, "rb") as f:
        data = f.read()

    token_lines = lex(data)

    parser = Parser(token_lines)
    tree = parser.parse_program()

    checker = SemanticChecker()
    checker.check(tree)

    module = ir.Module(name="practice3")
    module.triple = llvm.get_default_triple()

    main_type = ir.FunctionType(
        I32,
        [],
    )

    main = ir.Function(
        module,
        main_type,
        name="main",
    )

    entry = main.append_basic_block("entry")
    builder = ir.IRBuilder(entry)

    printf_type = ir.FunctionType(
        I32,
        [ir.PointerType(I8)],
        var_arg=True,
    )

    printf = ir.Function(
        module,
        printf_type,
        name="printf",
    )

    text = b"Program exit with result %lld\n\0"

    fmt_type = ir.ArrayType(
        I8,
        len(text),
    )

    fmt = ir.GlobalVariable(
        module,
        fmt_type,
        name="fmt",
    )

    fmt.linkage = "private"
    fmt.global_constant = True
    fmt.initializer = ir.Constant(
        fmt_type,
        bytearray(text),
    )

    codegen = CodeGen(
        module,
        builder,
        printf,
        fmt,
    )

    codegen.generate(tree)

    with open(output_path, "w") as f:
        f.write(str(module))

def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--ast":
        source_path = sys.argv[2]

        try:
            with open(source_path, "rb") as f:
                data = f.read()

            token_lines = lex(data)

            parser = Parser(token_lines)
            tree = parser.parse_program()

            for line in tree.dump():
                print(line)

        except CompileError as e:
            print(
                f"compilation error: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

        except FileNotFoundError:
            print(
                f"compilation error: source file "
                f"'{source_path}' not found",
                file=sys.stderr,
            )
            sys.exit(1)

        return

    if len(sys.argv) != 3:
        print(
            "usage:",
            file=sys.stderr,
        )
        print(
            "  python3 compiler.py <source> <output.ll>",
            file=sys.stderr,
        )
        print(
            "  python3 compiler.py --ast <source>",
            file=sys.stderr,
        )
        sys.exit(1)

    source_path = sys.argv[1]
    output_path = sys.argv[2]

    if os.path.exists(output_path):
        os.remove(output_path)

    try:
        compile_program(
            source_path,
            output_path,
        )

    except CompileError as e:
        if os.path.exists(output_path):
            os.remove(output_path)

        print(
            f"compilation error: {e}",
            file=sys.stderr,
        )

        sys.exit(1)

    except FileNotFoundError:
        if os.path.exists(output_path):
            os.remove(output_path)

        print(
            f"compilation error: source file "
            f"'{source_path}' not found",
            file=sys.stderr,
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
