"""Native release checks, only inside an explicitly isolated ChimeraX profile."""
import importlib
import os
from pathlib import Path
import runpy
import sys
import traceback

from chimerax import app_dirs
from chimerax.core.commands import run


def check(session):
    profile = Path(os.environ['RESNOTES_RELEASE_PROFILE']).resolve()
    data = Path(app_dirs.user_data_dir).resolve()
    assert data.is_relative_to(profile), f'Refusing to modify non-test profile: {data}'
    phase = os.environ['RESNOTES_RELEASE_PHASE']
    name = 'ChimeraX-ResidueNotes'
    expected = os.environ['RESNOTES_RELEASE_VERSION']
    if phase == 'install':
        assert session.toolshed.find_bundle(name, session.logger) is None
        session.toolshed.install_bundle(os.environ['RESNOTES_RELEASE_WHEEL'], session.logger,
                                        session=session, no_deps=True)
        session.toolshed.reload(session.logger, rebuild_cache=True)
        bundle = session.toolshed.find_bundle(name, session.logger)
        assert bundle is not None and bundle.version == expected
    elif phase == 'uninstall':
        bundle = session.toolshed.find_bundle(name, session.logger)
        assert bundle is not None and bundle.version == expected
        session.toolshed.uninstall_bundle(bundle, session.logger, session=session)
        session.toolshed.reload(session.logger, rebuild_cache=True)
        assert session.toolshed.find_bundle(name, session.logger) is None
    elif phase == 'gui':
        bundle = session.toolshed.find_bundle(name, session.logger)
        assert bundle is not None and bundle.version == expected
        module = importlib.import_module('chimerax.residue_notes')
        installed = Path(module.__file__).resolve().parent
        assert installed.is_relative_to(profile), installed
        for relative in ('license.txt', 'docs/user/tools/residue_notes.html'):
            assert (installed/relative).is_file(), relative

        root = Path(__file__).resolve().parents[1]
        fixture = root.parent/'annotated_example.cif'
        if not fixture.is_file():
            fixture = root.parent/'coot-trimmings/coot-download/pdb3ch3.ent'
        run(session, 'open "'+str(fixture)+'"')
        # Invoke a subcommand first to exercise lazy Tool Shed registration.
        run(session, 'resnotes import "'+str(fixture)+'" #1')
        run(session, 'nearby_notes #1')
        run(session, 'resnotes refresh #1')
        output = Path(os.environ['POSITION_NOTES_TEST_OUTPUT'])
        run(session, 'resnotes export "'+str(output)+'" #1 overwrite true')
        run(session, 'resnotes export-markdown "'+str(output.with_suffix('.md'))+'" #1 overwrite true')
        assert output.is_file() and output.with_suffix('.md').is_file()
        from chimerax.residue_notes.tool import ResidueNotesTool
        from chimerax.residue_notes.nearby_tool import NearbyNotesTool
        for tool in list(session.tools.list()):
            if isinstance(tool, (ResidueNotesTool, NearbyNotesTool)):
                tool.delete()
        run(session, 'close all')
        os.environ['RESNOTES_TEST_INSTALLED'] = '1'
        source = root/'tools/check_positions_gui.py'
        # Load its helpers without executing the source-mode entry point.
        namespace = runpy.run_path(str(source))
        namespace['check'](session)
        assert 'Gemmi' not in sys.modules and 'gemmi' not in sys.modules
    else:
        raise ValueError('Unknown phase: '+phase)
    print('RESNOTES_RELEASE_'+phase.upper()+': PASS', flush=True)


def run_checks():
    gui = os.environ['RESNOTES_RELEASE_PHASE'] == 'gui'
    capture_pending = False
    try:
        check(session)
        if gui and os.environ.get('RESNOTES_RELEASE_SCREENSHOT'):
            prepare_demo()
            from Qt.QtCore import QTimer
            QTimer.singleShot(1000, capture_demo)
            capture_pending = True
            return
    except Exception:
        traceback.print_exc()
        print('RESNOTES_RELEASE: FAIL', flush=True)
        if not gui:
            raise SystemExit(1)
    finally:
        if gui and not capture_pending:
            session.ui.quit(confirm=False)


def prepare_demo():
    from chimerax.atomic import AtomicStructure
    from chimerax.residue_notes import io, selection, state, positions
    from chimerax.residue_notes.tool import show_residue_notes_tool

    run(session, 'close all')
    root = Path(__file__).resolve().parents[1]
    fixture = root.parent/'annotated_example.cif'
    if not fixture.is_file():
        fixture = root.parent/'coot-trimmings/coot-download/pdb3ch3.ent'
    run(session, 'open "'+str(fixture)+'"')
    model = session.models.list(type=AtomicStructure)[0]
    model.name = 'Annotation example'
    residues = [r for r in model.residues if selection.is_polymer_residue(r)]
    first, last = residues[0], residues[2]
    entries = state.model_note_state(model)
    entries.entries.clear()
    entries.loaded_from_source = True
    xyz = selection.residue_center_xyz(first)
    targets = [
        (selection.residue_identifier_fields(first), 'Residue annotation',
         'Example: inspect this residue during model review.'),
        (selection.region_identifier_fields(first, last), 'Motif / region',
         'Example: a named region, domain boundary or structural motif.'),
        (positions.position_identifier_fields(model, (xyz[0]+4, xyz[1]+4, xyz[2])),
         'Unknown-density site', 'Example: a spatial note without a residue attachment.'),
    ]
    for index, (fields, title, text) in enumerate(targets, 1):
        entries.entries.append(io.normalize_entry(dict(fields, id=index, title=title,
                                                       author='Demo', note=text)))
    run(session, 'view #'+model.id_string)
    tool = show_residue_notes_tool(session)
    tool._set_current_model(model)
    tool._refresh_threads(selected_key=state.note_thread_key(entries.entries[1]))
    tool._goto_thread(tool._current_thread())


def capture_demo():
    try:
        from chimerax.residue_notes.tool import show_residue_notes_tool
        path = Path(os.environ['RESNOTES_RELEASE_SCREENSHOT'])
        tool = show_residue_notes_tool(session)
        assert tool.tool_window.ui_area.grab().save(str(path))
        session.main_view.image(width=1200, height=900, supersample=1).save(
            path.with_name('annotated-region.png'))
        print('RESNOTES_RELEASE_SCREENSHOTS: PASS', flush=True)
    except Exception:
        traceback.print_exc()
        print('RESNOTES_RELEASE_SCREENSHOTS: FAIL', flush=True)
    finally:
        session.ui.quit(confirm=False)


if os.environ['RESNOTES_RELEASE_PHASE'] == 'gui':
    from Qt.QtCore import QTimer
    # Startup scripts run before the main window is painted.
    QTimer.singleShot(1000, run_checks)
else:
    run_checks()
