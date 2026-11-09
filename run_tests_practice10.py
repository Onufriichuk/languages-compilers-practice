"""Practice 10: regression plus binary IO/FFI tests.
Usage: python3 run_tests_practice10.py [--remove-unused] [--all] [--new-only]
--all runs ordinary and optimized modes.
"""
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPILER = ROOT / "compiler.py"
LLC = shutil.which("llc-18") or shutil.which("llc")
CLANG = shutil.which("clang")
LLI = shutil.which("lli-18") or shutil.which("lli")
FLAGS = (False, True) if "--all" in sys.argv else ("--remove-unused" in sys.argv,)
if not CLANG:
    sys.exit("clang is required for binary tests")


def build(source, dest, optimized):
    ir_file = dest.with_suffix(".ll")
    obj_file = dest.with_suffix(".o")
    flag = ["--remove-unused"] if optimized else []
    compilation = subprocess.run([sys.executable, str(COMPILER), *flag, str(source), str(ir_file)], capture_output=True, text=True, timeout=20)
    if compilation.returncode:
        return compilation, None
    if LLC:
        obj_command = [LLC, "-filetype=obj", "-relocation-model=pic", str(ir_file), "-o", str(obj_file)]
    else:
        # Host fallback only. Ubuntu course environment should use llc.
        obj_command = [CLANG, "-Wno-override-module", "-fPIC", "-c", str(ir_file), "-o", str(obj_file)]
    obj = subprocess.run(obj_command, capture_output=True, text=True, timeout=20)
    if obj.returncode:
        return obj, None
    cmd = [CLANG, "-fPIE", str(obj_file)]
    c_file = source.with_suffix(".c")
    if c_file.exists():
        cmd.append(str(c_file))
    cmd += ["-o", str(dest)]
    link = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if link.returncode:
        return link, None
    return compilation, dest


def run_old_test(source, optimized, tmp):
    group = source.parent.name
    expected = source.with_suffix(".expected").read_text()
    ir_file = tmp / "old.ll"
    cmd = [sys.executable, str(COMPILER)] + (["--remove-unused"] if optimized else []) + [str(source), str(ir_file)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if group == "err":
        return result.returncode != 0 and result.stderr == expected, result.stderr, expected
    if result.returncode:
        return False, result.stderr, expected
    if LLI:
        program = subprocess.run([LLI, str(ir_file)], capture_output=True, input=(source.with_suffix(".in").read_text() if source.with_suffix(".in").exists() else ""), text=True, timeout=20)
    else:
        built, executable = build(source, tmp / "old", optimized)
        if executable is None:
            return False, built.stderr, expected
        program = subprocess.run([str(executable)], capture_output=True, input=(source.with_suffix(".in").read_text() if source.with_suffix(".in").exists() else ""), text=True, timeout=20)
    ok = program.stdout == expected and program.returncode == 0
    if ok and group == "opt" and optimized:
        ast = subprocess.run([sys.executable, str(COMPILER), "--remove-unused", "--ast-checked", str(source)], capture_output=True, text=True, timeout=20)
        ok = ast.returncode == 0 and ast.stdout == source.with_suffix(".astc").read_text()
    return ok, program.stdout, expected


failures = []
count = 0
with tempfile.TemporaryDirectory() as directory:
    tmp = Path(directory)
    for optimized in FLAGS:
        mode = "optimized" if optimized else "ordinary"
        for group in (() if "--new-only" in sys.argv else ("ok", "err", "opt")):
            for source in sorted((ROOT / "tests" / group).glob("*.txt")):
                if not source.with_suffix(".expected").exists():
                    continue
                count += 1
                try:
                    passed, actual, expected = run_old_test(source, optimized, tmp)
                except Exception as e:
                    passed, actual, expected = False, str(e), ""
                print(("PASS" if passed else "FAIL"), mode, group, source.stem, flush=True)
                if not passed:
                    failures.append((mode, str(source), actual, expected))
        for group in ("io", "ffi"):
            for source in sorted((ROOT / "tests" / group).glob("*.txt")):
                sessions = sorted(source.parent.glob(source.stem + ".*.in"))
                if not sessions:
                    continue
                try:
                    result, executable = build(source, tmp / source.stem, optimized)
                except Exception as e:
                    result, executable = str(e), None
                for session in sessions:
                    count += 1
                    expected = session.with_suffix(".expected").read_text()
                    if executable is None:
                        actual = result.stderr if hasattr(result, "stderr") else str(result)
                        passed = False
                    else:
                        result = subprocess.run([str(executable)], input=session.read_text(), capture_output=True, text=True, timeout=20)
                        actual = result.stdout
                        passed = actual == expected and result.returncode == 0
                    print(("PASS" if passed else "FAIL"), mode, group, session.stem, flush=True)
                    if not passed:
                        failures.append((mode, str(session), actual, expected))
print(f"Passed {count - len(failures)}/{count}")
for mode, source, actual, expected in failures[:30]:
    print(f"FAIL {mode} {source}\nACTUAL:\n{actual}\nEXPECTED:\n{expected}")
if failures:
    sys.exit(1)
