import os
import subprocess
import sys
import tempfile


ROOT = os.path.dirname(os.path.abspath(__file__))
COMPILER = os.path.join(ROOT, "src", "compiler.py")

TEST_GROUPS = [
    (
        "ok",
        [
            "p6_nested_field",
            "p6_field_write",
            "p6_struct_parameter",
            "p6_struct_result",
            "p6_nested_calls",
            "p6_i32_to_i64",
            "p6_nested_init",
        ],
    ),
    (
        "err",
        [
            "p6_unknown_field",
            "p6_wrong_struct_values",
            "p6_const_link",
            "p6_wrong_arguments",
            "p6_wrong_function_exit",
            "p6_function_after_statement",
            "p6_nested_init_builtin",
            "p6_nested_init_wrong_count",
        ],
    ),
]


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def run_ok(name):
    source = os.path.join(
        ROOT,
        "tests",
        "ok",
        f"{name}.txt",
    )

    expected_path = os.path.join(
        ROOT,
        "tests",
        "ok",
        f"{name}.expected",
    )

    expected = read_text(expected_path)

    with tempfile.NamedTemporaryFile(
        suffix=".ll",
        delete=False,
    ) as tmp:
        output_path = tmp.name

    try:
        compile_result = subprocess.run(
            [
                sys.executable,
                COMPILER,
                source,
                output_path,
            ],
            capture_output=True,
            text=True,
        )

        if compile_result.returncode != 0:
            return False, compile_result.stderr.strip()

        lli_result = subprocess.run(
            [
                "lli",
                output_path,
            ],
            capture_output=True,
            text=True,
        )

        actual = lli_result.stdout.strip()

        if lli_result.returncode != 0:
            return False, lli_result.stderr.strip()

        if actual != expected:
            return (
                False,
                f"expected:\n{expected}\nactual:\n{actual}",
            )

        return True, ""

    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


def run_err(name):
    source = os.path.join(
        ROOT,
        "tests",
        "err",
        f"{name}.txt",
    )

    expected_path = os.path.join(
        ROOT,
        "tests",
        "err",
        f"{name}.expected",
    )

    expected = read_text(expected_path)

    with tempfile.NamedTemporaryFile(
        suffix=".ll",
        delete=False,
    ) as tmp:
        output_path = tmp.name

    try:
        result = subprocess.run(
            [
                sys.executable,
                COMPILER,
                source,
                output_path,
            ],
            capture_output=True,
            text=True,
        )

        actual = result.stderr.strip()

        if result.returncode == 0:
            return False, "compiler accepted an invalid program"

        if actual != expected:
            return (
                False,
                f"expected:\n{expected}\nactual:\n{actual}",
            )

        return True, ""

    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


def main():
    passed = 0
    total = 0

    for group, names in TEST_GROUPS:
        for name in names:
            total += 1

            if group == "ok":
                success, message = run_ok(name)
            else:
                success, message = run_err(name)

            if success:
                passed += 1
                print(f"PASS tests/{group}/{name}.txt")
            else:
                print(f"FAIL tests/{group}/{name}.txt")
                print(message)

    print()
    print(f"{passed}/{total} tests passed")

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
