import sys
import os
import re

from llvmlite import ir
import llvmlite.binding as llvm


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
