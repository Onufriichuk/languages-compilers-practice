import subprocess
from pathlib import Path
import sys
root=Path(__file__).resolve().parent
compiler=root/'src/compiler.py'
failures=[]
total=sum(len(list((root/'tests'/folder).glob('*.txt'))) for folder in ('ok','err'))
for category in ('ok','err'):
    for source in sorted((root/'tests'/category).glob('*.txt')):
        expected=source.with_suffix('.expected').read_text()
        output=root/'output_test.ll'
        result=subprocess.run([sys.executable,str(compiler),str(source),str(output)],capture_output=True,text=True)
        if category == 'err':
            actual=result.stderr
            passed=result.returncode != 0 and actual==expected
        else:
            if result.returncode:
                actual=result.stderr
                passed=False
            else:
                import shutil
                lli=shutil.which('lli') or shutil.which('lli-18')
                if not lli:
                    raise RuntimeError('lli or lli-18 required to run successful programs')
                in_file=source.with_suffix('.in')
                input_data=in_file.read_text() if in_file.exists() else ''
                run=subprocess.run([lli,str(output)],input=input_data,capture_output=True,text=True)
                actual=run.stdout
                passed=run.returncode==0 and actual==expected
        print(('PASS' if passed else 'FAIL'),category,source.stem)
        if not passed:
            failures.append((source.name,actual,expected))
        if output.exists():output.unlink()
print('Passed',total-len(failures),'/',total)
if failures:
    for name,actual,expected in failures:print('FAIL',name,'\nActual:',actual,'\nExpected:',expected)
    sys.exit(1)
