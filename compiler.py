import sys
import os
import re

from llvmlite import ir
import llvmlite.binding as llvm

class CompileError(Exception):
    pass


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
    "mut": "keyword",
    "exit": "keyword",
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

    open_brace_line = None
    open_brace_col = None

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
                if open_brace_line is not None:
                    raise CompileError(
                        f"line {open_brace_line}:{open_brace_col}: "
                        "'{' is not closed before the end of the line"
                    )

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

                open_brace_line = line
                open_brace_col = col

                i += 1
                col += 1
                continue

            if b == ord("}"):
                tokens.append(
                    Token("rbrace", "}", line, col)
                )

                open_brace_line = None
                open_brace_col = None

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

    if open_brace_line is not None:
        raise CompileError(
            f"line {open_brace_line}:{open_brace_col}: "
            "'{' is not closed before the end of the line"
        )

    if tokens:
        lines.append(tokens)

    return lines

I32 = ir.IntType(32)
I8 = ir.IntType(8)


def compilation_error(line_number, message, output_path=None):
    if output_path and os.path.exists(output_path):
        os.remove(output_path)

    print(
        f"compilation error: line {line_number}: {message}",
        file=sys.stderr
    )
    sys.exit(1)


def valid_name(name):
    return (
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
        and name not in {"int", "exit"}
    )


def compile_program(source_path, output_path):
    module = ir.Module(name="practice1")
    module.triple = llvm.get_default_triple()

    main_type = ir.FunctionType(I32, [])
    main = ir.Function(module, main_type, name="main")

    entry = main.append_basic_block("entry")
    builder = ir.IRBuilder(entry)

    printf_type = ir.FunctionType(
        I32,
        [ir.PointerType(I8)],
        var_arg=True
    )

    printf = ir.Function(
        module,
        printf_type,
        name="printf"
    )

    text = b"Program exit with result %d\n\0"

    fmt_type = ir.ArrayType(I8, len(text))

    fmt = ir.GlobalVariable(
        module,
        fmt_type,
        name="fmt"
    )

    fmt.linkage = "private"
    fmt.global_constant = True
    fmt.initializer = ir.Constant(
        fmt_type,
        bytearray(text)
    )

    symbols = {}
    found_exit = False

    with open(source_path, "r") as f:
        lines = f.readlines()

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()

        if not line:
            compilation_error(
                line_number,
                "empty line",
                output_path
            )

        if line.startswith("int "):
            parts = line.split()

            if len(parts) != 2:
                compilation_error(
                    line_number,
                    "invalid declaration",
                    output_path
                )

            name = parts[1]

            if not valid_name(name):
                compilation_error(
                    line_number,
                    f"invalid variable name '{name}'",
                    output_path
                )

            if name in symbols:
                compilation_error(
                    line_number,
                    f"variable '{name}' already declared",
                    output_path
                )

            symbols[name] = builder.alloca(
                I32,
                name=name
            )

            continue

        if line.startswith("exit "):
            parts = line.split()

            if len(parts) != 2:
                compilation_error(
                    line_number,
                    "invalid exit statement",
                    output_path
                )

            name = parts[1]

            if name not in symbols:
                compilation_error(
                    line_number,
                    f"undeclared variable '{name}'",
                    output_path
                )

            value = builder.load(
                symbols[name],
                name=f"load_{name}"
            )

            fmt_ptr = builder.bitcast(
                fmt,
                ir.PointerType(I8)
            )

            builder.call(
                printf,
                [fmt_ptr, value]
            )

            builder.ret(
                ir.Constant(I32, 0)
            )

            found_exit = True

            if line_number != len(lines):
                compilation_error(
                    line_number,
                    "exit must be the last line",
                    output_path
                )

            break

        if ":=" in line:
            left, right = line.split(":=", 1)

            target = left.strip()
            expression = right.strip()

            if target not in symbols:
                compilation_error(
                    line_number,
                    f"undeclared variable '{target}'",
                    output_path
                )

            result = parse_expression(
                expression,
                symbols,
                builder,
                line_number,
                output_path
            )

            builder.store(
                result,
                symbols[target]
            )

            continue

        compilation_error(
            line_number,
            "cannot parse statement",
            output_path
        )

    if not found_exit:
        compilation_error(
            len(lines) if lines else 1,
            "no exit statement",
            output_path
        )

    with open(output_path, "w") as out:
        out.write(str(module))


def parse_operand(
    token,
    symbols,
    builder,
    line_number,
    output_path
):
    token = token.strip()

    if re.fullmatch(r"-?\d+", token):
        return ir.Constant(
            I32,
            int(token)
        )

    if token in symbols:
        return builder.load(
            symbols[token],
            name=f"load_{token}"
        )

    compilation_error(
        line_number,
        f"undeclared variable '{token}'",
        output_path
    )


def parse_expression(
    expression,
    symbols,
    builder,
    line_number,
    output_path
):
    expression = expression.strip()

    if re.fullmatch(
        r"-?\d+|[A-Za-z_][A-Za-z0-9_]*",
        expression
    ):
        return parse_operand(
            expression,
            symbols,
            builder,
            line_number,
            output_path
        )

    match = re.fullmatch(
        r"(.+?)\s*([+\-*])\s*(.+)",
        expression
    )

    if not match:
        compilation_error(
            line_number,
            "invalid expression",
            output_path
        )

    left_text = match.group(1).strip()
    operator = match.group(2)
    right_text = match.group(3).strip()

    left = parse_operand(
        left_text,
        symbols,
        builder,
        line_number,
        output_path
    )

    right = parse_operand(
        right_text,
        symbols,
        builder,
        line_number,
        output_path
    )

    if operator == "+":
        return builder.add(
            left,
            right,
            name="addtmp"
        )

    if operator == "-":
        return builder.sub(
            left,
            right,
            name="subtmp"
        )

    if operator == "*":
        return builder.mul(
            left,
            right,
            name="multmp"
        )

    compilation_error(
        line_number,
        "unsupported operator",
        output_path
    )


def main():
    if len(sys.argv) != 3:
        print(
            "usage: python3 compiler.py <source> <output.ll>",
            file=sys.stderr
        )
        sys.exit(1)

    source_path = sys.argv[1]
    output_path = sys.argv[2]

    if os.path.exists(output_path):
        os.remove(output_path)

    try:
        compile_program(
            source_path,
            output_path
        )

    except FileNotFoundError:
        print(
            f"compilation error: source file '{source_path}' not found",
            file=sys.stderr
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
