"""Exercise the source bundle in an isolated, real ChimeraX GUI session."""
import importlib
import os
from pathlib import Path
import sys
from types import ModuleType
import traceback
from types import SimpleNamespace
from unittest.mock import patch

from numpy import array, allclose, dot
from chimerax.atomic import AtomicStructure
from chimerax.core.commands import run
from chimerax.geometry import rotation, translation


def check(session):
    root = Path(__file__).resolve().parents[1]
    package = ModuleType('positional_notes_gui_check')
    package.__path__ = [str(root/'src')]
    sys.modules[package.__name__] = package
    tool_module = importlib.import_module(package.__name__+'.tool')
    nearby_module = importlib.import_module(package.__name__+'.nearby_tool')
    io = importlib.import_module(package.__name__+'.io')
    state = importlib.import_module(package.__name__+'.state')
    positions = importlib.import_module(package.__name__+'.positions')
    selection = importlib.import_module(package.__name__+'.selection')
    fixture = root.parent/'annotated_example.cif'
    if not fixture.is_file():
        fixture = root.parent/'coot-trimmings/coot-download/pdb3ch3.ent'
    run(session, 'open "'+str(fixture)+'"')
    model = next(m for m in session.models.list() if isinstance(m, AtomicStructure))
    note_state = state.model_note_state(model)
    note_state.entries.clear()
    note_state.loaded_from_source = True
    before = model.atoms.coords.copy()
    model.scene_position = translation((20, -30, 40)) * rotation((0, 0, 1), 37)
    local_point = array((125.125, -321.5, 999.25))
    scene_point = model.scene_position * local_point
    session.main_view.center_of_rotation = scene_point
    original_camera = session.main_view.camera.position.matrix.copy()

    editor = tool_module.ResidueNotesTool(session, 'Residue Notes GUI check')
    assert editor.add_position_button.text() == 'Add note at center of rotation'
    assert editor.add_position_button.isEnabled()
    assert editor.add_button.text() == 'Add note from selection'
    assert not editor.add_button.isEnabled()
    def prompt(*args):
        assert allclose(session.main_view.center_of_rotation, scene_point)
        session.main_view.center_of_rotation = array((0., 0., 0.))
        return ('Unknown density', 'GUI tester', 'Not a residue.\nPotential ligand.')
    editor._prompt_for_note = prompt
    editor.add_position_button.click()
    entries = state.model_note_state(model).entries
    assert len(entries) == 1
    point = entries[0]
    assert allclose(positions.position_xyz(point), local_point)
    assert point['auth_seq_id'] is None
    assert allclose(session.main_view.camera.position.matrix, original_camera), 'Adding a note moved the view'
    residue_fields = selection.residue_identifier_fields(model.residues[0])
    residue = io.normalize_entry(dict(residue_fields, id=2, title='Residue', note='', author='Tester'))
    entries.append(residue)
    session.selection.clear()
    model.residues[:3].atoms.selected = True
    editor._update_button_states()
    assert editor.add_button.isEnabled()
    editor._prompt_for_note = lambda *args: ('Region from selection', 'Tester', '')
    editor.add_button.click()
    assert len(entries) == 3
    region = entries[-1]
    assert region['target_kind'] == 'region'
    assert selection.find_residues_for_annotation(model, region) == list(model.residues[:3])
    session.selection.clear()
    model.residues[0].atoms.selected = True
    model.residues[2].atoms.selected = True
    editor._prompt_for_note = lambda *args: (_ for _ in ()).throw(AssertionError('Invalid selection opened editor'))
    editor._add_note_from_selection()
    assert len(entries) == 3
    assert 'unselected gaps' in editor.status_label.text()
    session.selection.clear()

    previous_mode = session.ui.mouse_modes.mode('left', [], exact=True)
    def marker_count():
        return sum(d.name == 'Note range endpoint' for d in model.child_drawings())
    editor._start_region_picking(model)
    picker = editor._region_picker
    with patch.object(type(picker.view), 'picked_object', return_value=SimpleNamespace(atom=model.residues[0].find_atom('CA'))):
        picker.pick_at(0, 0)
    assert marker_count() == 1
    def cancel_with_markers(*args):
        assert marker_count() == 2
        return None
    editor._prompt_for_note = cancel_with_markers
    with patch.object(type(picker.view), 'picked_object', return_value=SimpleNamespace(residue=model.residues[2])):
        picker.pick_at(0, 0)
    assert marker_count() == 0
    assert session.ui.mouse_modes.mode('left', [], exact=True) is previous_mode
    assert len(entries) == 3
    editor._start_region_picking(model)
    picker = editor._region_picker
    with patch.object(type(picker.view), 'picked_object', return_value=SimpleNamespace(residue=model.residues[0])):
        picker.pick_at(0, 0)
    editor._cancel_region_picking()
    assert marker_count() == 0
    assert session.ui.mouse_modes.mode('left', [], exact=True) is previous_mode
    editor._refresh_threads(selected_key=state.note_thread_key(point))

    region_row = next(i for i, t in enumerate(editor._thread_rows)
                      if t.entries[0]['target_kind'] == 'region')
    editor._set_current_thread_row(region_row, navigate=False)
    editor._goto_thread(editor._current_thread())
    print('REGION_NAVIGATION_STATUS:', editor.status_label.text(), flush=True)
    expected_region_centre = model.residues[:3].atoms.scene_bounds.center()
    assert allclose(session.main_view.center_of_rotation, expected_region_centre), 'Region CoFR is wrong'
    assert allclose(session.main_view.camera.position.inverse() * expected_region_centre,
                    (0, 0, (session.main_view.camera.position.inverse() * expected_region_centre)[2])), 'Region is off screen centre'
    run(session, 'wait 2')
    assert allclose(session.main_view.center_of_rotation, expected_region_centre), 'Region centre drifted after frames'
    editor._set_current_thread_row(next(i for i, t in enumerate(editor._thread_rows)
                                       if t.entries[0]['target_kind'] == 'position'), navigate=False)

    camera = session.main_view.camera.position
    camera_axes = camera.matrix[:, :3].copy()
    depth = dot(session.main_view.center_of_rotation-camera.origin(), session.main_view.camera.view_direction())
    projection = (getattr(session.main_view.camera, 'field_of_view', None),
                  getattr(session.main_view.camera, 'field_width', None))
    editor._goto_thread(editor._current_thread())
    assert allclose(session.main_view.center_of_rotation, scene_point)
    assert allclose(session.main_view.camera.position.matrix[:, :3], camera_axes)
    assert abs(dot(scene_point-session.main_view.camera.position.origin(),
                   session.main_view.camera.view_direction())-depth) < 1e-3
    assert projection == (getattr(session.main_view.camera, 'field_of_view', None),
                          getattr(session.main_view.camera, 'field_width', None))
    assert editor._position_highlight.drawing is not None
    assert len(session.models.list(type=AtomicStructure)) == 1
    assert allclose(model.atoms.coords, before), 'Navigation changed atoms'

    editor._prompt_for_note = lambda *args: ('Edited site', 'GUI tester', 'Edited text')
    editor._edit_selected_note()
    assert point['title'] == 'Edited site'
    assert allclose(positions.position_xyz(point), local_point)
    assert editor._position_highlight.drawing is None

    nearby = nearby_module.NearbyNotesTool(session, 'Nearby Notes GUI check')
    session.main_view.center_of_rotation = scene_point + array((0, 0, 5))
    nearby._refresh_nearby_threads(force=True)
    assert any(r.thread.entries[0]['id'] == 1 and abs(r.distance-5) < 1e-4 for r in nearby._thread_rows)
    point_row = next(i for i, row in enumerate(nearby._thread_rows) if row.thread.entries[0]['id'] == 1)
    nearby.thread_list.setCurrentRow(point_row)
    nearby._on_thread_clicked()
    assert nearby._position_highlight.drawing is not None
    assert allclose(session.main_view.center_of_rotation, scene_point)
    model.scene_position = translation((100, 0, 0)) * model.scene_position
    nearby._refresh_nearby_threads(force=False)
    assert not any(r.thread.entries[0]['id'] == 1 for r in nearby._thread_rows)
    assert nearby._position_highlight.drawing is None

    session.main_view.center_of_rotation = selection.residue_center_xyz(model.residues[0])
    nearby.radius_spin.setValue(50)
    nearby._refresh_nearby_threads(force=True)
    nearby.thread_list.setCurrentRow(next(i for i, row in enumerate(nearby._thread_rows)
                                         if row.thread.entries[0]['target_kind'] == 'region'))
    view = session.main_view
    # Reproduce navigation from an old clipping slab far from the range.
    direction = view.camera.view_direction()
    view.clip_planes.set_clip_position('near', scene_point - direction, view)
    view.clip_planes.set_clip_position('far', scene_point + direction, view)
    nearby._on_thread_clicked()
    centre = model.residues[:3].atoms.scene_bounds.center()
    assert allclose(view.center_of_rotation, centre), 'Nearby region did not centre the range'
    assert nearby._region_highlight._residues
    for name in ('near', 'far'):
        assert abs(dot(view.clip_planes.find_plane(name).plane_point - centre, direction)) < 30
    run(session, 'wait 2')
    assert allclose(view.center_of_rotation, centre)

    output = Path(os.environ['POSITION_NOTES_TEST_OUTPUT'])
    assert editor.export_entries_to_path(str(output), model, overwrite=True) == 3
    exported = io.read_annotations(output)
    saved_point = next(e for e in exported if e['id'] == 1)
    assert allclose(positions.position_xyz(saved_point), local_point)
    assert allclose(model.atoms.coords, before)
    run(session, 'open "'+str(output)+'"')
    reloaded = [m for m in session.models.list(type=AtomicStructure) if m != model][0]
    assert allclose(reloaded.atoms.coords, before, atol=0.001), 'Export frame differs from note frame'
    editor._set_current_model(reloaded)
    assert len(state.model_note_state(reloaded).entries) == 3
    assert any(t.entries[0]['target_kind'] == 'position' for t in editor._thread_rows)
    editor._set_current_thread_row(next(i for i, t in enumerate(editor._thread_rows)
                                       if t.entries[0]['target_kind'] == 'region'), navigate=False)
    editor._on_thread_clicked()
    reloaded_centre = reloaded.residues[:3].atoms.scene_bounds.center()
    assert allclose(view.center_of_rotation, reloaded_centre), 'Reloaded region centre is wrong'
    run(session, 'wait 2')
    assert allclose(view.center_of_rotation, reloaded_centre)
    editor.delete()
    nearby.delete()
    assert allclose(model.atoms.coords, before)
    if os.environ.get('REGION_NOTES_TEST_MODEL'):
        check_supplied_model(session, tool_module, state, selection)
    print('POSITION_NOTES_GUI: PASS', flush=True)


def check_supplied_model(session, tool_module, state, selection):
    existing = set(session.models.list(type=AtomicStructure))
    run(session, 'open "'+os.environ['REGION_NOTES_TEST_MODEL']+'"')
    model = next(m for m in session.models.list(type=AtomicStructure) if m not in existing)
    before = model.atoms.coords.copy()
    editor = tool_module.ResidueNotesTool(session, 'Selection file check')
    editor._set_current_model(model)
    entries = state.model_note_state(model).entries
    initial_count = len(entries)
    # This file has two copies of each ID, one with polymer_type == PT_NONE.
    chosen = [r for r in model.residues if r.chain_id == 'D' and 80 <= r.number <= 91]
    assert len(chosen) == 24
    assert any(r.polymer_type == r.PT_NONE for r in chosen)
    session.selection.clear()
    for residue in chosen:
        residue.atoms.selected = True
    run(session, 'wait 1')
    editor._update_button_states()
    assert editor.add_button.isEnabled()
    prompted = []
    def prompt(*args):
        prompted.append(True)
        return 'Selected region', 'Regression', 'Real protein with incomplete chain classification'
    editor._prompt_for_note = prompt
    editor.add_button.click()
    assert prompted, editor.status_label.text()
    assert len(entries) == initial_count + 1
    region = entries[-1]
    members = selection.find_residues_for_annotation(model, region)
    assert set(members) == set(chosen), 'Repeated chain blocks expanded the target'
    assert region['auth_seq_id'] == 80 and region['end_auth_seq_id'] == 91
    editor._on_thread_clicked()
    centre = model.atoms.filter(model.atoms.selecteds).scene_bounds.center()
    assert allclose(session.main_view.center_of_rotation, centre)
    assert allclose(model.atoms.coords, before)
    assert len(model.atoms.coords) == len(before)
    # Endpoint picking must accept the same unassigned protein residues.
    editor._start_region_picking(model)
    picker = editor._region_picker
    with patch.object(type(picker.view), 'picked_object', return_value=SimpleNamespace(residue=chosen[0])):
        picker.pick_at(0, 0)
    assert picker._first is chosen[0]
    assert len(picker._markers._drawings) == 1
    editor._prompt_for_note = lambda *args: None
    with patch.object(type(picker.view), 'picked_object', return_value=SimpleNamespace(residue=chosen[-1])):
        picker.pick_at(0, 0)
    assert editor._region_picker is None
    assert not picker._markers._drawings
    assert len(entries) == initial_count + 1
    assert allclose(model.atoms.coords, before)
    editor.delete()
    print('SUPPLIED_MODEL_SELECTION: PASS', flush=True)


try:
    check(session)
except Exception:
    traceback.print_exc()
    print('POSITION_NOTES_GUI: FAIL', flush=True)
