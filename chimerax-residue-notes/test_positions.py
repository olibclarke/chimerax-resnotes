"""Offline notes/codec regressions, including the actual Coot schema helpers."""
import ast
import base64
import importlib
import math
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import gemmi


ROOT = Path(__file__).resolve().parent
package = ModuleType('notes_under_test')
package.__path__ = [str(ROOT/'src')]
sys.modules[package.__name__] = package
io = importlib.import_module(package.__name__+'.io')
state = importlib.import_module(package.__name__+'.state')
positions = importlib.import_module(package.__name__+'.positions')


def point(xyz=(1.123456789012345, -2e-7, 30.5), identifier=1):
    return io.normalize_entry(dict(id=identifier, target_kind='position',
        **dict(zip(positions.POSITION_FIELDS, xyz)), title='Unassigned density',
        note='A site, not a residue.', author='Tester', modified_utc='2026-10-23T12:00:00Z'))


def residue(identifier=2):
    return io.normalize_entry(dict(id=identifier, auth_asym_id='A', auth_seq_id=12,
        label_comp_id='ALA', label_asym_id='A', label_seq_id='1', title='Residue',
        note='', author='Tester', modified_utc='2026-10-23T12:00:00Z'))


def region(identifier=3):
    return io.normalize_entry(dict(residue(identifier), target_kind='region',
        end_label_comp_id='GLY', end_label_asym_id='A', end_label_seq_id='2',
        end_auth_asym_id='A', end_auth_seq_id=13, end_pdbx_PDB_ins_code=''))


def coot_helpers():
    candidates = [ROOT.parent/'coot-trimmings/coot_trimmings.py',
                  ROOT.parent.parent/'coot-trimmings/coot_trimmings.py']
    configured = os.environ.get('COOT_TRIMMINGS_SCRIPT')
    source = Path(configured) if configured else next((p for p in candidates if p.is_file()), None)
    if source is None:
        raise unittest.SkipTest('Set COOT_TRIMMINGS_SCRIPT to run the optional Coot interoperability test')
    tree = ast.parse(source.read_text())
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and
             (node.name.startswith('_annotation_') or node.name == '_load_annotations_from_mmcif_file')]
    ns = dict(gemmi=gemmi, math=math, os=os, base64=base64,
        RESIDUE_ANNOTATION_CATEGORY_PREFIX=io.CATEGORY_PREFIX,
        RESIDUE_ANNOTATION_META_VERSION_TAG='_cootnote_annotation_meta.version',
        RESIDUE_ANNOTATION_META_PROGRAM_TAG='_cootnote_annotation_meta.program',
        RESIDUE_ANNOTATION_SCHEMA_VERSION='5',
        RESIDUE_ANNOTATION_RANGE_FIELDS=tuple(io.RANGE_FIELDS))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), ns)
    return ns


class PositionTests(unittest.TestCase):
    def test_no_fake_residue_and_finite_coordinates_only(self):
        entry = point()
        self.assertEqual(io.normalize_entry(entry), entry)
        self.assertIsNone(entry['auth_seq_id'])
        self.assertEqual(entry['auth_asym_id'], '')
        for bad in (None, '', '?', True, False, float('nan'), float('inf'), '-inf'):
            self.assertIsNone(io.normalize_entry(dict(entry, position_y=bad)))
        entry.pop('position_x')
        self.assertIsNone(io.normalize_entry(entry))

    def test_grouping_same_point_and_mixed_sort(self):
        entries = [point(), point(identifier=4), residue(), region(), point((0, 0, 0), 5)]
        threads = state.group_threads(entries)
        self.assertEqual(len(threads), 4)
        self.assertEqual(threads[0].entries[0]['target_kind'], 'residue')
        self.assertEqual(len(threads[-1].entries), 2)
        self.assertIn('Position (', threads[-1].label)
        self.assertIn('Position (', io.markdown_table_text(entries))

    def test_mixed_roundtrip_precision_and_atoms_unchanged(self):
        original = 'data_test\nloop_\n_atom_site.id\n_atom_site.Cartn_x\n1 10.125\n#\n'
        entries = [point(), residue(), region()]
        entries[0]['note'] = 'A "quoted" note with don\'t.\nloop_\n_fake_category.x\nUnicode: \u03b1'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'notes.cif'
            path.write_text(original)
            before = gemmi.cif.read_file(str(path)).sole_block().get_mmcif_category('_atom_site.')
            for _ in range(2):
                io.write_annotations(path, path, entries)
                self.assertEqual(sorted(io.read_annotations(path), key=lambda e: e['id']), entries)
                block = gemmi.cif.read_file(str(path)).sole_block()
                self.assertEqual(block.get_mmcif_category('_atom_site.'), before)
                self.assertEqual(len(block.find_values(io.CATEGORY_PREFIX+'id')), 3)

    def test_old_11_and_18_column_loops_and_legacy_base64(self):
        for width in (11, 18):
            entries = [residue()] if width == 11 else [region()]
            tags = io.ROW_TAGS[:width]
            for legacy in (False, True):
                rows = []
                actual_tags = []
                for tag in tags:
                    value = entries[0].get(tag, '?')
                    if legacy and tag in ('title', 'author', 'note'):
                        tag += '_b64'
                        value = base64.b64encode(str(value).encode()).decode()
                    actual_tags.append(io.CATEGORY_PREFIX+tag)
                    rows.append(io._cif_token(value))
                text = 'data_test\nloop_\n'+'\n'.join(actual_tags+rows)+'\n#\n'
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp)/'old.cif'
                    path.write_text(text)
                    loaded, = io.read_annotations(path)
                    self.assertEqual(loaded['target_kind'], 'residue' if width == 11 else 'region')
                    self.assertEqual(loaded['title'], entries[0]['title'])

    def test_coot_to_chimerax_to_coot(self):
        ns = coot_helpers()
        entries = [point(), residue(), region()]
        entries[0]['note'] = "don't discard apostrophes\nloop_\n_tag_like_text"
        doc = gemmi.cif.read_string('data_test\n_atom_site.id 1\n')
        rows = []
        for entry in entries:
            rows.append([str(entry.get(tag) if entry.get(tag) not in (None, '') else '?')
                         for tag in io.ROW_TAGS])
        ns['_annotation_write_entries_to_mmcif_block'](doc.sole_block(), rows)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'coot.cif'
            doc.write_file(str(path))
            imported = io.read_annotations(path)
            self.assertEqual(len(imported), 3)
            io.write_annotations(path, path, imported)
            reimported = ns['_load_annotations_from_mmcif_file'](str(path))
        self.assertEqual({e['id']: e for e in imported}, {e['id']: e for e in reimported})
        restored = next(e for e in reimported if e['id'] == 1)
        self.assertEqual(positions.position_xyz(restored), positions.position_xyz(entries[0]))

    def test_position_does_not_query_model_residues(self):
        fake_atomic = ModuleType('chimerax.atomic')
        fake_atomic.selected_residues = Mock()
        with patch.dict(sys.modules, {'chimerax': ModuleType('chimerax'), 'chimerax.atomic': fake_atomic}):
            selection = importlib.import_module(package.__name__+'.selection')
        model = SimpleNamespace()
        self.assertEqual(selection.find_residues_for_annotation(model, point()), [])
        self.assertIsNone(selection.find_residue_for_annotation(model, point()))
        self.assertFalse(selection.annotation_entry_matches_residue(point(), object()))

    def test_marker_cleanup_when_model_is_closed(self):
        highlight = positions.PositionHighlight()
        model = SimpleNamespace(deleted=False, remove_drawing=Mock())
        drawing = object()
        highlight.model, highlight.drawing = model, drawing
        highlight.clear()
        model.remove_drawing.assert_called_once_with(drawing)
        highlight.clear()
        model.deleted = True
        highlight.model, highlight.drawing = model, drawing
        highlight.clear()
        self.assertIsNone(highlight.drawing)

    def test_capture_cofr_before_editor_without_moving_it(self):
        tree = ast.parse((ROOT/'src/tool.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ResidueNotesTool')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_add_note_at_cofr')
        centre = [10., 20., 30.]
        class Place:
            def __init__(self, sign=1): self.sign = sign
            def __mul__(self, xyz): return tuple(value + self.sign for value in xyz)
            def inverse(self): return Place(-self.sign)
        model = SimpleNamespace(scene_position=Place())
        notes = SimpleNamespace(entries=[])
        def prompt():
            centre[:] = [100., 200., 300.]
            return 'Site', 'Tester', 'Unknown density'
        ns = dict(position_identifier_fields=positions.position_identifier_fields,
                  cofr_xyz=lambda session: tuple(centre), normalize_entry=io.normalize_entry,
                  next_note_id=state.next_note_id, note_thread_key=state.note_thread_key, now_utc=io.now_utc)
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'CoFR method', 'exec'), ns)
        tool = SimpleNamespace(_current_model=lambda: model, session=object(),
            _prompt_for_note=prompt, _atomic_models=lambda: [model], _state_for_model=lambda m: notes,
            _refresh_threads=Mock(), _set_status=Mock())
        ns['_add_note_at_cofr'](tool)
        self.assertEqual(positions.position_xyz(notes.entries[0]), (9., 19., 29.))
        self.assertEqual(positions.position_scene_xyz(model, notes.entries[0]), (10., 20., 30.))
        self.assertEqual(centre, [100., 200., 300.])
        tool._prompt_for_note = lambda: None
        ns['_add_note_at_cofr'](tool)
        self.assertEqual(len(notes.entries), 1)
        tool._prompt_for_note = prompt
        tool._atomic_models = lambda: []
        ns['_add_note_at_cofr'](tool)
        self.assertEqual(len(notes.entries), 1)


if __name__ == '__main__':
    unittest.main()
