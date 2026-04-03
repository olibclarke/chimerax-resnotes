import json
import os

from Qt.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from chimerax.atomic import AtomicStructure, get_triggers as atomic_triggers
from chimerax.core.commands import run
from chimerax.core.models import ADD_MODELS, MODEL_ID_CHANGED, MODEL_NAME_CHANGED, REMOVE_MODELS
from chimerax.core.selection import SELECTION_CHANGED
from chimerax.core.tools import ToolInstance, get_singleton
from chimerax.ui import MainToolWindow

from .io import default_author, normalize_entry, now_utc, read_annotations, write_annotations, write_markdown_table
from .selection import closest_residue_to_xyz, cofr_key, single_selected_residue, safe_model_residues, selected_residues_for_model
from .state import ModelNoteState, group_threads, next_note_id, note_thread_key, thread_detail_text, thread_key_for_residue, thread_preview
from .ui import build_residue_notes_ui


def show_residue_notes_tool(session):
    return get_singleton(session, ResidueNotesTool, "Residue Notes", create=True)


class ResidueNotesTool(ToolInstance):
    SESSION_ENDURING = False
    SESSION_SAVE = False
    help = "help:user/tools/residue_notes.html"

    def __init__(self, session, tool_name):
        super().__init__(session, tool_name)
        self._model_state = {}
        self._thread_rows = []
        self._building_ui = False
        self._closest_residue_cache = {"model": None, "cofr_key": None, "residue": None}
        self._trigger_handlers = []
        self._last_selection_signature = None
        self._last_io_dir = ""
        self._session_author = default_author()

        self.tool_window = MainToolWindow(self)
        self._build_ui()
        self._refresh_models()
        self._install_triggers()
        self.tool_window.manage("side")

    def delete(self):
        for handler in getattr(self, "_trigger_handlers", []):
            try:
                handler.remove()
            except Exception:
                pass
        self._trigger_handlers = []
        super().delete()

    def _build_ui(self):
        self._building_ui = True
        self.widgets = build_residue_notes_ui(
            self.tool_window.ui_area,
            {
                "on_model_changed": self._on_model_changed,
                "refresh_models": self._refresh_models,
                "import_model_source": self._import_from_model_source,
                "import_file": self._import_from_file,
                "export_file": self._export_to_file,
                "export_markdown": self._export_markdown_to_file,
                "add_note": self._add_note_for_selected_residue,
                "edit_note": self._edit_selected_note,
                "delete_note": self._delete_selected_note,
                "thread_changed": self._on_thread_changed,
                "thread_clicked": self._on_thread_clicked,
                "previous_thread": self._goto_previous_thread,
                "next_thread": self._goto_next_thread,
            },
        )
        self.model_combo = self.widgets.model_combo
        self.refresh_models_button = self.widgets.refresh_models_button
        self.source_label = self.widgets.source_label
        self.active_residue_label = self.widgets.active_residue_label
        self.status_label = self.widgets.status_label
        self.import_auto_button = self.widgets.import_auto_button
        self.import_file_button = self.widgets.import_file_button
        self.export_file_button = self.widgets.export_file_button
        self.export_markdown_button = self.widgets.export_markdown_button
        self.add_button = self.widgets.add_button
        self.edit_button = self.widgets.edit_button
        self.delete_button = self.widgets.delete_button
        self.thread_list = self.widgets.thread_list
        self.detail_text = self.widgets.detail_text
        self.prev_button = self.widgets.prev_button
        self.next_button = self.widgets.next_button
        self._building_ui = False
        self._set_empty_detail_text("No annotated residues in the current model.")
        self._update_button_states()

    def _atomic_models(self):
        return [model for model in self.session.models.list() if isinstance(model, AtomicStructure)]

    def _set_status(self, message):
        self.status_label.setText(f"Status: {message}")

    def _normalize_path(self, path):
        return os.path.abspath(os.path.expanduser(path))

    def _remember_io_path(self, path):
        normalized = self._normalize_path(path)
        directory = normalized if os.path.isdir(normalized) else os.path.dirname(normalized)
        if directory:
            self._last_io_dir = directory

    def _default_import_dir(self):
        if self._last_io_dir and os.path.isdir(self._last_io_dir):
            return self._last_io_dir
        model = self._current_model()
        if model is not None:
            source_path = self._state_for_model(model).source_path
            if source_path:
                source_dir = os.path.dirname(self._normalize_path(source_path))
                if os.path.isdir(source_dir):
                    return source_dir
        desktop = os.path.expanduser("~/Desktop")
        if os.path.isdir(desktop):
            return desktop
        return os.path.expanduser("~")

    def _install_triggers(self):
        self._trigger_handlers = [
            self.session.triggers.add_handler(SELECTION_CHANGED, self._selection_changed_cb),
            self.session.triggers.add_handler(ADD_MODELS, self._models_changed_cb),
            self.session.triggers.add_handler(REMOVE_MODELS, self._models_changed_cb),
            self.session.triggers.add_handler(MODEL_ID_CHANGED, self._models_changed_cb),
            self.session.triggers.add_handler(MODEL_NAME_CHANGED, self._models_changed_cb),
            self.session.triggers.add_handler("new frame", self._new_frame_cb),
            atomic_triggers().add_handler("changes done", self._atomic_changes_done_cb),
        ]

    def _default_model(self):
        residues = selected_residues_for_model(self.session)
        if residues:
            return residues[0].structure
        models = self._atomic_models()
        return models[0] if models else None

    def _current_model(self):
        return self.model_combo.currentData()

    def _state_for_model(self, model):
        state = self._model_state.get(model)
        if state is None:
            state = ModelNoteState()
            self._model_state[model] = state
        if state.source_path is None:
            state.source_path = self._model_source_path(model)
        return state

    def _model_source_path(self, model):
        for attr_name in ("filename", "path", "opened_path", "session_path"):
            path = getattr(model, attr_name, None)
            if isinstance(path, str) and path:
                return path
        return None

    def _model_label(self, model):
        return f"#{model.id_string} {model.name}"

    def _cleanup_model_state(self, models):
        live_models = set(models)
        stale_models = [model for model in self._model_state if model not in live_models]
        for model in stale_models:
            self._model_state.pop(model, None)

    def _update_source_label(self):
        model = self._current_model()
        if model is None:
            self.source_label.setText("Source: none")
            return
        state = self._state_for_model(model)
        source_path = state.source_path
        if source_path:
            note_count = len(state.entries)
            thread_count = len(group_threads(state.entries))
            if note_count:
                self.source_label.setText(
                    "Source: {0} ({1} thread{2}, {3} note{4})".format(
                        os.path.basename(source_path),
                        thread_count,
                        "" if thread_count == 1 else "s",
                        note_count,
                        "" if note_count == 1 else "s",
                    )
                )
            else:
                self.source_label.setText(f"Source: {os.path.basename(source_path)}")
        else:
            self.source_label.setText("Source: no associated file")

    def _update_active_residue_label(self):
        label_prefix, residue = self._residue_target()
        if residue is None:
            self.active_residue_label.setText("Selected residue: none")
            return
        self.active_residue_label.setText(
            "{0}: {1}:{2}{3} {4}".format(
                label_prefix,
                residue.chain_id,
                residue.number,
                residue.insertion_code or "",
                residue.name,
            )
        )

    def _single_selected_residue(self):
        return single_selected_residue(self.session, model=self._current_model())

    def _closest_residue_to_cofr(self):
        model = self._current_model()
        if model is None:
            return None
        cofr_xyz, rounded_key = cofr_key(self.session)
        if cofr_xyz is None:
            return None
        if (
            self._closest_residue_cache["model"] is model
            and self._closest_residue_cache["cofr_key"] == rounded_key
        ):
            return self._closest_residue_cache["residue"]
        best_residue = closest_residue_to_xyz(model, cofr_xyz)
        self._closest_residue_cache = {
            "model": model,
            "cofr_key": rounded_key,
            "residue": best_residue,
        }
        return best_residue

    def _residue_target(self):
        selected_residue = self._single_selected_residue()
        if selected_residue is not None:
            return "Selected residue", selected_residue
        closest_residue = self._closest_residue_to_cofr()
        if closest_residue is not None:
            return "Closest residue", closest_residue
        return "Selected residue", None

    def _selection_signature(self):
        model = self._current_model()
        label_prefix, residue = self._residue_target()
        model_id = getattr(model, "id_string", None) if model is not None else None
        if residue is None:
            return (model_id, label_prefix, None)
        return (
            model_id,
            label_prefix,
            residue.chain_id,
            residue.number,
            residue.insertion_code or "",
            residue.name or "",
        )

    def _refresh_target_state(self, *, force=False, sync_thread=True):
        try:
            signature = self._selection_signature()
        except Exception:
            return
        if signature == self._last_selection_signature:
            if force:
                self._update_active_residue_label()
                self._update_button_states()
                if sync_thread:
                    self._sync_thread_to_single_selected_residue()
            return
        self._last_selection_signature = signature
        self._update_active_residue_label()
        self._update_button_states()
        if sync_thread:
            self._sync_thread_to_single_selected_residue()

    def _selection_changed_cb(self, *_args):
        self._refresh_target_state(force=True, sync_thread=True)

    def _models_changed_cb(self, *_args):
        self._closest_residue_cache = {"model": None, "cofr_key": None, "residue": None}
        self._last_selection_signature = None
        self._refresh_models()

    def _atomic_changes_done_cb(self, *_args):
        self._closest_residue_cache = {"model": None, "cofr_key": None, "residue": None}
        self._last_selection_signature = None
        self._refresh_target_state(force=True, sync_thread=True)

    def _new_frame_cb(self, *_args):
        if self._single_selected_residue() is not None:
            return
        self._refresh_target_state(force=False, sync_thread=False)

    def _refresh_models(self):
        current = self._current_model()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        models = self._atomic_models()
        self._cleanup_model_state(models)
        for model in models:
            self.model_combo.addItem(self._model_label(model), model)
        if models:
            target = current if current in models else self._default_model()
            index = max(0, self.model_combo.findData(target))
            self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(False)
        self._on_model_changed()

    def _resolve_model(self, model=None):
        target_model = self._current_model() if model is None else model
        if target_model is None:
            raise ValueError("No atomic model selected.")
        if not isinstance(target_model, AtomicStructure):
            raise ValueError("Residue Notes only works with atomic structure models.")
        return target_model

    def _set_current_model(self, model):
        if model is None:
            return
        index = self.model_combo.findData(model)
        if index < 0:
            raise ValueError(f"Model is not available in the Residue Notes tool: {getattr(model, 'name', model)!r}")
        if index != self.model_combo.currentIndex():
            self.model_combo.setCurrentIndex(index)

    def _update_button_states(self):
        model = self._current_model()
        thread = self._current_thread()
        has_model = model is not None
        has_threads = bool(self._thread_rows)
        can_import_embedded = has_model and self._can_import_embedded_for_model(model)
        _label_prefix, residue = self._residue_target() if has_model else ("Selected residue", None)
        self.import_auto_button.setEnabled(can_import_embedded)
        self.import_file_button.setEnabled(has_model)
        self.export_file_button.setEnabled(has_model)
        self.export_markdown_button.setEnabled(has_model)
        self.add_button.setEnabled(has_model and residue is not None)
        self.edit_button.setEnabled(thread is not None)
        self.delete_button.setEnabled(thread is not None)
        self.prev_button.setEnabled(has_threads)
        self.next_button.setEnabled(has_threads)
        if can_import_embedded:
            self.import_auto_button.setToolTip("Import embedded notes from the current model source file")
        elif has_model:
            self.import_auto_button.setToolTip("Current model has no readable mmCIF source file")
        else:
            self.import_auto_button.setToolTip("No atomic model selected")

    def _set_empty_detail_text(self, message):
        self.detail_text.setPlainText(message)

    def _can_import_embedded_for_model(self, model):
        if model is None:
            return False
        source_path = self._state_for_model(model).source_path
        if not source_path or not os.path.exists(source_path):
            return False
        return source_path.lower().endswith((".cif", ".mmcif"))

    def _auto_import_if_possible(self, model):
        state = self._state_for_model(model)
        if state.loaded_from_source:
            return
        state.loaded_from_source = True
        source_path = state.source_path
        if not source_path or not os.path.exists(source_path):
            return
        if not source_path.lower().endswith((".cif", ".mmcif")):
            return
        try:
            state.entries = read_annotations(source_path)
        except Exception as error:
            self.session.logger.warning(f"Residue Notes: failed to import embedded annotations from {source_path}: {error!r}")

    def _on_model_changed(self, *_args):
        if self._building_ui:
            return
        self._closest_residue_cache = {"model": None, "cofr_key": None, "residue": None}
        model = self._current_model()
        if model is None:
            self.thread_list.clear()
            self._set_empty_detail_text("No atomic model selected.")
            self._thread_rows = []
            self._update_source_label()
            self._update_active_residue_label()
            self._update_button_states()
            self._set_status("No atomic model selected")
            return
        self._auto_import_if_possible(model)
        self._update_source_label()
        self._refresh_threads()
        self._refresh_target_state(force=True, sync_thread=True)
        self._set_status(f"Ready for {self._model_label(model)}")

    def _set_current_thread_row(self, row, *, reactivate_if_same=False):
        if row is None or row < 0 or row >= len(self._thread_rows):
            return
        current_row = self.thread_list.currentRow()
        if row == current_row:
            current_item = self.thread_list.item(row)
            if current_item is not None:
                self.thread_list.scrollToItem(current_item)
            if reactivate_if_same:
                self._activate_current_thread()
            return
        self.thread_list.setCurrentRow(row)
        current_item = self.thread_list.currentItem()
        if current_item is not None:
            self.thread_list.scrollToItem(current_item)

    def _refresh_threads(self, selected_key=None):
        model = self._current_model()
        current_row = self.thread_list.currentRow()
        if selected_key is None:
            current_thread = self._current_thread()
            if current_thread is not None:
                selected_key = current_thread.key
        self.thread_list.blockSignals(True)
        self.thread_list.clear()
        self._thread_rows = []
        if model is not None:
            self._thread_rows = group_threads(self._state_for_model(model).entries)
            for thread in self._thread_rows:
                self.thread_list.addItem(thread_preview(thread))
        self.thread_list.blockSignals(False)
        if self._thread_rows:
            selected_row = None
            if selected_key is not None:
                for index, thread in enumerate(self._thread_rows):
                    if thread.key == selected_key or thread.key[:3] == selected_key:
                        selected_row = index
                        break
            if selected_row is None:
                if current_row >= 0:
                    selected_row = min(current_row, len(self._thread_rows) - 1)
                else:
                    selected_row = 0
            self._set_current_thread_row(selected_row)
        else:
            self._set_empty_detail_text("No annotated residues in the current model.")
        self._update_button_states()

    def _current_thread(self):
        row = self.thread_list.currentRow()
        if row < 0 or row >= len(self._thread_rows):
            return None
        return self._thread_rows[row]

    def _thread_index_for_residue(self, residue):
        if residue is None:
            return None
        residue_key = thread_key_for_residue(residue)
        for index, thread in enumerate(self._thread_rows):
            if thread.key[:3] == residue_key:
                return index
        return None

    def _preferred_thread_key(self):
        selected_residue = self._single_selected_residue()
        if selected_residue is not None:
            return thread_key_for_residue(selected_residue)
        current_thread = self._current_thread()
        if current_thread is not None:
            return current_thread.key
        return None

    def _sync_thread_to_single_selected_residue(self):
        residue = self._single_selected_residue()
        if residue is None or not self._thread_rows:
            return
        row = self._thread_index_for_residue(residue)
        if row is None or row == self.thread_list.currentRow():
            return
        self._set_current_thread_row(row)

    def _find_residue(self, model, key):
        chain_id, resno, ins_code, _comp_id = key
        for residue in safe_model_residues(model):
            if residue.chain_id == chain_id and residue.number == resno and (residue.insertion_code or "") == (ins_code or ""):
                return residue
        return None

    def _goto_residue_with_context(self, residue):
        atom_count = len(getattr(residue, "atoms", []) or [])
        if atom_count <= 2:
            context_zoom_factor = 0.18
        elif atom_count <= 5:
            context_zoom_factor = 0.28
        elif atom_count <= 12:
            context_zoom_factor = 0.45
        else:
            context_zoom_factor = 0.65
        run(self.session, f"select {residue.atomspec}")
        try:
            # First center the residue in the view, then pin CoFR to it, then
            # zoom out to reveal local context while keeping the residue central.
            run(self.session, f"view {residue.atomspec} pad 0.2")
            run(self.session, f"cofr {residue.atomspec}")
            run(self.session, f"zoom {context_zoom_factor}")
            run(self.session, f"cofr {residue.atomspec}")
        except Exception:
            run(self.session, f"view {residue.atomspec}")

    def _goto_thread(self, thread):
        model = self._current_model()
        if model is None or thread is None:
            return
        residue = self._find_residue(model, thread.key)
        if residue is None:
            return
        self._goto_residue_with_context(residue)

    def _activate_current_thread(self):
        thread = self._current_thread()
        if thread is None:
            self._set_empty_detail_text("Select an annotated residue to view notes.")
            self._update_button_states()
            return
        self.detail_text.setPlainText(thread_detail_text(thread))
        self._update_button_states()
        self._goto_thread(thread)

    def _on_thread_changed(self, row):
        self._update_active_residue_label()
        self._activate_current_thread()

    def _on_thread_clicked(self, *_args):
        self._update_active_residue_label()
        self._activate_current_thread()

    def _goto_previous_thread(self):
        if not self._thread_rows:
            return
        current_row = self.thread_list.currentRow()
        row = current_row
        if row <= 0:
            row = len(self._thread_rows) - 1
        else:
            row -= 1
        if row == current_row:
            self._activate_current_thread()
        else:
            self._set_current_thread_row(row)

    def _goto_next_thread(self):
        if not self._thread_rows:
            return
        current_row = self.thread_list.currentRow()
        row = current_row
        if row < 0 or row >= len(self._thread_rows) - 1:
            row = 0
        else:
            row += 1
        if row == current_row:
            self._activate_current_thread()
        else:
            self._set_current_thread_row(row)

    def _selected_residue_entry_template(self):
        _label_prefix, residue = self._residue_target()
        if residue is None:
            QMessageBox.information(
                self.tool_window.ui_area,
                "Residue Notes",
                "Select a single residue, or place the center of rotation near the residue you want to annotate.",
            )
            return None
        return {
            "auth_asym_id": residue.chain_id,
            "auth_seq_id": int(residue.number),
            "pdbx_PDB_ins_code": residue.insertion_code or "",
            "label_comp_id": residue.name or "?",
        }

    def _prompt_for_note(self, initial_author="", initial_note=""):
        author, author_ok = QInputDialog.getText(
            self.tool_window.ui_area,
            "Residue Notes",
            "Author:",
            text=initial_author or self._session_author,
        )
        if not author_ok:
            return None
        note, note_ok = QInputDialog.getMultiLineText(
            self.tool_window.ui_area,
            "Residue Notes",
            "Note:",
            initial_note,
        )
        if not note_ok:
            return None
        normalized = normalize_entry(
            {
                "id": 1,
                "auth_asym_id": "A",
                "auth_seq_id": 1,
                "pdbx_PDB_ins_code": "",
                "label_comp_id": "UNK",
                "author": author,
                "modified_utc": now_utc(),
                "note": note,
            },
            fallback_id=1,
        )
        if normalized is None:
            QMessageBox.information(self.tool_window.ui_area, "Residue Notes", "Please enter a non-empty note.")
            return None
        self._session_author = normalized["author"]
        return normalized["author"], normalized["note"]

    def _add_note_for_selected_residue(self):
        model = self._current_model()
        template = self._selected_residue_entry_template()
        if model is None or template is None:
            return
        prompted = self._prompt_for_note()
        if prompted is None:
            return
        author, note = prompted
        new_entry = normalize_entry(
            {
                "id": next_note_id(self._state_for_model(model).entries),
                "auth_asym_id": template["auth_asym_id"],
                "auth_seq_id": template["auth_seq_id"],
                "pdbx_PDB_ins_code": template["pdbx_PDB_ins_code"],
                "label_comp_id": template["label_comp_id"],
                "author": author,
                "modified_utc": now_utc(),
                "note": note,
            }
        )
        if new_entry is None:
            return
        self._state_for_model(model).entries.append(new_entry)
        self._refresh_threads(selected_key=note_thread_key(new_entry))
        self._set_status(
            "Added note for {0}:{1}{2} {3}".format(
                new_entry["auth_asym_id"],
                new_entry["auth_seq_id"],
                new_entry.get("pdbx_PDB_ins_code", ""),
                new_entry.get("label_comp_id", "?"),
            )
        )

    def _choose_note_entry(self, thread, title):
        if thread is None:
            return None
        if len(thread.entries) == 1:
            return thread.entries[0]
        labels = [
            f"Note {index + 1} - {entry.get('author') or 'Unknown'} - {entry.get('modified_utc') or 'Unknown'}"
            for index, entry in enumerate(thread.entries)
        ]
        chosen, ok = QInputDialog.getItem(
            self.tool_window.ui_area,
            title,
            "Choose note:",
            labels,
            0,
            False,
        )
        if not ok:
            return None
        return thread.entries[labels.index(chosen)]

    def _edit_selected_note(self):
        model = self._current_model()
        thread = self._current_thread()
        if model is None or thread is None:
            return
        entry = self._choose_note_entry(thread, "Edit Note")
        if entry is None:
            return
        prompted = self._prompt_for_note(entry.get("author", ""), entry.get("note", ""))
        if prompted is None:
            return
        author, note = prompted
        entry["author"] = author
        entry["note"] = note
        entry["modified_utc"] = now_utc()
        self._refresh_threads(selected_key=thread.key)
        self._set_status(f"Edited note for {thread.label}")

    def _delete_selected_note(self):
        model = self._current_model()
        thread = self._current_thread()
        if model is None or thread is None:
            return
        entry = self._choose_note_entry(thread, "Delete Note")
        if entry is None:
            return
        reply = QMessageBox.question(
            self.tool_window.ui_area,
            "Delete Note",
            "Delete the selected note?",
        )
        if reply != QMessageBox.Yes:
            return
        state = self._state_for_model(model)
        state.entries = [candidate for candidate in state.entries if candidate.get("id") != entry.get("id")]
        self._refresh_threads(selected_key=thread.key)
        self._set_status(f"Deleted note from {thread.label}")

    def _import_entries(self, model, file_path, *, interactive):
        file_path = self._normalize_path(file_path)
        try:
            entries = read_annotations(file_path)
        except Exception as error:
            if interactive:
                QMessageBox.critical(self.tool_window.ui_area, "Residue Notes", f"Failed to import notes:\n{error!r}")
                return None
            raise
        self._remember_io_path(file_path)
        state = self._state_for_model(model)
        state.entries = entries
        state.source_path = file_path
        state.loaded_from_source = True
        self._update_source_label()
        preferred_key = self._preferred_thread_key()
        self._refresh_threads(selected_key=preferred_key)
        file_name = os.path.basename(file_path)
        if entries:
            self._set_status(f"Imported {len(entries)} note{'s' if len(entries) != 1 else ''} from {file_name}")
        else:
            self._set_status(f"No embedded notes found in {file_name}")
        return len(entries)

    def import_entries_from_path(self, file_path, model=None):
        target_model = self._resolve_model(model)
        self._set_current_model(target_model)
        result = self._import_entries(target_model, file_path, interactive=False)
        return 0 if result is None else result

    def _import_from_model_source(self):
        try:
            model = self._resolve_model()
        except ValueError:
            return
        source_path = self._state_for_model(model).source_path
        if not source_path or not os.path.exists(source_path):
            QMessageBox.information(self.tool_window.ui_area, "Residue Notes", "The current model has no readable source file.")
            return
        self._import_entries(model, source_path, interactive=True)

    def _import_from_file(self):
        try:
            model = self._resolve_model()
        except ValueError:
            return
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self.tool_window.ui_area,
            "Import Residue Notes",
            self._default_import_dir(),
            "mmCIF files (*.cif *.mmcif);;All files (*)",
        )
        if not file_path:
            return
        self._import_entries(model, file_path, interactive=True)

    def _default_export_path(self, model):
        base_dir = self._default_import_dir()
        if not os.path.isdir(base_dir):
            base_dir = os.path.expanduser("~/Desktop")
        basename = self._export_basename(model)
        return os.path.join(base_dir, f"{basename}.annotated.cif")

    def _default_markdown_export_path(self, model):
        base_dir = self._default_import_dir()
        if not os.path.isdir(base_dir):
            base_dir = os.path.expanduser("~/Desktop")
        basename = self._export_basename(model)
        return os.path.join(base_dir, f"{basename}.annotations.md")

    def _export_basename(self, model):
        basename = os.path.splitext(os.path.basename(model.name or f"model_{model.id_string}"))[0]
        for suffix in (
            ".annotated_chimerax",
            ".annotated",
            ".annotations",
            "_annotated_chimerax",
            "_annotated",
            "_annotations",
            "-annotated-chimerax",
            "-annotated",
            "-annotations",
        ):
            if basename.lower().endswith(suffix.lower()):
                basename = basename[: -len(suffix)]
                break
        return basename or f"model_{model.id_string}"

    def _export_entries(self, model, file_path, *, interactive, overwrite):
        file_path = self._normalize_path(file_path)
        if os.path.exists(file_path) and not overwrite:
            if interactive:
                reply = QMessageBox.question(
                    self.tool_window.ui_area,
                    "Overwrite File",
                    f"Overwrite existing file?\n{file_path}",
                )
                if reply != QMessageBox.Yes:
                    return None
            else:
                raise FileExistsError(file_path)
        state = self._state_for_model(model)
        try:
            run(
                self.session,
                "save {0} format mmcif models #{1}".format(
                    json.dumps(file_path),
                    model.id_string,
                ),
            )
            write_annotations(file_path, file_path, state.entries)
        except Exception as error:
            if interactive:
                QMessageBox.critical(self.tool_window.ui_area, "Residue Notes", f"Failed to export annotated mmCIF:\n{error!r}")
                return None
            raise
        self._remember_io_path(file_path)
        self._set_status(
            "Exported {0} note{1} to {2}".format(
                len(state.entries),
                "" if len(state.entries) == 1 else "s",
                os.path.basename(file_path),
            )
        )
        if interactive:
            QMessageBox.information(self.tool_window.ui_area, "Residue Notes", f"Exported annotated mmCIF:\n{file_path}")
        return len(state.entries)

    def export_entries_to_path(self, file_path, model=None, overwrite=False):
        target_model = self._resolve_model(model)
        self._set_current_model(target_model)
        result = self._export_entries(target_model, file_path, interactive=False, overwrite=overwrite)
        return 0 if result is None else result

    def _export_markdown_entries(self, model, file_path, *, interactive, overwrite):
        file_path = self._normalize_path(file_path)
        if os.path.exists(file_path) and not overwrite:
            if interactive:
                reply = QMessageBox.question(
                    self.tool_window.ui_area,
                    "Overwrite File",
                    f"Overwrite existing file?\n{file_path}",
                )
                if reply != QMessageBox.Yes:
                    return None
            else:
                raise FileExistsError(file_path)
        state = self._state_for_model(model)
        try:
            write_markdown_table(file_path, state.entries)
        except Exception as error:
            if interactive:
                QMessageBox.critical(self.tool_window.ui_area, "Residue Notes", f"Failed to export annotation Markdown:\n{error!r}")
                return None
            raise
        self._remember_io_path(file_path)
        self._set_status(
            "Exported {0} note{1} as Markdown to {2}".format(
                len(state.entries),
                "" if len(state.entries) == 1 else "s",
                os.path.basename(file_path),
            )
        )
        if interactive:
            QMessageBox.information(self.tool_window.ui_area, "Residue Notes", f"Exported annotation Markdown:\n{file_path}")
        return len(state.entries)

    def export_markdown_to_path(self, file_path, model=None, overwrite=False):
        target_model = self._resolve_model(model)
        self._set_current_model(target_model)
        result = self._export_markdown_entries(target_model, file_path, interactive=False, overwrite=overwrite)
        return 0 if result is None else result

    def refresh_tool_state(self, model=None):
        if model is not None:
            self._set_current_model(self._resolve_model(model))
        self._refresh_models()

    def _export_to_file(self):
        try:
            model = self._resolve_model()
        except ValueError:
            return
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self.tool_window.ui_area,
            "Export Annotated mmCIF",
            self._default_export_path(model),
            "mmCIF files (*.cif *.mmcif);;All files (*)",
        )
        if not file_path:
            return
        self._export_entries(model, file_path, interactive=True, overwrite=False)

    def _export_markdown_to_file(self):
        try:
            model = self._resolve_model()
        except ValueError:
            return
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self.tool_window.ui_area,
            "Export Annotation Markdown",
            self._default_markdown_export_path(model),
            "Markdown files (*.md);;Text files (*.txt);;All files (*)",
        )
        if not file_path:
            return
        self._export_markdown_entries(model, file_path, interactive=True, overwrite=False)
