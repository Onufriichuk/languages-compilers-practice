import os
import subprocess


TEST_DIR = "tests"
COMPILER = "compiler.py"
OUTPUT = "test_output.ll"


def read_file(path):
    with open(path, "r") as f:
        return f.read().strip()


def run_valid_test(test_path, expected_path):
    if os.path.exists(OUTPUT):
        os.remove(OUTPUT)

    compile_result = subprocess.run(
        ["python3", COMPILER, test_path, OUTPUT],
        capture_output=True,
        text=True,
    )

    if compile_result.returncode != 0:
        return False, (
            "compiler failed:\n"
            + compile_result.stderr.strip()
        )

    run_result = subprocess.run(
        ["lli", OUTPUT],
        capture_output=True,
        text=True,
    )

    actual = run_result.stdout.strip()
    expected = read_file(expected_path)

    if actual != expected:
        return False, (
            f"expected:\n{expected}\n"
            f"actual:\n{actual}"
        )

    return True, ""


def run_invalid_test(test_path, expected_path):
    if os.path.exists(OUTPUT):
        os.remove(OUTPUT)

    result = subprocess.run(
        ["python3", COMPILER, test_path, OUTPUT],
        capture_output=True,
        text=True,
    )

    expected = read_file(expected_path)
    actual = result.stderr.strip()

    if result.returncode == 0:
        return False, "compiler succeeded but should have failed"

    if actual != expected:
        return False, (
            f"expected:\n{expected}\n"
            f"actual:\n{actual}"
        )

    if os.path.exists(OUTPUT):
        return False, "output.ll exists after compilation error"

    return True, ""


def main():
    tests = sorted(
        name
        for name in os.listdir(TEST_DIR)
        if name.endswith(".txt")
    )

    passed = 0

    for filename in tests:
        test_path = os.path.join(
            TEST_DIR,
            filename,
        )

        expected_path = os.path.join(
            TEST_DIR,
            filename.replace(
                ".txt",
                ".expected",
            ),
        )

        if filename.startswith("valid_"):
            ok, message = run_valid_test(
                test_path,
                expected_path,
            )
        elif filename.startswith("invalid_"):
            ok, message = run_invalid_test(
                test_path,
                expected_path,
            )
        else:
            continue

        if ok:
            print(f"{filename}: PASS")
            passed += 1
        else:
            print(f"{filename}: FAIL")
            print(message)

    print()
    print(f"{passed}/{len(tests)} tests passed")

    if passed != len(tests):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
