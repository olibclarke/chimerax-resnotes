"""Run positional-note GUI checks with isolated ChimeraX preferences."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--chimerax', default='/Applications/ChimeraX_Daily.app/Contents/MacOS/ChimeraX')
    parser.add_argument('--model', type=Path, help='Also test a 24-residue selection in this supplied model')
    args = parser.parse_args()
    script = Path(__file__).resolve().with_name('check_positions_gui.py')
    with tempfile.TemporaryDirectory(prefix='chimerax-position-notes-') as tmp:
        env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=tmp+'/config',
                   XDG_DATA_HOME=tmp+'/data', XDG_CACHE_HOME=tmp+'/cache',
                   POSITION_NOTES_TEST_OUTPUT=str(args.report.resolve().with_suffix('.cif')))
        if args.model:
            env['REGION_NOTES_TEST_MODEL'] = str(args.model.resolve())
        with args.report.open('w') as output:
            result = subprocess.run([args.chimerax, '--notools', '--exit',
                                     '--script', json.dumps(str(script))], env=env, cwd=tmp,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=100)
        text = args.report.read_text(errors='replace')
        print('ChimeraX exit:', result.returncode, 'Log:', args.report)
        print('\n'.join(line for line in text.splitlines() if 'POSITION_NOTES_GUI' in line))
        if result.returncode or 'POSITION_NOTES_GUI: PASS' not in text:
            raise RuntimeError(text[-6500:])


if __name__ == '__main__':
    main()
