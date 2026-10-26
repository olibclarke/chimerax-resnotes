"""Offline regressions for exact selection-to-region conversion."""
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


package = ModuleType('region_notes_under_test')
package.__path__ = [str(Path(__file__).resolve().parent/'src')]
sys.modules[package.__name__] = package
atomic = ModuleType('chimerax.atomic')
atomic.selected_residues = Mock()
with patch.dict(sys.modules, {'chimerax': ModuleType('chimerax'), 'chimerax.atomic': atomic}):
    selection = importlib.import_module(package.__name__+'.selection')
regions = importlib.import_module(package.__name__+'.regions')


class Residue:
    PT_NONE = 0

    def __init__(self, model, number, chain='A', insertion='', polymer_type=1):
        self.structure = model
        self.number = number
        self.chain_id = chain
        self.mmcif_chain_id = chain
        self.insertion_code = insertion
        self.polymer_type = polymer_type
        self.name = 'ALA'
        self.backbone = set()

    def find_atom(self, name):
        return object() if name in self.backbone else None


class RegionTests(unittest.TestCase):
    def setUp(self):
        self.model = SimpleNamespace(residues=[])
        # Numbering gaps and insertion codes are not selection gaps.
        self.residues = [Residue(self.model, 10), Residue(self.model, 10, insertion='A'),
                         Residue(self.model, 14), Residue(self.model, 15)]
        self.model.residues = self.residues

    def test_contiguous_selection_preserves_exact_members_and_insertion_codes(self):
        members = self.residues[:3]
        entry = selection.selection_note_fields(list(reversed(members)), self.model)
        self.assertEqual(entry['target_kind'], 'region')
        self.assertEqual(selection.find_residues_for_annotation(self.model, entry), members)
        entry = selection.selection_note_fields(self.residues[1:3], self.model)
        self.assertEqual(entry['pdbx_PDB_ins_code'], 'A')

    def test_rejects_disjoint_selection_without_filling_gaps(self):
        with self.assertRaisesRegex(ValueError, 'unselected gaps'):
            selection.selection_note_fields([self.residues[0], self.residues[2]], self.model)

    def test_single_residue_or_ligand_is_not_converted_to_a_region(self):
        ligand = Residue(self.model, 20, polymer_type=0)
        self.model.residues.append(ligand)
        for residue in (self.residues[0], ligand):
            entry = selection.selection_note_fields([residue], self.model)
            self.assertNotEqual(entry.get('target_kind'), 'region')
            self.assertEqual(selection.find_residues_for_annotation(self.model, entry), [residue])
        with self.assertRaises(ValueError):
            selection.selection_note_fields([self.residues[0], ligand], self.model)

    def test_rejects_empty_cross_model_and_cross_chain_selections(self):
        with self.assertRaises(ValueError):
            selection.selection_note_fields([], self.model)
        other = Residue(SimpleNamespace(residues=[]), 20)
        with self.assertRaisesRegex(ValueError, 'annotation model'):
            selection.selection_note_fields([self.residues[0], other], self.model)
        other = Residue(self.model, 20, chain='B')
        self.model.residues.append(other)
        with self.assertRaisesRegex(ValueError, 'same model and chain'):
            selection.selection_note_fields([self.residues[0], other], self.model)

    def test_backbone_fallback_for_unassigned_protein_and_nucleic_residues(self):
        for r in self.residues:
            r.polymer_type = 0
            r.backbone = {'N', 'CA', 'C'}
        fields = selection.selection_note_fields(self.residues[:3], self.model)
        self.assertEqual(selection.find_residues_for_annotation(self.model, fields), self.residues[:3])
        for r in self.residues:
            r.name = 'DA'
            r.backbone = {"C3'", "C4'", "O3'"}
        fields = selection.selection_note_fields(self.residues[:3], self.model)
        self.assertEqual(selection.find_residues_for_annotation(self.model, fields), self.residues[:3])
        self.residues[0].backbone = {'CA'}
        self.assertFalse(selection.is_polymer_residue(self.residues[0]))
        self.residues[0].name = 'HOH'
        self.residues[0].backbone = {'N', 'CA', 'C'}
        self.assertFalse(selection.is_polymer_residue(self.residues[0]))

    def test_repeated_chain_blocks_do_not_expand_to_the_whole_chain(self):
        unassigned = [Residue(self.model, r.number, insertion=r.insertion_code, polymer_type=0)
                      for r in self.residues]
        for r in unassigned:
            r.backbone = {'N', 'CA', 'C'}
        self.model.residues = unassigned + self.residues
        chosen = unassigned[1:3] + self.residues[1:3]
        fields = selection.selection_note_fields(chosen, self.model)
        self.assertEqual(selection.find_residues_for_annotation(self.model, fields), chosen)
        self.assertEqual(fields['auth_seq_id'], 10)
        self.assertEqual(fields['pdbx_PDB_ins_code'], 'A')
        self.assertEqual(fields['end_auth_seq_id'], 14)
        # Picking just one block cannot be silently broadened to both copies.
        with self.assertRaisesRegex(ValueError, 'unselected gaps'):
            selection.selection_note_fields(unassigned[1:3], self.model)

    def test_endpoint_cleanup_is_idempotent_and_handles_closed_models(self):
        model = SimpleNamespace(deleted=False, remove_drawing=Mock())
        highlight = regions.EndpointHighlight()
        drawing = object()
        highlight._drawings = [(model, drawing)]
        highlight.clear()
        highlight.clear()
        model.remove_drawing.assert_called_once_with(drawing)
        model.deleted = True
        highlight._drawings = [(model, drawing)]
        highlight.clear()
        self.assertEqual(highlight._drawings, [])


if __name__ == '__main__':
    unittest.main()
