import subprocess
from pathlib import Path


def run_ok_test(test_file):
    expected_file = test_file.with_suffix(".expected")
    output_file = Path("test_output.ll")

    result = subprocess.run(
        [
            "python3",
            "compiler.py",
            str(test_file),
            str(output_file),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return False, result.stderr.strip()

    run_result = subprocess.run(
        ["lli", str(output_file)],
        capture_output=True,
        text=True,
    )

    actual = run_result.stdout.strip()
    expected = expected_file.read_text().strip()

    return actual == expected, actual


def run_error_test(test_file):
    expected_file = test_file.with_suffix(".expected")
    output_file = Path("test_output.ll")

    result = subprocess.run(
        [
            "python3",
            "compiler.py",
            str(test_file),
            str(output_file),
        ],
        capture_output=True,
        text=True,
    )

    actual = result.stderr.strip()
    expected = expected_file.read_text().strip()

    return result.returncode != 0 and actual == expected, actual


def main():
    passed = 0
    total = 0

    for test_file in sorted(Path("tests/ok").glob("*.txt")):
        total += 1

        ok, output = run_ok_test(test_file)

        if ok:
            passed += 1
            print(f"{test_file.name}: PASS")
        else:
            print(f"{test_file.name}: FAIL")
            print(output)

    for test_file in sorted(Path("tests/err").glob("*.txt")):
        total += 1

        ok, output = run_error_test(test_file)

        if ok:
            passed += 1
            print(f"{test_file.name}: PASS")
        else:
            print(f"{test_file.name}: FAIL")
            print(output)

    print()
    print(f"{passed}/{total} tests passed")

    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
