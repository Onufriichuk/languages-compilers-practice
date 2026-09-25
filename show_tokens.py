import sys

from compiler import lex, CompileError


def main():
    if len(sys.argv) != 2:
        print("usage: python3 show_tokens.py <source>")
        sys.exit(1)

    path = sys.argv[1]

    with open(path, "rb") as f:
        data = f.read()

    try:
        lines = lex(data)

        for line_tokens in lines:
            for token in line_tokens:
                print(token)

    except CompileError as e:
        print(
            f"compilation error: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
