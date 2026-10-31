"""Release metadata and wheel-content checks; no ChimeraX required."""
import importlib.util
import ast
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('release_tools', ROOT/'tools/prepare_toolshed_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_roundtrip_coordinates_are_compared_by_atom_identity_not_water_order(self):
        tree = ast.parse((ROOT/'tools/check_positions_gui.py').read_text())
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'atom_coordinates_by_identity')
        namespace = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'atom identity helper', 'exec'), namespace)
        snapshot = namespace['atom_coordinates_by_identity']
        def atom(number, xyz):
            residue = SimpleNamespace(chain_id='A', number=number, insertion_code='', name='HOH')
            return SimpleNamespace(residue=residue, name='O', alt_loc='', coord=xyz)
        first, second = atom(10, (1, 2, 3)), atom(11, (4, 5, 6))
        self.assertEqual(snapshot(SimpleNamespace(atoms=[first, second])),
                         snapshot(SimpleNamespace(atoms=[second, first])))
        with self.assertRaises(AssertionError):
            snapshot(SimpleNamespace(atoms=[first, first]))

    def fixture(self, root, *, omit=None, replace=None):
        version = ET.parse(ROOT/'bundle_info.xml').getroot().attrib['version']
        metadata = ('Metadata-Version: 2.1\nName: ChimeraX-ResidueNotes\nVersion: '+version+'\n'
                    'Author-email: olibclarke@gmail.com\nLicense: MIT\nRequires-Python: >=3.10\n'
                    'Home-page: https://github.com/olibclarke/chimerax-resnotes\n')
        for dependency in ET.parse(ROOT/'bundle_info.xml').getroot().findall('Dependencies/Dependency'):
            metadata += 'Requires-Dist: '+dependency.attrib['name']+dependency.attrib['version']+'\n'
        if replace:
            metadata = metadata.replace(*replace)
        wheel = root/'test.whl'
        with ZipFile(wheel, 'w') as archive:
            archive.writestr('chimerax_residuenotes-'+version+'.dist-info/METADATA', metadata+'\n')
            for name in ('__init__.py', 'positions.py', 'regions.py', 'picking.py', 'navigation.py', 'license.txt',
                         'docs/user/tools/residue_notes.html'):
                if name != omit:
                    data = (ROOT/'license.txt').read_text() if name == 'license.txt' else 'test'
                    archive.writestr(release.PACKAGE+name, data)
        return wheel, version

    def test_metadata_declares_maintainer_license_and_python_floor(self):
        root = ET.parse(ROOT/'bundle_info.xml').getroot()
        self.assertEqual(root.attrib['limitedAPI'], '3.10')
        self.assertEqual(root.findtext('Email'), 'olibclarke@gmail.com')
        self.assertEqual(root.findtext('License'), 'MIT')
        deps = {entry.attrib['name']: entry.attrib['version']
                for entry in root.findall('Dependencies/Dependency')}
        self.assertEqual(deps['ChimeraX-Core'], '>=1.11')
        self.assertNotIn('gemmi', {name.lower() for name in deps})
        self.assertIn('Copyright (c) 2026 Oliver Clarke', (ROOT/'license.txt').read_text())

    def test_accepted_wheel_has_a_hash_and_dependency_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel, version = self.fixture(Path(tmp))
            manifest = release.inspect_wheel(wheel, version)
            self.assertEqual(len(manifest['sha256']), 64)
            self.assertEqual(manifest['version'], version)
            self.assertTrue(manifest['dependencies'])

    def test_missing_help_license_and_modules_are_rejected(self):
        for omitted in ('positions.py', 'license.txt', 'docs/user/tools/residue_notes.html'):
            with self.subTest(omitted=omitted), tempfile.TemporaryDirectory() as tmp:
                wheel, version = self.fixture(Path(tmp), omit=omitted)
                with self.assertRaisesRegex(ValueError, 'missing'):
                    release.inspect_wheel(wheel, version)

    def test_stale_metadata_is_rejected(self):
        for replacement in (('>=3.10', '>=3.7'), ('License: MIT', 'License: unknown'),
                            ('ChimeraX-Core>=1.11', 'gemmi>=0.7')):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as tmp:
                wheel, version = self.fixture(Path(tmp), replace=replacement)
                with self.assertRaises(ValueError):
                    release.inspect_wheel(wheel, version)

    def test_environment_is_isolated_and_offline(self):
        root = Path('/tmp/isolated-release')
        env = release.isolated_environment(root)
        for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME'):
            self.assertTrue(Path(env[key]).is_relative_to(root))
        self.assertEqual(env['PIP_NO_INDEX'], '1')
        self.assertNotIn('PYTHONPATH', env)
        self.assertNotIn('PYTHONHOME', env)


if __name__ == '__main__':
    unittest.main()
