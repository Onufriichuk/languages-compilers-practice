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


class FieldDeclNode(Node):
    def __init__(self, line, column, name, type_name, mutable):
        super().__init__(line, column)
        self.name = name
        self.type_name = type_name
        self.mutable = mutable

    def dump(self, indent=0):
        kind = "mut" if self.mutable else "const"

        return [
            " " * indent
            + f"Field {self.name} {self.type_name} {kind}"
        ]


class StructNode(Node):
    def __init__(self, line, column, name, fields, methods=None):
        super().__init__(line, column)
        self.name = name
        self.fields = fields
        self.methods = methods or []

    def dump(self, indent=0):
        lines = [
            " " * indent + f"Struct {self.name}"
        ]

        for field in self.fields:
            lines.extend(
                field.dump(indent + 2)
            )

        for method in self.methods:
            lines.extend(method.dump(indent + 2))
        return lines


class ProgramNode(Node):
    def __init__(
        self,
        structs,
        functions,
        statements,
        exit_node,
    ):
        super().__init__(1, 1)
        self.structs = structs
        self.functions = functions
        self.statements = statements
        self.exit_node = exit_node

    def dump(self, indent=0):
        lines = [" " * indent + "Program"]

        for struct in self.structs:
            lines.extend(
                struct.dump(indent + 2)
            )

        for function in self.functions:
            lines.extend(
                function.dump(indent + 2)
            )

        for stmt in self.statements:
            lines.extend(
                stmt.dump(indent + 2)
            )

        lines.extend(
            self.exit_node.dump(indent + 2)
        )

        return lines


class ParamNode(Node):
    def __init__(self, line, column, name, type_name):
        super().__init__(line, column)
        self.name = name
        self.type_name = type_name
        self.mutable = False

    def dump(self, indent=0):
        return [
            " " * indent
            + f"Param {self.name} {self.type_name}"
        ]


class FunctionNode(Node):
    def __init__(
        self,
        line,
        column,
        name,
        params,
        result_type,
        body,
    ):
        super().__init__(line, column)
        self.name = name
        self.params = params
        self.result_type = result_type
        self.body = body

    def dump(self, indent=0):
        lines = [
            " " * indent
            + f"Function {self.name} -> {self.result_type}"
        ]

        for param in self.params:
            lines.extend(
                param.dump(indent + 2)
            )

        lines.extend(
            self.body.dump(indent + 2)
        )

        return lines


class MemberFnNode(FunctionNode):
    def dump(self, indent=0):
        lines = [" " * indent + f"MemberFn {self.name} -> {self.result_type}"]
        for param in self.params:
            lines.extend(param.dump(indent + 2))
        lines.extend(self.body.dump(indent + 2))
        return lines

class LambdaNode(Node):
    def __init__(self, function, captures):
        super().__init__(function.line, function.column)
        self.name = function.name
        self.function = function
        self.captures = captures

    def dump(self, indent=0):
        lines = [' ' * indent + f"Lambda {self.name} -> {self.function.result_type}"]
        for tok, mutable in self.captures:
            lines.append(' ' * (indent + 2) + f"Capture {tok.text} {'mut' if mutable else 'const'}")
        if hasattr(self, 'generated_struct'):
            lines.extend(self.generated_struct.dump(indent + 2))
            lines.extend(self.generated_decl.dump(indent + 2))
        else:
            lines.extend(self.function.body.dump(indent + 2))
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
    def __init__(self, line, column, target, value):
        super().__init__(line, column)
        self.target = target
        self.value = value

    def dump(self, indent=0):
        lines = [
            " " * indent + "Assign"
        ]

        lines.extend(
            self.target.dump(indent + 2)
        )

        lines.extend(
            self.value.dump(indent + 2)
        )

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


class StructInitNode(ExprNode):
    def __init__(self, line, column, values):
        super().__init__(line, column)
        self.values = values

    def dump(self, indent=0):
        lines = [
            " " * indent + "StructInit"
        ]

        for value in self.values:
            lines.extend(
                value.dump(indent + 2)
            )

        return lines


class InitListNode(ExprNode):
    def __init__(self, line, column, values):
        super().__init__(line, column)
        self.values = values

    def dump(self, indent=0):
        lines = [
            " " * indent + "InitList"
        ]

        for value in self.values:
            lines.extend(
                value.dump(indent + 2)
            )

        return lines


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


class CallNode(ExprNode):
    def __init__(self, line, column, name, args):
        super().__init__(line, column)
        self.name = name
        self.args = args

    def dump(self, indent=0):
        lines = [
            " " * indent + (f"CallableCall {self.name}" if hasattr(self, "callable_member") else f"Call {self.name}")
        ]

        for arg in self.args:
            lines.extend(
                arg.dump(indent + 2)
            )

        return lines


class MemberCallNode(ExprNode):
    def __init__(self, line, column, receiver, name, args):
        super().__init__(line, column)
        self.receiver = receiver
        self.name = name
        self.args = args

    def dump(self, indent=0):
        lines = [" " * indent + f"MemberCall {self.name}"]
        lines.extend(self.receiver.dump(indent + 2))
        for arg in self.args:
            lines.extend(arg.dump(indent + 2))
        return lines


class ChainFieldNode(ExprNode):
    def __init__(self, line, column, receiver, name):
        super().__init__(line, column)
        self.receiver = receiver
        self.name = name

    def dump(self, indent=0):
        lines = [" " * indent + f"Field {self.name}"]
        lines.extend(self.receiver.dump(indent + 2))
        return lines

class VarNode(ExprNode):
    def __init__(self, line, column, name):
        super().__init__(line, column)
        self.name = name

    def dump(self, indent=0):
        return [
            " " * indent + f"Var {self.name}"
        ]


class FieldAccessNode(ExprNode):
    def __init__(self, line, column, base_name, fields):
        super().__init__(line, column)
        self.base_name = base_name
        self.fields = fields

    def dump(self, indent=0):
        path = ".".join(
            [self.base_name] + self.fields
        )

        return [
            " " * indent + f"FieldAccess {path}"
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

class StringNode(ExprNode):
    def __init__(self, line, column, value):
        super().__init__(line, column)
        self.value = value

    def dump(self, indent=0):
        return [" " * indent + f"String {self.value!r}"]


class PrintNode(StmtNode):
    def __init__(self, line, column, value):
        super().__init__(line, column)
        self.value = value

    def dump(self, indent=0):
        lines = [" " * indent + "Print"]
        lines.extend(self.value.dump(indent + 2))
        return lines

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
        structs = []
        functions = []
        statements = []
        exit_node = None

        phase = "structs"

        while self.next_line():
            first = self.peek()

            if (
                first.kind == "keyword"
                and first.text == "struct"
            ):
                if phase != "structs":
                    raise CompileError(
                        f"line {first.line}:{first.column}: "
                        "struct declaration must appear "
                        "before functions and statements"
                    )

                structs.append(
                    self.parse_struct()
                )
                continue

            if (
                first.kind == "keyword"
                and first.text == "fn"
            ):
                if any(t.kind == "lbracket" for t in self.toks):
                    phase = "statements"
                    statements.append(self.parse_lambda())
                    continue
                if phase == "statements":
                    raise CompileError(
                        f"line {first.line}:{first.column}: "
                        "function declaration must appear "
                        "before statements"
                    )

                phase = "functions"

                functions.append(
                    self.parse_function()
                )
                continue

            if (
                first.kind == "keyword"
                and first.text == "exit"
            ):
                exit_node = self.parse_exit()

                if self.peek() is not None:
                    tok = self.peek()

                    raise CompileError(
                        f"line {tok.line}:{tok.column}: "
                        f"unexpected '{tok.text}' "
                        "after the statement"
                    )

                if self.peek_line() is not None:
                    tok = self.peek_line()[0]

                    raise CompileError(
                        f"line {tok.line}:{tok.column}: "
                        "code after exit is not allowed"
                    )

                break

            phase = "statements"

            statements.append(
                self.parse_statement()
            )

            if self.peek() is not None:
                tok = self.peek()

                raise CompileError(
                    f"line {tok.line}:{tok.column}: "
                    f"unexpected '{tok.text}' "
                    "after the statement"
                )

        if exit_node is None:
            raise CompileError(
                "line 1:1: program needs an exit statement"
            )

        return ProgramNode(
            structs,
            functions,
            statements,
            exit_node,
        )

    def parse_type(self):
        tok = self.peek()

        if tok is None:
            self.error_end(
                "expected a type"
            )

        if (
            tok.kind == "keyword"
            and tok.text in {"i32", "i64", "bool"}
        ):
            return self.eat()

        if tok.kind == "identifier":
            return self.eat()

        raise CompileError(
            f"line {tok.line}:{tok.column}: "
            f"expected a type, got '{tok.text}'"
        )

    def parse_struct(self):
        struct_tok = self.expect_text(
            "struct",
            "expected 'struct'"
        )

        name = self.expect_kind(
            "identifier",
            "expected struct name"
        )

        if self.peek() is not None:
            tok = self.peek()

            raise CompileError(
                f"line {tok.line}:{tok.column}: "
                f"unexpected '{tok.text}' after struct name"
            )

        if not self.next_line():
            raise CompileError(
                f"line {struct_tok.line}:{struct_tok.column}: "
                "expected '{' after struct declaration"
            )

        tok = self.peek()

        if (
            tok is None
            or tok.kind != "lbrace"
            or len(self.toks) != 1
        ):
            raise CompileError(
                f"line {tok.line}:{tok.column}: "
                "expected '{' on its own line"
            )

        fields = []
        methods = []

        while True:
            if not self.next_line():
                raise CompileError(
                    f"line {struct_tok.line}:{struct_tok.column}: "
                    "struct is never closed"
                )

            first = self.peek()

            if (
                first.kind == "rbrace"
                and len(self.toks) == 1
            ):
                if not fields:
                    raise CompileError(
                        f"line {first.line}:{first.column}: "
                        "struct must contain at least one field"
                    )

                self.eat()

                return StructNode(
                    struct_tok.line,
                    struct_tok.column,
                    name.text,
                    fields,
                    methods,
                )

            if first.text == "fn":
                if not fields:
                    raise CompileError(f"line {first.line}:{first.column}: member function before first field")
                method = self.parse_function()
                methods.append(MemberFnNode(method.line, method.column, method.name,
                                            method.params, method.result_type, method.body))
                continue
            if methods:
                raise CompileError(f"line {first.line}:{first.column}: field after member function")

            type_tok = self.parse_type()

            mutable = False

            tok = self.peek()

            if (
                tok is not None
                and tok.kind == "keyword"
                and tok.text == "mut"
            ):
                self.eat()
                mutable = True

            field_name = self.expect_kind(
                "identifier",
                "expected field name"
            )

            if self.peek() is not None:
                tok = self.peek()

                raise CompileError(
                    f"line {tok.line}:{tok.column}: "
                    f"unexpected '{tok.text}' after field declaration"
                )

            fields.append(
                FieldDeclNode(
                    field_name.line,
                    field_name.column,
                    field_name.text,
                    type_tok.text,
                    mutable,
                )
            )

    def parse_function(self):
        fn_tok = self.expect_text(
            "fn",
            "expected 'fn'"
        )

        name = self.expect_kind(
            "identifier",
            "expected function name"
        )

        self.expect_text(
            ":=",
            "expected ':=' after function name"
        )

        self.expect_kind(
            "lparen",
            "expected '(' after ':='"
        )

        params = []

        if (
            self.peek() is not None
            and self.peek().kind != "rparen"
        ):
            while True:
                type_tok = self.parse_type()

                param_name = self.expect_kind(
                    "identifier",
                    "expected parameter name"
                )

                params.append(
                    ParamNode(
                        param_name.line,
                        param_name.column,
                        param_name.text,
                        type_tok.text,
                    )
                )

                tok = self.peek()

                if (
                    tok is not None
                    and tok.kind == "comma"
                ):
                    self.eat()
                    continue

                break

        self.expect_kind(
            "rparen",
            "expected ')'"
        )

        self.expect_kind(
            "arrow",
            "expected '->'"
        )

        result_type = self.parse_type()

        if self.peek() is not None:
            tok = self.peek()

            raise CompileError(
                f"line {tok.line}:{tok.column}: "
                f"unexpected '{tok.text}' "
                "after function declaration"
            )

        if not self.next_line():
            raise CompileError(
                f"line {fn_tok.line}:{fn_tok.column}: "
                "expected function body"
            )

        tok = self.peek()

        if (
            tok is None
            or tok.kind != "lbrace"
            or len(self.toks) != 1
        ):
            raise CompileError(
                f"line {tok.line}:{tok.column}: "
                "expected '{' on its own line "
                "after function declaration"
            )

        body = self.parse_block()

        if body.exit_node is None:
            raise CompileError(
                f"line {fn_tok.line}:{fn_tok.column}: "
                f"function '{name.text}' must end with exit"
            )

        return FunctionNode(
            fn_tok.line,
            fn_tok.column,
            name.text,
            params,
            result_type.text,
            body,
        )

    def parse_lambda(self):
        original = list(self.toks)
        start = self.pos
        fn_tok = self.expect_text("fn", "expected fn")
        self.expect_kind("identifier", "expected lambda name")
        self.expect_text(":=", "expected ':='")
        self.expect_kind("lbracket", "expected '[' for captures")
        captures = []
        seen = set()
        while self.peek() is not None and self.peek().kind != "rbracket":
            mutable = False
            if self.peek().text == "mut":
                self.eat()
                mutable = True
            tok = self.expect_kind("identifier", "expected capture name")
            if tok.text in seen:
                raise CompileError(f"line {tok.line}:{tok.column}: '{tok.text}' is captured twice")
            seen.add(tok.text)
            captures.append((tok, mutable))
            if self.peek() is None or self.peek().kind != "comma":
                break
            self.eat()
        self.expect_kind("rbracket", "expected ']' after captures")
        remainder = self.toks[self.pos:]
        self.toks = original[:start+3] + remainder
        self.pos = start
        function = self.parse_function()
        return LambdaNode(function, captures)

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

        if tok.kind == "keyword" and tok.text == "fn":
            if any(t.kind == "lbracket" for t in self.toks):
                return self.parse_lambda()
            raise CompileError(f"line {tok.line}:{tok.column}: function inside block needs capture list")

        if tok.kind == "keyword" and tok.text == "print":
            self.eat()
            self.expect_kind("lparen", "expected '(' after print")
            arg = self.peek()
            if arg is None or arg.kind == "rparen":
                self.error_end("print expects one argument")
            if arg.kind == "string":
                self.eat()
                value = StringNode(arg.line, arg.column, arg.text)
            else:
                value = self.parse_expr()
            self.expect_kind("rparen", "expected ')' after print argument")
            return PrintNode(tok.line, tok.column, value)

        if tok.kind == "identifier":
            next_pos = self.pos + 1

            if next_pos < len(self.toks):
                next_tok = self.toks[next_pos]

                if (
                    next_tok.kind == "identifier"
                    or (
                        next_tok.kind == "keyword"
                        and next_tok.text == "mut"
                    )
                ):
                    return self.parse_decl()

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
        type_tok = self.parse_type()

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

        if (
            self.peek() is not None
            and self.peek().kind == "rbrace"
        ):
            raise CompileError(
                f"line {open_brace.line}:{open_brace.column}: "
                "initialiser cannot be empty"
            )

        values = [
            self.parse_expr()
        ]

        while (
            self.peek() is not None
            and self.peek().kind == "comma"
        ):
            self.eat()

            values.append(
                self.parse_expr()
            )

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

        if len(values) == 1:
            init = values[0]
        else:
            init = InitListNode(
                open_brace.line,
                open_brace.column,
                values,
            )

        return DeclNode(
            name.line,
            name.column,
            name.text,
            type_tok.text,
            mutable,
            init,
        )

    def parse_call(self):
        name = self.expect_kind(
            "identifier",
            "expected function name"
        )

        self.expect_kind(
            "lparen",
            "expected '('"
        )

        args = []

        if (
            self.peek() is not None
            and self.peek().kind != "rparen"
        ):
            while True:
                args.append(
                    self.parse_expr()
                )

                tok = self.peek()

                if (
                    tok is not None
                    and tok.kind == "comma"
                ):
                    self.eat()
                    continue

                break

        self.expect_kind(
            "rparen",
            "expected ')'"
        )

        return CallNode(
            name.line,
            name.column,
            name.text,
            args,
        )

    def parse_access(self):
        name = self.expect_kind(
            "identifier",
            "expected variable name"
        )

        fields = []

        while (
            self.peek() is not None
            and self.peek().kind == "dot"
        ):
            self.eat()

            field = self.expect_kind(
                "identifier",
                "expected field name after '.'"
            )

            fields.append(
                field.text
            )

        if not fields:
            return VarNode(
                name.line,
                name.column,
                name.text,
            )

        return FieldAccessNode(
            name.line,
            name.column,
            name.text,
            fields,
        )

    def parse_assign(self):
        target = self.parse_access()

        tok = self.peek()

        if (
            tok is None
            or tok.kind != "operator"
            or tok.text != ":="
        ):
            if tok is None:
                self.error_end(
                    "expected ':=' after assignment target"
                )

            raise CompileError(
                f"line {tok.line}:{tok.column}: "
                f"expected ':=' after assignment target, "
                f"got '{tok.text}'"
            )

        self.eat()

        value = self.parse_expr()

        return AssignNode(
            target.line,
            target.column,
            target,
            value,
        )

    def parse_exit(self):
        exit_tok = self.expect_text(
            "exit",
            "expected 'exit'"
        )

        value = self.parse_expr()

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

    def parse_struct_init(self):
        open_tok = self.expect_kind(
            "lbrace",
            "expected '{'"
        )

        values = []

        if (
            self.peek() is not None
            and self.peek().kind == "rbrace"
        ):
            raise CompileError(
                f"line {open_tok.line}:{open_tok.column}: "
                "struct initialiser cannot be empty"
            )

        while True:
            if (
                self.peek() is not None
                and self.peek().kind == "lbrace"
            ):
                value = self.parse_struct_init()
            else:
                value = self.parse_expr()

            values.append(
                value
            )

            tok = self.peek()

            if (
                tok is not None
                and tok.kind == "comma"
            ):
                self.eat()
                continue

            break

        self.expect_kind(
            "rbrace",
            "expected '}'"
        )

        return StructInitNode(
            open_tok.line,
            open_tok.column,
            values,
        )

    def parse_args(self):
        self.expect_kind("lparen", "expected '('")
        args = []
        if self.peek() is not None and self.peek().kind != "rparen":
            while True:
                args.append(self.parse_expr())
                if self.peek() is not None and self.peek().kind == "comma":
                    self.eat()
                    continue
                break
        self.expect_kind("rparen", "expected ')'")
        return args

    def parse_factor(self):
        tok = self.peek()
        if tok is None:
            self.error_end("expected a constant or a variable")
        if tok.kind == "lbrace":
            return self.parse_struct_init()
        if tok.kind == "operator" and tok.text == "!":
            self.eat()
            return NotNode(tok.line, tok.column, self.parse_factor())
        if tok.kind == "number":
            self.eat()
            node = ConstNode(tok.line, tok.column, int(tok.text))
        elif tok.kind == "keyword" and tok.text in {"true", "false"}:
            self.eat()
            node = BoolNode(tok.line, tok.column, tok.text == "true")
        elif tok.kind == "identifier" or (tok.kind == "keyword" and tok.text == "read"):
            self.eat()
            if self.peek() is not None and self.peek().kind == "lparen":
                node = CallNode(tok.line, tok.column, tok.text, self.parse_args())
            else:
                node = VarNode(tok.line, tok.column, tok.text)
        else:
            raise CompileError(f"line {tok.line}:{tok.column}: expected a constant or a variable, got '{tok.text}'")
        while self.peek() is not None and self.peek().kind == "dot":
            dot = self.eat()
            name = self.expect_kind("identifier", "expected field or method after '.'")
            if self.peek() is not None and self.peek().kind == "lparen":
                node = MemberCallNode(name.line, name.column, node, name.text, self.parse_args())
            elif isinstance(node, VarNode):
                node = FieldAccessNode(node.line, node.column, node.name, [name.text])
            elif isinstance(node, FieldAccessNode):
                node.fields.append(name.text)
            else:
                node = ChainFieldNode(dot.line, dot.column, node, name.text)
        return node

class SemanticChecker:
    def __init__(self):
        self.scopes = [{}]
        self.structs = {}
        self.functions = {}
        self.current_function_result = None
        self.current_struct = None
        self.active_member = None
        self.member_calls = []
        self.program = None
        self.lambda_names = set()
        self.forbidden_outer = set()

    def lookup(self, node, name):
        for frame in reversed(self.scopes):
            if name in frame:
                return frame[name]

        if self.current_struct is not None:
            for field in self.current_struct.fields:
                if field.name == name:
                    return field
        if name in self.forbidden_outer:
            raise CompileError(f"line {node.line}:{node.column}: '{name}' is not captured by lambda: add it to the capture list")
        raise CompileError(
            f"line {node.line}:{node.column}: "
            f"variable '{name}' is used before its declaration"
        )

    def check(self, program):
        self.program = program
        for struct in program.structs:
            self.visit_struct(struct)

        for struct in program.structs:
            struct.method_map = {}
            for method in struct.methods:
                if method.name in {"read", "print"} or method.name in struct.method_map or any(f.name == method.name for f in struct.fields):
                    raise CompileError(f"line {method.line}:{method.column}: duplicate member name '{method.name}'")
                struct.method_map[method.name] = method
                self.validate_signature(method)
        for function in program.functions:
            self.collect_function(
                function
            )

        for struct in program.structs:
            for method in struct.methods:
                self.current_struct = struct
                self.visit_function(method)
                self.current_struct = None
        for function in program.functions:
            self.visit_function(
                function
            )

        self.scopes = [{}]

        for stmt in program.statements:
            self.visit_stmt(stmt)

        self.current_function_result = None

        self.visit_exit(program.exit_node)
        changed = True
        while changed:
            changed = False
            for struct in program.structs:
                for method in struct.methods:
                    if not getattr(method, "mutating", False) and any(
                        getattr(target, "mutating", False) for target in getattr(method, "same_object_calls", [])
                    ):
                        method.mutating = True
                        changed = True
        for call in self.member_calls:
            if call.method.mutating and not getattr(call, "temporary", False):
                receiver = call.receiver
                if not getattr(receiver, "mutable_path", False):
                    raise CompileError(f"line {call.line}:{call.column}: mutating call through const link")

    def validate_signature(self, node):
        if node.result_type not in {"i32", "i64", "bool"} | set(self.structs):
            raise CompileError(f"line {node.line}:{node.column}: unknown return type '{node.result_type}'")
        seen = set()
        for param in node.params:
            if param.name in seen or param.name in {"read", "print"}:
                raise CompileError(f"line {param.line}:{param.column}: invalid or duplicate parameter '{param.name}'")
            seen.add(param.name)
            if param.type_name not in {"i32", "i64", "bool"} | set(self.structs):
                raise CompileError(f"line {param.line}:{param.column}: unknown parameter type '{param.type_name}'")

    def visit_struct(self, node):
        if node.name in self.structs:
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"struct '{node.name}' is already declared"
            )

        field_names = set()

        for field in node.fields:
            if field.name in {"read", "print"} or field.name in field_names:
                raise CompileError(
                    f"line {field.line}:{field.column}: "
                    f"field '{field.name}' is already declared"
                )

            field_names.add(field.name)

            if field.type_name == node.name:
                raise CompileError(
                    f"line {field.line}:{field.column}: "
                    "struct cannot contain itself"
                )

            if (
                field.type_name not in {"i32", "i64", "bool"}
                and field.type_name not in self.structs
            ):
                raise CompileError(
                    f"line {field.line}:{field.column}: "
                    f"unknown type '{field.type_name}'"
                )

        self.structs[node.name] = node

    def collect_function(self, node):
        if node.name in {"read", "print"} or node.name in self.functions:
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"function '{node.name}' "
                "is already declared"
            )

        if (
            node.result_type not in {"i32", "i64", "bool"}
            and node.result_type not in self.structs
        ):
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"unknown result type "
                f"'{node.result_type}'"
            )

        param_names = set()

        for param in node.params:
            if param.name in param_names:
                raise CompileError(
                    f"line {param.line}:{param.column}: "
                    f"parameter '{param.name}' "
                    "is already declared"
                )

            param_names.add(
                param.name
            )

            if (
                param.type_name not in {"i32", "i64", "bool"}
                and param.type_name not in self.structs
            ):
                raise CompileError(
                    f"line {param.line}:{param.column}: "
                    f"unknown parameter type "
                    f"'{param.type_name}'"
                )

        self.validate_signature(node)
        self.functions[node.name] = node

    def visit_function(self, node):
        old_scopes = self.scopes
        old_result = self.current_function_result

        self.scopes = [{}]
        self.current_function_result = node.result_type
        if isinstance(node, MemberFnNode):
            node.mutating = False
            node.same_object_calls = []
        old_active = self.active_member
        self.active_member = node if isinstance(node, MemberFnNode) else None
        try:
            frame = self.scopes[-1]

            for param in node.params:
                frame[
                    param.name
                ] = param

            self.visit_block(
                node.body
            )

        finally:
            self.scopes = old_scopes
            self.current_function_result = old_result
            self.active_member = old_active

    def visit_stmt(self, node):
        if isinstance(node, LambdaNode):
            return self.visit_lambda(node)
        if isinstance(node, DeclNode):
            return self.visit_decl(node)

        if isinstance(node, AssignNode):
            return self.visit_assign(node)

        if isinstance(node, IfNode):
            return self.visit_if(node)

        if isinstance(node, WhileNode):
            return self.visit_while(node)
        if isinstance(node, PrintNode):
            if isinstance(node.value, VarNode):
                decl = next((scope[node.value.name] for scope in reversed(self.scopes) if node.value.name in scope), None)
                if decl is not None and decl.type_name.startswith('lambda.'):
                    raise CompileError(f"line {node.value.line}:{node.value.column}: lambda '{node.value.name}' cannot be printed")
            if isinstance(node.value, StringNode):
                node.value.type = "string"
            else:
                self.visit_expr(node.value)
            return

        raise CompileError(
            f"line {node.line}:{node.column}: unknown statement"
        )

    def visit_lambda(self, node):
        frame = self.scopes[-1]
        if node.name in frame or node.name in {'read', 'print'}:
            raise CompileError(f"line {node.line}:{node.column}: variable '{node.name}' is already declared")
        fields = []
        values = []
        for tok, mutable in node.captures:
            try:
                decl = self.lookup(tok, tok.text)
            except CompileError:
                raise CompileError(f"line {tok.line}:{tok.column}: cannot capture '{tok.text}': no variable '{tok.text}' is visible here")
            field = FieldDeclNode(tok.line, tok.column, tok.text, decl.type_name, mutable)
            fields.append(field)
            values.append(VarNode(tok.line, tok.column, tok.text))
            self.visit_var(values[-1])
        name = f"lambda.{node.name}.{node.line}.{node.column}" if node.name in self.lambda_names else f"lambda.{node.name}"
        self.lambda_names.add(node.name)
        method = MemberFnNode(node.line, node.column, 'call', node.function.params,
                              node.function.result_type, node.function.body)
        struct = StructNode(node.line, node.column, name, fields, [method])
        struct.method_map = {'call': method}
        self.structs[name] = struct
        self.program.structs.append(struct)
        self.validate_signature(method)
        overlap = {f.name for f in fields} & {param.name for param in method.params}
        if overlap:
            conflict = next(param for param in method.params if param.name in overlap)
            raise CompileError(f"line {conflict.line}:{conflict.column}: parameter '{conflict.name}' conflicts with lambda capture")
        decl = DeclNode(node.line, node.column, node.name, name,
                        any(m for _, m in node.captures), InitListNode(node.line, node.column, values))
        decl.struct_def = struct
        node.generated_struct = struct
        node.generated_decl = decl
        old_struct, old_active, old_forbidden = self.current_struct, self.active_member, self.forbidden_outer
        self.forbidden_outer = {k for scope in self.scopes for k in scope} - {f.name for f in fields}
        self.current_struct = struct
        try:
            self.visit_function(method)
        finally:
            self.current_struct, self.active_member, self.forbidden_outer = old_struct, old_active, old_forbidden
        frame[node.name] = decl
        return None

    def visit_expr(self, node):
        if isinstance(node, ConstNode):
            return self.visit_const(node)

        if isinstance(node, BoolNode):
            return self.visit_bool(node)

        if isinstance(node, VarNode):
            return self.visit_var(node)

        if isinstance(node, FieldAccessNode):
            return self.visit_field_access(node)

        if isinstance(node, CallNode):
            return self.visit_call(node)
        if isinstance(node, MemberCallNode):
            return self.visit_member_call(node)
        if isinstance(node, ChainFieldNode):
            return self.visit_chain_field(node)

        if isinstance(node, BinOpNode):
            return self.visit_binop(node)

        if isinstance(node, NotNode):
            return self.visit_not(node)

        if isinstance(node, StructInitNode):
            raise CompileError(
                f"line {node.line}:{node.column}: "
                "nested struct initialiser needs an expected struct type"
            )

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
        node.mutable_path = getattr(node.decl, "mutable", False)
        node.is_lvalue = True
        return node.type

    def visit_field_access(self, node):
        decl = self.lookup(
            node,
            node.base_name,
        )

        node.decl = decl
        node.is_lvalue = True

        current_type = decl.type_name
        if current_type.startswith('lambda.'):
            raise CompileError(f"line {node.line}:{node.column}: lambda captures are private")
        node.field_indices = []
        node.field_defs = []

        for field_name in node.fields:
            if current_type not in self.structs:
                raise CompileError(
                    f"line {node.line}:{node.column}: "
                    f"type '{current_type}' has no fields"
                )

            struct = self.structs[current_type]

            found = None

            for index, field in enumerate(
                struct.fields
            ):
                if field.name == field_name:
                    found = (
                        index,
                        field,
                    )
                    break

            if found is None:
                raise CompileError(
                    f"line {node.line}:{node.column}: "
                    f"struct '{current_type}' has no field "
                    f"'{field_name}'"
                )

            index, field = found

            node.field_indices.append(
                index
            )

            node.field_defs.append(
                field
            )

            current_type = field.type_name

        node.type = current_type
        node.mutable_path = decl.mutable and all(f.mutable for f in node.field_defs)
        return node.type

    def visit_call(self, node):
        visible = None
        for scope in reversed(self.scopes):
            if node.name in scope:
                visible = scope[node.name]
                break
        if visible is None and self.current_struct is not None:
            visible = next((f for f in self.current_struct.fields if f.name == node.name), None)
        available_function = node.name in self.functions or (self.current_struct is not None and node.name in self.current_struct.method_map)
        if visible is not None and available_function:
            raise CompileError(f"line {node.line}:{node.column}: '{node.name}' is both a variable and a function: rename one of them")
        if visible is not None:
            typ = visible.type_name
            if typ not in self.structs:
                raise CompileError(f"line {node.line}:{node.column}: '{node.name}' is not callable: it is {typ}")
            if 'call' not in self.structs[typ].method_map:
                raise CompileError(f"line {node.line}:{node.column}: '{node.name}' is not callable: {typ} has no member function 'call'")
            receiver = VarNode(node.line, node.column, node.name)
            call = MemberCallNode(node.line, node.column, receiver, 'call', node.args)
            self.visit_member_call(call)
            node.callable_member = call
            node.type = call.type
            return node.type
        if node.name == "read":
            if node.args:
                raise CompileError(f"line {node.line}:{node.column}: read takes no arguments")
            node.type = "i32"
            return node.type
        if self.current_struct is not None and node.name in self.current_struct.method_map:
            method = self.current_struct.method_map[node.name]
            self.check_call_args(node, method)
            node.member_function = method
            node.implicit_this = True
            node.type = method.result_type
            if self.active_member is not None:
                self.active_member.same_object_calls.append(method)
            return node.type
        if node.name not in self.functions:
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"unknown function '{node.name}'"
            )

        function = self.functions[
            node.name
        ]

        if len(node.args) != len(function.params):
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"function '{node.name}' expects "
                f"{len(function.params)} arguments, "
                f"got {len(node.args)}"
            )

        for arg, param in zip(
            node.args,
            function.params,
        ):
            self.visit_expr(
                arg
            )

            self.check_assignable(
                arg,
                param.type_name,
                arg,
                f"pass argument to '{node.name}'"
            )

        node.function = function
        node.type = function.result_type

        return node.type

    def check_call_args(self, node, method):
        if len(node.args) != len(method.params):
            raise CompileError(f"line {node.line}:{node.column}: '{node.name}' expects {len(method.params)} arguments, got {len(node.args)}")
        for arg, param in zip(node.args, method.params):
            self.visit_expr(arg)
            self.check_assignable(arg, param.type_name, arg, "pass argument")

    def visit_member_call(self, node):
        receiver_type = self.visit_expr(node.receiver)
        if receiver_type not in self.structs:
            raise CompileError(f"line {node.line}:{node.column}: type '{receiver_type}' has no methods")
        struct = self.structs[receiver_type]
        if node.name not in struct.method_map:
            field = next((f for f in struct.fields if f.name == node.name), None)
            if field is not None:
                receiver = ChainFieldNode(node.line, node.column, node.receiver, node.name)
                rewritten = MemberCallNode(node.line, node.column, receiver, 'call', node.args)
                self.visit_member_call(rewritten)
                node.callable_member = rewritten
                node.type = rewritten.type
                return node.type
            raise CompileError(f"line {node.line}:{node.column}: unknown member function '{node.name}'")
        method = struct.method_map[node.name]
        node.method = method
        node.type = method.result_type
        self.check_call_args(node, method)
        node.temporary = isinstance(node.receiver, (MemberCallNode, CallNode, ChainFieldNode)) and not getattr(node.receiver, 'is_lvalue', False)
        self.member_calls.append(node)
        if self.active_member is not None and self.current_struct is not None:
            if isinstance(node.receiver, (VarNode, FieldAccessNode)) and isinstance(getattr(node.receiver, 'decl', None), FieldDeclNode):
                if method.mutating and not node.receiver.mutable_path:
                    raise CompileError(f"line {node.line}:{node.column}: mutating call through const field")
            if isinstance(node.receiver, VarNode) and any(f.name == node.receiver.name for f in self.current_struct.fields):
                self.active_member.same_object_calls.append(method)
        return node.type

    def visit_chain_field(self, node):
        current_type = self.visit_expr(node.receiver)
        if current_type.startswith('lambda.'):
            raise CompileError(f"line {node.line}:{node.column}: lambda captures are private")
        if current_type not in self.structs:
            raise CompileError(f"line {node.line}:{node.column}: cannot access field on '{current_type}'")
        for i, field in enumerate(self.structs[current_type].fields):
            if field.name == node.name:
                node.field_index = i
                node.type = field.type_name
                node.mutable_path = getattr(node.receiver, 'mutable_path', False) and field.mutable
                node.is_lvalue = getattr(node.receiver, 'is_lvalue', False)
                return node.type
        raise CompileError(f"line {node.line}:{node.column}: unknown field '{node.name}'")

    def struct_all_mut(self, type_name):
        if type_name not in self.structs:
            return True

        struct = self.structs[type_name]

        for field in struct.fields:
            if not field.mutable:
                return False

            if not self.struct_all_mut(
                field.type_name
            ):
                return False

        return True

    def visit_decl(self, node):
        frame = self.scopes[-1]

        if node.name in {"read", "print"} or node.name in frame:
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"variable '{node.name}' is already declared in this block"
            )

        if (
            node.type_name not in {"i32", "i64", "bool"}
            and node.type_name not in self.structs
        ):
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"unknown type '{node.type_name}'"
            )

        if node.type_name in self.structs:
            struct = self.structs[node.type_name]
            node.struct_def = struct

            if isinstance(node.init, InitListNode):
                values = node.init.values
            else:
                self.visit_expr(
                    node.init
                )

                if node.init.type == node.type_name:
                    frame[node.name] = node
                    return

                values = [
                    node.init
                ]

            if len(values) != len(struct.fields):
                raise CompileError(
                    f"line {node.line}:{node.column}: "
                    f"struct '{node.type_name}' needs "
                    f"{len(struct.fields)} values, got {len(values)}"
                )

            for value, field in zip(
                values,
                struct.fields,
            ):
                if isinstance(value, StructInitNode):
                    self.check_struct_init(
                        value,
                        field.type_name,
                    )
                else:
                    self.visit_expr(
                        value
                    )

                    self.check_assignable(
                        value,
                        field.type_name,
                        value,
                        f"initialise field '{field.name}'"
                    )

            frame[node.name] = node
            return

        if isinstance(node.init, InitListNode):
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"type {node.type_name} needs exactly one value"
            )

        self.visit_expr(
            node.init
        )

        self.check_assignable(
            node.init,
            node.type_name,
            node,
            f"initialise '{node.name}'"
        )

        frame[node.name] = node

    def check_struct_init(self, node, expected_type):
        if expected_type not in self.structs:
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"cannot use '{{}}' for built-in type "
                f"'{expected_type}'"
            )

        struct = self.structs[
            expected_type
        ]

        if len(node.values) != len(struct.fields):
            raise CompileError(
                f"line {node.line}:{node.column}: "
                f"struct '{expected_type}' needs "
                f"{len(struct.fields)} values, "
                f"got {len(node.values)}"
            )

        node.type = expected_type
        node.struct_def = struct

        for value, field in zip(
            node.values,
            struct.fields,
        ):
            if isinstance(
                value,
                StructInitNode,
            ):
                self.check_struct_init(
                    value,
                    field.type_name,
                )
            else:
                self.visit_expr(
                    value
                )

                self.check_assignable(
                    value,
                    field.type_name,
                    value,
                    f"initialise field '{field.name}'"
                )

    def visit_assign(self, node):
        if isinstance(node.target, VarNode):
            decl = self.lookup(
                node.target,
                node.target.name,
            )

            if not decl.mutable:
                raise CompileError(
                    f"line {node.line}:{node.column}: "
                    f"cannot assign to '{node.target.name}': "
                    "it is not mut"
                )

            node.target.decl = decl
            node.target.type = decl.type_name
            if self.active_member is not None and isinstance(decl, FieldDeclNode):
                self.active_member.mutating = True

            if (
                decl.type_name in self.structs
                and not self.struct_all_mut(
                    decl.type_name
                )
            ):
                raise CompileError(
                    f"line {node.line}:{node.column}: "
                    f"cannot replace struct '{decl.type_name}': "
                    "not all fields are mut"
                )

            target_type = decl.type_name

        elif isinstance(
            node.target,
            FieldAccessNode,
        ):
            target_type = self.visit_field_access(
                node.target
            )

            decl = node.target.decl
            if self.active_member is not None and isinstance(decl, FieldDeclNode):
                self.active_member.mutating = True

            if not decl.mutable:
                raise CompileError(
                    f"line {node.line}:{node.column}: "
                    f"cannot write through '{node.target.base_name}': "
                    "it is not mut"
                )

            for field in node.target.field_defs:
                if not field.mutable:
                    raise CompileError(
                        f"line {node.line}:{node.column}: "
                        f"cannot write through field "
                        f"'{field.name}': it is not mut"
                    )

            if (
                target_type in self.structs
                and not self.struct_all_mut(
                    target_type
                )
            ):
                raise CompileError(
                    f"line {node.line}:{node.column}: "
                    f"cannot replace struct '{target_type}': "
                    "not all fields are mut"
                )

        else:
            raise CompileError(
                f"line {node.line}:{node.column}: "
                "invalid assignment target"
            )

        self.visit_expr(
            node.value
        )

        self.check_assignable(
            node.value,
            target_type,
            node,
            f"assign to '{node.target.name}'"
            if isinstance(node.target, VarNode)
            else "assign"
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

        if have.startswith('lambda.') and have != want:
            raise CompileError(f"line {at.line}:{at.column}: lambda cannot be used as a value here: its type has no name")
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
        if node.value.type.startswith('lambda.'):
            raise CompileError(f"line {node.line}:{node.column}: lambda cannot be returned: its type has no name")

        if self.current_function_result is not None:
            self.check_assignable(
                node.value,
                self.current_function_result,
                node,
                "return from function"
            )

            return

        if node.value.type not in {
            "i32",
            "i64",
            "bool",
        }:
            raise CompileError(
                f"line {node.line}:{node.column}: "
                "top-level exit must have "
                "a built-in type"
            )

class CodeGen:
    def __init__(self, module, builder, printf, fmt):
        self.module = module
        self.builder = builder
        self.printf = printf
        self.fmt = fmt
        self.storage = {}
        self.struct_types = {}
        self.functions = {}
        self.current_function_result = None
        self.this_ptr = None
        self.field_layout = {}
        self.string_count = 0
        self.printf_formats = {}
        self.scanf = ir.Function(module, ir.FunctionType(I32, [ir.PointerType(I8)], var_arg=True), name="scanf")

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

        if type_name in self.struct_types:
            return self.struct_types[type_name]

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

    def prepare_structs(self, program):
        for struct in program.structs:
            self.struct_types[struct.name] = (
                self.module.context.get_identified_type(
                    struct.name
                )
            )

        for struct in program.structs:
            self.field_layout[struct.name] = {f: i for i, f in enumerate(struct.fields)}
            field_types = [
                self.llvm_type(field.type_name)
                for field in struct.fields
            ]

            self.struct_types[
                struct.name
            ].set_body(
                *field_types
            )

    def prepare_functions(self, program):
        for function in program.functions + [m for st in program.structs for m in st.methods]:
            result_type = self.llvm_type(
                function.result_type
            )

            param_types = [
                self.llvm_type(
                    param.type_name
                )
                for param in function.params
            ]

            if isinstance(function, MemberFnNode):
                owner = next(st for st in program.structs if function in st.methods)
                function.owner = owner
                param_types.insert(0, self.struct_types[owner.name].as_pointer())
            function_type = ir.FunctionType(
                result_type,
                param_types,
            )

            llvm_function = ir.Function(
                self.module,
                function_type,
                name=(f"{function.owner.name}_{function.name}" if isinstance(function, MemberFnNode)
                      else f"user_{function.name}"),
            )

            if isinstance(function, MemberFnNode):
                llvm_function.args[0].name = "this"
            for argument, param in zip(
                llvm_function.args[1:] if isinstance(function, MemberFnNode) else llvm_function.args,
                function.params,
            ):
                argument.name = param.name

            self.functions[
                function
            ] = llvm_function

    def generate_function(self, node):
        llvm_function = self.functions[
            node
        ]

        old_builder = self.builder
        old_storage = self.storage
        old_result = self.current_function_result
        old_this = self.this_ptr

        entry = llvm_function.append_basic_block(
            "entry"
        )

        self.builder = ir.IRBuilder(
            entry
        )

        self.storage = {}
        self.current_function_result = node.result_type
        self.this_ptr = llvm_function.args[0] if isinstance(node, MemberFnNode) else None
        self.active_struct_name = node.owner.name if isinstance(node, MemberFnNode) else None
        try:
            for argument, param in zip(
                llvm_function.args[1:] if isinstance(node, MemberFnNode) else llvm_function.args,
                node.params,
            ):
                ptr = self.create_entry_alloca(
                    param.type_name,
                    f"{param.name}_slot",
                )

                self.builder.store(
                    argument,
                    ptr,
                )

                self.storage[
                    param
                ] = ptr

            self.visit_block(
                node.body
            )

        finally:
            self.builder = old_builder
            self.storage = old_storage
            self.current_function_result = old_result
            self.this_ptr = old_this

    def generate(self, program):
        self.struct_definitions = {st.name: st for st in program.structs}
        self.prepare_structs(program)

        self.prepare_functions(
            program
        )

        for function in program.functions + [m for st in program.structs for m in st.methods]:
            self.generate_function(
                function
            )

        for stmt in program.statements:
            self.visit_stmt(
                stmt
            )

        self.current_function_result = None

        self.visit_exit(
            program.exit_node
        )

    def visit_stmt(self, node):
        if isinstance(node, LambdaNode):
            return self.visit_decl(node.generated_decl)
        if isinstance(node, DeclNode):
            return self.visit_decl(node)

        if isinstance(node, AssignNode):
            return self.visit_assign(node)

        if isinstance(node, IfNode):
            return self.visit_if(node)

        if isinstance(node, WhileNode):
            return self.visit_while(node)
        if isinstance(node, PrintNode):
            return self.visit_print(node)

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

        if isinstance(node, FieldAccessNode):
            return self.visit_field_access(node)

        if isinstance(node, CallNode):
            return self.visit_call(node)
        if isinstance(node, MemberCallNode):
            return self.visit_member_call(node)
        if isinstance(node, ChainFieldNode):
            return self.visit_chain_field(node)

        if isinstance(node, BinOpNode):
            return self.visit_binop(node)

        if isinstance(node, NotNode):
            return self.visit_not(node)

        if isinstance(node, StructInitNode):
            return self.visit_struct_init(node)

        raise CompileError(
            f"line {node.line}:{node.column}: unknown expression"
        )

    def visit_struct_init(self, node):
        struct_type = self.llvm_type(
            node.type
        )

        value = ir.Constant(
            struct_type,
            ir.Undefined,
        )

        for index, (value_node, field) in enumerate(
            zip(
                node.values,
                node.struct_def.fields,
            )
        ):
            field_value = self.visit_expr(
                value_node
            )

            field_value = self.coerce(
                field_value,
                value_node.type,
                field.type_name,
            )

            value = self.builder.insert_value(
                value,
                field_value,
                index,
                name="struct_init",
            )

        return value

    def visit_var(self, node):
        ptr = self.decl_pointer(node.decl)

        return self.builder.load(
            ptr,
            name=f"load_{node.name}",
        )

    def field_pointer(self, node):
        ptr = self.decl_pointer(node.decl)

        for index in node.field_indices:
            ptr = self.builder.gep(
                ptr,
                [
                    ir.Constant(I32, 0),
                    ir.Constant(I32, index),
                ],
                name="field_ptr",
            )

        return ptr

    def visit_field_access(self, node):
        ptr = self.field_pointer(
            node
        )

        return self.builder.load(
            ptr,
            name="load_field",
        )

    def visit_call(self, node):
        if hasattr(node, 'callable_member'):
            return self.visit_member_call(node.callable_member)
        if node.name == "read":
            ptr = self.create_entry_alloca("i32", "read_slot")
            fmt = self.get_format("%d")
            self.builder.call(self.scanf, [fmt, ptr])
            return self.builder.load(ptr, name="read_value")
        if getattr(node, "implicit_this", False):
            return self.invoke_method(node.member_function, self.this_ptr, node.args)
        llvm_function = self.functions[
            node.function
        ]

        arguments = []

        for arg, param in zip(
            node.args,
            node.function.params,
        ):
            value = self.visit_expr(
                arg
            )

            value = self.coerce(
                value,
                arg.type,
                param.type_name,
            )

            arguments.append(
                value
            )

        return self.builder.call(
            llvm_function,
            arguments,
            name=f"call_{node.name}",
        )

    def decl_pointer(self, decl):
        if decl in self.storage:
            return self.storage[decl]
        if isinstance(decl, FieldDeclNode) and self.this_ptr is not None:
            return self.builder.gep(self.this_ptr, [ir.Constant(I32, 0),
                ir.Constant(I32, self.field_layout[self.active_struct_name][decl])], name="this_field")
        raise CompileError(f"unknown local storage for '{decl.name}'")

    def get_format(self, text):
        if text not in self.printf_formats:
            self.string_count += 1
            global_string = self.make_string(f"text_{self.string_count}", text.encode("utf-8") + b"\0")
            self.printf_formats[text] = global_string
        return self.builder.bitcast(self.printf_formats[text], ir.PointerType(I8))

    def invoke_method(self, method, receiver_ptr, args):
        arguments = [receiver_ptr]
        for arg, param in zip(args, method.params):
            value = self.visit_expr(arg)
            arguments.append(self.coerce(value, arg.type, param.type_name))
        return self.builder.call(self.functions[method], arguments, name=f"call_{method.name}")

    def receiver_pointer(self, receiver):
        if isinstance(receiver, VarNode):
            return self.decl_pointer(receiver.decl)
        if isinstance(receiver, FieldAccessNode):
            return self.field_pointer(receiver)
        if isinstance(receiver, ChainFieldNode) and getattr(receiver, "is_lvalue", False):
            return self.chain_pointer(receiver)
        value = self.visit_expr(receiver)
        ptr = self.create_entry_alloca(receiver.type, "temporary_object")
        self.builder.store(value, ptr)
        return ptr

    def chain_pointer(self, node):
        ptr = self.receiver_pointer(node.receiver)
        return self.builder.gep(ptr, [ir.Constant(I32, 0), ir.Constant(I32, node.field_index)], name="chain_field_ptr")

    def visit_chain_field(self, node):
        return self.builder.load(self.chain_pointer(node), name="chain_field")

    def visit_member_call(self, node):
        if hasattr(node, 'callable_member'):
            return self.visit_member_call(node.callable_member)
        return self.invoke_method(node.method, self.receiver_pointer(node.receiver), node.args)

    def visit_print(self, node):
        arg = node.value
        if isinstance(arg, StringNode):
            data = arg.value.encode("latin-1")
            self.string_count += 1
            g = self.make_string(f"literal_{self.string_count}", data + b"\0")
            self.builder.call(self.printf, [self.get_format("%s\n"), self.builder.bitcast(g, ir.PointerType(I8))])
            return
        value = self.visit_expr(arg)
        self.print_value(value, arg.type)

    def print_value(self, value, typ, prefix="", suffix="\n"):
        if typ in {"i32", "i64"}:
            self.builder.call(self.printf, [self.get_format(prefix + ("%d" if typ == "i32" else "%lld") + suffix), value])
        elif typ == "bool":
            t = self.builder.bitcast(self.true_text, ir.PointerType(I8))
            f = self.builder.bitcast(self.false_text, ir.PointerType(I8))
            self.builder.call(self.printf, [self.get_format(prefix + "%s" + suffix), self.builder.select(value, t, f)])
        else:
            struct = self.struct_definitions[typ]
            self.builder.call(self.printf, [self.get_format(prefix + typ + "{")])
            for i, field in enumerate(struct.fields):
                field_value = self.builder.extract_value(value, i)
                self.print_value(field_value, field.type_name, ("" if i == 0 else ", ") + field.name + ": ", "")
            self.builder.call(self.printf, [self.get_format("}" + suffix)])

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
        ptr = self.create_entry_alloca(
            node.type_name,
            node.name,
        )

        if node.type_name in self.struct_types:
            if (
                not isinstance(node.init, InitListNode)
                and node.init.type == node.type_name
            ):
                value = self.visit_expr(
                    node.init
                )

                self.builder.store(
                    value,
                    ptr,
                )

                self.storage[node] = ptr
                return

            if isinstance(node.init, InitListNode):
                values = node.init.values
            else:
                values = [
                    node.init
                ]

            for index, (value_node, field) in enumerate(
                zip(
                    values,
                    node.struct_def.fields,
                )
            ):
                value = self.visit_expr(
                    value_node
                )

                value = self.coerce(
                    value,
                    value_node.type,
                    field.type_name,
                )

                field_ptr = self.builder.gep(
                    ptr,
                    [
                        ir.Constant(I32, 0),
                        ir.Constant(I32, index),
                    ],
                    name=f"{node.name}_{field.name}",
                )

                self.builder.store(
                    value,
                    field_ptr,
                )

            self.storage[node] = ptr
            return

        value = self.visit_expr(
            node.init
        )

        value = self.coerce(
            value,
            node.init.type,
            node.type_name,
        )

        self.builder.store(
            value,
            ptr,
        )

        self.storage[node] = ptr

    def visit_assign(self, node):
        value = self.visit_expr(
            node.value
        )

        if isinstance(node.target, VarNode):
            target_type = node.target.type

            ptr = self.decl_pointer(node.target.decl)

        elif isinstance(
            node.target,
            FieldAccessNode,
        ):
            target_type = node.target.type

            ptr = self.field_pointer(
                node.target
            )

        else:
            raise CompileError(
                f"line {node.line}:{node.column}: "
                "invalid assignment target"
            )

        value = self.coerce(
            value,
            node.value.type,
            target_type,
        )

        self.builder.store(
            value,
            ptr,
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
        if self.current_function_result is not None:
            value = self.visit_expr(
                node.value
            )

            value = self.coerce(
                value,
                node.value.type,
                self.current_function_result,
            )

            self.builder.ret(
                value
            )

            return

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
    "struct": "keyword",
    "fn": "keyword",
    "read": "keyword",
    "print": "keyword",
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

            if b == ord('"'):
                start_line, start_col = line, col
                j = i + 1
                while j < len(data) and data[j] not in (10, 34):
                    j += 1
                if j >= len(data) or data[j] == 10:
                    raise CompileError(f"line {line}:{col}: unterminated string literal")
                tokens.append(Token("string", data[i + 1:j].decode("latin-1"), line, col))
                col += j - i + 1
                i = j + 1
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
            if b == ord("["):
                tokens.append(Token("lbracket", "[", line, col))
                i += 1
                col += 1
                continue
            if b == ord("]"):
                tokens.append(Token("rbracket", "]", line, col))
                i += 1
                col += 1
                continue
            if b == ord("("):
                tokens.append(
                    Token("lparen", "(", line, col)
                )

                i += 1
                col += 1
                continue

            if b == ord(")"):
                tokens.append(
                    Token("rparen", ")", line, col)
                )

                i += 1
                col += 1
                continue

            if b == ord(","):
                tokens.append(
                    Token("comma", ",", line, col)
                )

                i += 1
                col += 1
                continue

            if b == ord("."):
                tokens.append(
                    Token("dot", ".", line, col)
                )

                i += 1
                col += 1
                continue

            if (
                b == ord("-")
                and i + 1 < len(data)
                and data[i + 1] == ord(">")
            ):
                tokens.append(
                    Token(
                        "arrow",
                        "->",
                        line,
                        col,
                    )
                )

                i += 2
                col += 2
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
    if len(sys.argv) == 3 and sys.argv[1] in {"--ast", "--ast-checked"}:
        source_path = sys.argv[2]

        try:
            with open(source_path, "rb") as f:
                data = f.read()

            token_lines = lex(data)

            parser = Parser(token_lines)
            tree = parser.parse_program()
            if sys.argv[1] == "--ast-checked":
                SemanticChecker().check(tree)
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
