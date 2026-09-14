import sys
import os

from llvmlite import ir
import llvmlite.binding as llvm


I32 = ir.IntType(32)
I8 = ir.IntType(8)


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
                if open_brace_line is None:
                    raise CompileError(
                        f"line {line}:{col}: unexpected byte '}}'"
                    )

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

    module = ir.Module(name="practice2")
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

    text = b"Program exit with result %d\n\0"

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

    symbols = {}
    found_exit = False

    for tokens in token_lines:
        if not tokens:
            continue

        if found_exit:
            error(
                tokens[0],
                "code after exit is not allowed"
            )

        first = tokens[0]

        if (
            first.kind == "keyword"
            and first.text == "i32"
        ):
            parse_declaration(
                tokens,
                symbols,
                builder,
            )

            continue

        if (
            first.kind == "keyword"
            and first.text == "exit"
        ):
            parse_exit(
                tokens,
                symbols,
                builder,
                printf,
                fmt,
            )

            found_exit = True
            continue

        if first.kind == "identifier":
            parse_assignment(
                tokens,
                symbols,
                builder,
            )

            continue

        error(
            first,
            "invalid statement"
        )

    if not found_exit:
        raise CompileError(
            "line 1:1: program needs an exit statement"
        )

    with open(output_path, "w") as f:
        f.write(str(module))


def main():
    if len(sys.argv) != 3:
        print(
            "usage: python3 compiler.py <source> <output.ll>",
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
