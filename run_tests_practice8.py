"""Practice 8 regression tests. Requires llvmlite and lli/lli-18."""
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
compiler = root / 'src' / 'compiler.py'
lli = shutil.which('lli') or shutil.which('lli-18')
if lli is None:
    print('Cannot run success tests: install llvm-18 (lli-18).', file=sys.stderr)
    sys.exit(2)

failures = []
total = 0
for group in ('ok', 'err'):
    for source in sorted((root / 'tests' / group).glob('p8_*.txt')):
        total += 1
        output = root / 'practice8_test_output.ll'
        if output.exists():
            output.unlink()
        compiled = subprocess.run([sys.executable, str(compiler), str(source), str(output)],
                                  capture_output=True, text=True)
        expected = source.with_suffix('.expected').read_text()
        if group == 'err':
            actual = compiled.stderr
            passed = compiled.returncode != 0 and actual == expected
        elif compiled.returncode:
            actual = compiled.stderr
            passed = False
        else:
            stdin_file = source.with_suffix('.in')
            user_input = stdin_file.read_text() if stdin_file.exists() else ''
            executed = subprocess.run([lli, str(output)], input=user_input,
                                      capture_output=True, text=True, timeout=10)
            actual = executed.stdout
            passed = executed.returncode == 0 and actual == expected
        print(('PASS' if passed else 'FAIL'), group, source.stem)
        if not passed:
            failures.append((source.name, actual, expected))
        if output.exists():
            output.unlink()

print(f'Passed {total - len(failures)}/{total}')
for name, actual, expected in failures:
    print(f'FAIL {name}:\nACTUAL:\n{actual}\nEXPECTED:\n{expected}')
if failures:
    sys.exit(1)
