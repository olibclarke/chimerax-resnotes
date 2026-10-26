"""Inspect selection annotation against a supplied model in isolated ChimeraX."""
from collections import Counter
import importlib
from pathlib import Path
import sys
from types import ModuleType

from chimerax.atomic import AtomicStructure
from chimerax.core.commands import run


root = Path(__file__).resolve().parents[1]
package = ModuleType('selection_file_check')
package.__path__ = [str(root/'src')]
sys.modules[package.__name__] = package
selection = importlib.import_module(package.__name__+'.selection')
run(session, 'open "'+sys.argv[1]+'"')
model = next(m for m in session.models.list() if isinstance(m, AtomicStructure))
print('POLYMER_TYPES:', Counter((r.name, r.polymer_type) for r in model.residues), flush=True)
for chain in model.chains:
    print('CHAIN:', chain.chain_id, chain.polymer_type, len(chain.existing_residues), flush=True)
for chain_id in ('A', 'B', 'C', 'D'):
    residues = [r for r in model.residues if r.chain_id == chain_id and 80 <= r.number <= 103]
    print('ENDPOINTS:', [(r.name, r.number, r.polymer_type, bool(r.chain)) for r in residues[:1]+residues[-1:]], flush=True)
    try:
        fields = selection.selection_note_fields(residues, model)
        print('SELECTION_FIELDS:', fields, flush=True)
    except ValueError as error:
        print('SELECTION_ERROR:', str(error), flush=True)
