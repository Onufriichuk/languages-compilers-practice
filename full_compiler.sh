#!/usr/bin/env bash
# Usage: ./full_compiler.sh tests/io/points.txt [tests/ffi/geometry.c] [--remove-unused]
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo 'Usage: ./full_compiler.sh SOURCE.txt [SOURCE.c] [--remove-unused]' >&2
  exit 2
fi
source_path="$1"
shift
cfile=''
flags=()
for arg in "$@"; do
  if [[ "$arg" == --remove-unused ]]; then flags+=("$arg")
  elif [[ "$arg" == *.c ]]; then cfile="$arg"
  else echo "Unexpected argument: $arg" >&2; exit 2
  fi
done
name="$(basename "${source_path%.txt}")"
python3 compiler.py "${flags[@]}" "$source_path" "$name.ll"
if command -v llc-18 >/dev/null; then
  llc-18 -filetype=obj -relocation-model=pic "$name.ll" -o "$name.o"
elif command -v llc >/dev/null; then
  llc -filetype=obj -relocation-model=pic "$name.ll" -o "$name.o"
else
  # Fallback for systems without llc; course Ubuntu should use llc.
  clang -Wno-override-module -fPIC -c "$name.ll" -o "$name.o"
fi
if [[ -n "$cfile" ]]; then
  clang -fPIE "$name.o" "$cfile" -o "$name"
else
  clang -fPIE "$name.o" -o "$name"
fi
echo "Built ./$name from compiler-generated $name.ll"
