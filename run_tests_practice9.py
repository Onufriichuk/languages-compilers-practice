"""Practice 9 optimization and earlier regression runner.
Usage: python3 run_tests_practice9.py [--remove-unused] [--all]
Run --all to check both optimized and ordinary compiles.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPILER = ROOT / 'src' / 'compiler.py'
LLI = shutil.which('lli-18') or shutil.which('lli')
CLANG = shutil.which('clang')
FLAGS = [True, False] if '--all' in sys.argv else ['--remove-unused' in sys.argv]


def run_code(ll_path, data):
    if LLI:
        return subprocess.run([LLI, str(ll_path)], text=True, input=data, capture_output=True, timeout=12)
    if CLANG:
        exe = ll_path.with_suffix('.out')
        c = subprocess.run([CLANG, '-Wno-override-module', str(ll_path), '-o', str(exe)], capture_output=True, text=True)
        if c.returncode:
            return c
        return subprocess.run([str(exe)], text=True, input=data, capture_output=True, timeout=12)
    raise RuntimeError('Install lli-18 or clang to execute test programs')


failures = []
total = 0
with tempfile.TemporaryDirectory() as tmp:
    output = Path(tmp) / 'test.ll'
    for enabled in FLAGS:
        flag = ['--remove-unused'] if enabled else []
        for group in ('ok', 'err', 'opt'):
            for source in sorted((ROOT / 'tests' / group).glob('*.txt')):
                expected_path = source.with_suffix('.expected')
                if not expected_path.exists():
                    continue
                total += 1
                expected = expected_path.read_text()
                result = subprocess.run([sys.executable, str(COMPILER), *flag, str(source), str(output)],
                                        text=True, capture_output=True, timeout=15)
                if group == 'err':
                    actual = result.stderr
                    passed = result.returncode != 0 and actual == expected
                elif result.returncode:
                    actual, passed = result.stderr, False
                else:
                    stdin = source.with_suffix('.in')
                    inp = stdin.read_text() if stdin.exists() else ''
                    try:
                        executed = run_code(output, inp)
                        actual = executed.stdout
                        passed = actual == expected and executed.returncode == 0
                    except (subprocess.TimeoutExpired, RuntimeError) as exc:
                        actual, passed = str(exc), False
                if group == 'opt' and enabled:
                    astc = subprocess.run([sys.executable, str(COMPILER), '--remove-unused', '--ast-checked', str(source)],
                                          capture_output=True, text=True, timeout=15)
                    passed = passed and astc.returncode == 0 and astc.stdout == source.with_suffix('.astc').read_text()
                print(('PASS' if passed else 'FAIL'), 'optimized' if enabled else 'ordinary', group, source.stem, flush=True)
                if not passed:
                    failures.append((enabled, group, source.name, actual, expected))
print(f'Passed {total-len(failures)}/{total}')
for enabled, group, name, actual, expected in failures[:30]:
    print(f'FAIL {enabled} {group}/{name}\nACTUAL:\n{actual}\nEXPECTED:\n{expected}')
if failures:
    sys.exit(1)
