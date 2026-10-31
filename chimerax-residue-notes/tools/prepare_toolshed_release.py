"""Build, inspect, and optionally install-test a wheel without using personal profiles."""
import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'chimerax/residue_notes/'


def inspect_wheel(path, expected_version):
    with ZipFile(path) as archive:
        names = archive.namelist()
        metadata = BytesParser().parsebytes(archive.read(next(
            name for name in names if name.endswith('.dist-info/METADATA'))))
        for relative in ('__init__.py', 'picking.py', 'positions.py', 'regions.py', 'navigation.py',
                         'license.txt', 'docs/user/tools/residue_notes.html'):
            if PACKAGE+relative not in names:
                raise ValueError('Wheel is missing '+relative)
        license_text = archive.read(PACKAGE+'license.txt').decode('utf-8')
        if 'MIT License' not in license_text or 'Oliver Clarke' not in license_text:
            raise ValueError('Wheel must contain the MIT license')
        for key, expected in (('Name', 'ChimeraX-ResidueNotes'), ('Version', expected_version),
                              ('Author-email', 'olibclarke@gmail.com'), ('License', 'MIT'),
                              ('Home-page', 'https://github.com/olibclarke/chimerax-resnotes'),
                              ('Requires-Python', '>=3.10')):
            if metadata[key] != expected:
                raise ValueError(f'{key}: expected {expected!r}, found {metadata[key]!r}')
        dependencies = metadata.get_all('Requires-Dist', [])
        required = {'ChimeraX-Core', 'ChimeraX-Atomic', 'ChimeraX-UI', 'ChimeraX-Geometry',
                    'ChimeraX-Graphics', 'ChimeraX-MouseModes', 'ChimeraX-Surface',
                    'ChimeraX-mmCIF', 'numpy'}
        from_names = {value.split(' ')[0].split('>')[0].split('~')[0] for value in dependencies}
        if not required <= from_names or any('gemmi' in value.lower() for value in dependencies):
            raise ValueError('Incorrect runtime dependencies: '+repr(dependencies))
        if any(name.endswith(('.pyc', '.pdb', '.cif')) or '__pycache__/' in name for name in names):
            raise ValueError('Wheel contains test models or bytecode')
    return dict(filename=path.name, version=expected_version,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                license=metadata['License'], maintainer_email=metadata['Author-email'],
                homepage=metadata['Home-page'], requires_python=metadata['Requires-Python'],
                dependencies=dependencies)


def isolated_environment(profile):
    env = dict(os.environ, HOME=str(profile), XDG_CONFIG_HOME=str(profile/'config'),
               XDG_DATA_HOME=str(profile/'data'), XDG_CACHE_HOME=str(profile/'cache'),
               XDG_STATE_HOME=str(profile/'state'), PYTHONDONTWRITEBYTECODE='1',
               PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1',
               RESNOTES_RELEASE_PROFILE=str(profile))
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    return env


def run_chimerax(executable, arguments, cwd, env, report, marker=None, *, exit_after=True):
    with report.open('w') as output:
        process = subprocess.Popen([executable, '--notools', *(['--exit'] if exit_after else []), *arguments],
                                   cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            returncode = process.wait(timeout=150)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
            raise
    text = report.read_text(errors='replace')
    if returncode or (marker and marker not in text):
        raise RuntimeError(f'ChimeraX check failed; see {report}\n'+text[-5000:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chimerax', default='/Applications/ChimeraX_Daily.app/Contents/MacOS/ChimeraX')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--test-install', action='store_true')
    args = parser.parse_args()
    executable = str(Path(args.chimerax).resolve())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # A failed retry must not leave an earlier success manifest beside a new wheel.
    for name in ('manifest.json', 'SHA256SUMS'):
        (output/name).unlink(missing_ok=True)
    version = ET.parse(ROOT/'bundle_info.xml').getroot().attrib['version']
    with tempfile.TemporaryDirectory(prefix='resnotes-release-') as temporary:
        temporary = Path(temporary)
        staged = temporary/'bundle'
        staged.mkdir()
        for name in ('bundle_info.xml', 'license.txt'):
            shutil.copy2(ROOT/name, staged/name)
        for name in ('src', 'docs'):
            shutil.copytree(ROOT/name, staged/name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'license.txt'))
        env = isolated_environment(temporary/'build-profile')
        run_chimerax(executable, ['--nogui', '--cmd', 'devel build .'], staged, env, output/'build.log')
        wheels = list((staged/'dist').glob('*.whl'))
        if len(wheels) != 1:
            raise RuntimeError('Build did not produce exactly one wheel; see build.log')
        manifest = inspect_wheel(wheels[0], version)
        wheel = output/wheels[0].name
        shutil.copy2(wheels[0], wheel)
        checks = []
        if args.test_install:
            env = isolated_environment(temporary/'install-profile')
            env.update(RESNOTES_RELEASE_WHEEL=str(wheel), RESNOTES_RELEASE_VERSION=version,
                       POSITION_NOTES_TEST_OUTPUT=str(output/'roundtrip.cif'),
                       RESNOTES_RELEASE_SCREENSHOT=str(output/'residue-notes.png'))
            script = json.dumps(str(ROOT/'tools/check_release_install.py'))
            for phase in ('install', 'gui', 'uninstall'):
                env['RESNOTES_RELEASE_PHASE'] = phase
                arguments = ['--script', script]
                if phase != 'gui':
                    arguments.insert(0, '--nogui')
                run_chimerax(executable, arguments, temporary, env,
                             output/(phase+'.log'), 'RESNOTES_RELEASE_'+phase.upper()+': PASS',
                             exit_after=phase != 'gui')
                checks.append(phase)
                if phase == 'gui' and 'RESNOTES_RELEASE_SCREENSHOTS: PASS' not in (output/'gui.log').read_text():
                    raise RuntimeError('Screenshot capture failed; see gui.log')
        manifest['installed_wheel_checks'] = checks
        manifest['tested_platform'] = sys.platform if checks else None
        build_text = (output/'build.log').read_text(errors='replace')
        native_version = re.search(r'UCSF ChimeraX version: ([^\s]+)', build_text)
        manifest['tested_chimerax'] = native_version.group(1) if native_version and checks else None
        manifest['untested'] = ['stable ChimeraX 1.11', 'Windows', 'Linux']
        (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        (output/'SHA256SUMS').write_text(manifest['sha256']+'  '+wheel.name+'\n')
        for name in ('SUBMISSION.md', 'license.txt'):
            shutil.copy2(ROOT/name, output/name)
    print('Prepared:', wheel)
    print('Verified:', ', '.join(checks) or 'wheel metadata and contents only')


if __name__ == '__main__':
    main()
