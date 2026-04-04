from dataclasses import dataclass
import math
import os

from Qt.QtCore import Qt
from Qt.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from chimerax.atomic import AtomicStructure, get_triggers as atomic_triggers
from chimerax.core.models import ADD_MODELS, MODEL_ID_CHANGED, MODEL_NAME_CHANGED, REMOVE_MODELS
from chimerax.core.tools import ToolInstance, get_singleton
from chimerax.ui import MainToolWindow

from .io import read_annotations
from .selection import cofr_key, distance_sq, find_residue_by_note_key, residue_center_xyz, selected_residues_for_model
from .state import ModelNoteState, entry_display_title, group_threads, thread_preview
from .ui import CollapsibleNoteCard


@dataclass
class NearbyThreadRow:
    thread: object
    residue: object
    distance: float


def show_nearby_notes_tool(session):
    return get_singleton(session, NearbyNotesTool, "Nearby Notes", create=True)


class NearbyNotesTool(ToolInstance):
    SESSION_ENDURING = False
    SESSION_SAVE = False
    help = "help:user/tools/residue_notes.html"

    def __init__(self, session, tool_name):
        super().__init__(session, tool_name)
        self._model_state = {}
        self._thread_rows = []
        self._expanded_note_ids_by_thread = {}
        self._trigger_handlers = []
        self._last_nearby_signature = None
        self._building_ui = False

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
        parent = self.tool_window.ui_area
        container = QWidget(parent)
        root = QVBoxLayout()
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)
        container.setLayout(root)

        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        model_row.addWidget(QLabel("Model:"))
        from Qt.QtWidgets import QComboBox

        self.model_combo = QComboBox()
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_row.addWidget(self.model_combo, 1)
        self.refresh_models_button = QPushButton("Refresh models")
        self.refresh_models_button.clicked.connect(self._refresh_models)
        model_row.addWidget(self.refresh_models_button)
        root.addLayout(model_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("Radius:"))
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(1.0, 50.0)
        self.radius_spin.setDecimals(1)
        self.radius_spin.setSingleStep(0.5)
        self.radius_spin.setSuffix(" A")
        self.radius_spin.setValue(6.0)
        self.radius_spin.setToolTip("Show annotated residues whose centers are within this radius of the current CoFR")
        self.radius_spin.valueChanged.connect(self._radius_changed)
        filter_row.addWidget(self.radius_spin)
        filter_row.addStretch(1)
        root.addLayout(filter_row)

        self.source_label = QLabel("Source: unknown")
        self.cofr_label = QLabel("CoFR: unavailable")
        self.status_label = QLabel("Status: ready")
        root.addWidget(self.source_label)
        root.addWidget(self.cofr_label)
        root.addWidget(self.status_label)

        self.thread_list = QListWidget()
        self.thread_list.setAlternatingRowColors(True)
        self.thread_list.setUniformItemSizes(True)
        self.thread_list.setMinimumWidth(180)
        self.thread_list.currentRowChanged.connect(self._on_thread_changed)

        thread_label = QLabel("Nearby annotated residues")
        thread_label.setStyleSheet("font-weight: 600;")
        thread_panel = QWidget()
        thread_layout = QVBoxLayout()
        thread_layout.setContentsMargins(0, 0, 0, 0)
        thread_layout.setSpacing(4)
        thread_panel.setLayout(thread_layout)
        thread_layout.addWidget(thread_label)
        thread_layout.addWidget(self.thread_list, 1)

        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setMinimumWidth(240)
        self.detail_container = QWidget()
        self.detail_layout = QVBoxLayout()
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_layout.setSpacing(8)
        self.detail_container.setLayout(self.detail_layout)
        self.detail_scroll.setWidget(self.detail_container)

        detail_label = QLabel("Nearby notes")
        detail_label.setStyleSheet("font-weight: 600;")
        detail_header_row = QHBoxLayout()
        detail_header_row.setSpacing(6)
        detail_header_row.addWidget(detail_label)
        detail_header_row.addStretch(1)
        self.expand_all_button = QPushButton("Expand all")
        self.expand_all_button.clicked.connect(self._expand_all_current_notes)
        detail_header_row.addWidget(self.expand_all_button)
        self.collapse_all_button = QPushButton("Collapse all")
        self.collapse_all_button.clicked.connect(self._collapse_all_current_notes)
        detail_header_row.addWidget(self.collapse_all_button)
        detail_panel = QWidget()
        detail_panel_layout = QVBoxLayout()
        detail_panel_layout.setContentsMargins(0, 0, 0, 0)
        detail_panel_layout.setSpacing(4)
        detail_panel.setLayout(detail_panel_layout)
        detail_panel_layout.addLayout(detail_header_row)
        detail_panel_layout.addWidget(self.detail_scroll, 1)

        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.addWidget(thread_panel)
        body_splitter.addWidget(detail_panel)
        body_splitter.setStretchFactor(0, 0)
        body_splitter.setStretchFactor(1, 1)
        body_splitter.setChildrenCollapsible(False)
        body_splitter.setSizes([220, 320])
        root.addWidget(body_splitter, 1)

        parent.setLayout(QVBoxLayout())
        parent.layout().addWidget(container)
        self._building_ui = False
        self._set_empty_detail_text("No nearby notes in the current model.")
        self._update_detail_button_states()

    def _install_triggers(self):
        self._trigger_handlers = [
            self.session.triggers.add_handler(ADD_MODELS, self._models_changed_cb),
            self.session.triggers.add_handler(REMOVE_MODELS, self._models_changed_cb),
            self.session.triggers.add_handler(MODEL_ID_CHANGED, self._models_changed_cb),
            self.session.triggers.add_handler(MODEL_NAME_CHANGED, self._models_changed_cb),
            self.session.triggers.add_handler("new frame", self._new_frame_cb),
            atomic_triggers().add_handler("changes done", self._atomic_changes_done_cb),
        ]

    def _atomic_models(self):
        return [model for model in self.session.models.list() if isinstance(model, AtomicStructure)]

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
        stale_thread_keys = [key for key in self._expanded_note_ids_by_thread if key[0] not in live_models]
        for key in stale_thread_keys:
            self._expanded_note_ids_by_thread.pop(key, None)

    def _set_status(self, message):
        self.status_label.setText(f"Status: {message}")

    def _clear_detail_layout(self):
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _set_empty_detail_text(self, message):
        self._clear_detail_layout()
        label = QLabel(message)
        label.setWordWrap(True)
        label.setStyleSheet("color: palette(mid); padding: 8px;")
        self.detail_layout.addWidget(label)
        self.detail_layout.addStretch(1)

    def _update_detail_button_states(self):
        has_thread = self._current_thread_row() is not None
        self.expand_all_button.setEnabled(has_thread)
        self.collapse_all_button.setEnabled(has_thread)

    def _thread_state_key(self, thread):
        model = self._current_model()
        if model is None or thread is None:
            return None
        return (model, thread.key)

    def _expanded_note_ids_for_thread(self, thread):
        state_key = self._thread_state_key(thread)
        if state_key is None:
            return set()
        expanded_ids = self._expanded_note_ids_by_thread.get(state_key)
        if expanded_ids is None:
            return {thread.entries[-1].get("id")} if thread.entries else set()
        return set(expanded_ids)

    def _set_note_expanded(self, thread, entry_id, expanded):
        state_key = self._thread_state_key(thread)
        if state_key is None:
            return
        expanded_ids = self._expanded_note_ids_by_thread.setdefault(state_key, set())
        if expanded:
            expanded_ids.add(entry_id)
        else:
            expanded_ids.discard(entry_id)

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
            self.session.logger.warning(f"Nearby Notes: failed to import embedded annotations from {source_path}: {error!r}")

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
            self.source_label.setText("Source: no associated file")

    def _update_cofr_label(self, xyz):
        if xyz is None:
            self.cofr_label.setText("CoFR: unavailable")
            return
        self.cofr_label.setText("CoFR: ({0:.2f}, {1:.2f}, {2:.2f})".format(*xyz))

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

    def _set_current_model(self, model):
        if model is None:
            return
        index = self.model_combo.findData(model)
        if index >= 0 and index != self.model_combo.currentIndex():
            self.model_combo.setCurrentIndex(index)

    def focus_model(self, model=None):
        if model is not None:
            self._set_current_model(model)
        self._refresh_nearby_threads(force=True)

    def _thread_row_preview(self, row):
        return f"{row.distance:.1f} A - {thread_preview(row.thread)}"

    def _current_thread_row(self):
        row = self.thread_list.currentRow()
        if row < 0 or row >= len(self._thread_rows):
            return None
        return self._thread_rows[row]

    def _set_current_thread_row(self, row):
        if row is None or row < 0 or row >= len(self._thread_rows):
            return
        self.thread_list.setCurrentRow(row)
        current_item = self.thread_list.currentItem()
        if current_item is not None:
            self.thread_list.scrollToItem(current_item)

    def _refresh_nearby_threads(self, *, force=False):
        model = self._current_model()
        if model is None:
            self.thread_list.clear()
            self._thread_rows = []
            self._update_source_label()
            self._update_cofr_label(None)
            self._set_empty_detail_text("No atomic model selected.")
            self._set_status("No atomic model selected")
            self._update_detail_button_states()
            return

        self._auto_import_if_possible(model)
        self._update_source_label()
        cofr_xyz_value, rounded_key = cofr_key(self.session)
        self._update_cofr_label(cofr_xyz_value)

        state = self._state_for_model(model)
        radius = float(self.radius_spin.value())
        signature = (model, rounded_key, round(radius, 2), len(state.entries))
        if not force and signature == self._last_nearby_signature:
            return
        self._last_nearby_signature = signature

        current_key = None
        current_row = self._current_thread_row()
        if current_row is not None:
            current_key = current_row.thread.key

        self.thread_list.blockSignals(True)
        self.thread_list.clear()
        self._thread_rows = []

        if cofr_xyz_value is not None:
            radius_sq = radius * radius
            for thread in group_threads(state.entries):
                residue = find_residue_by_note_key(model, thread.key)
                if residue is None:
                    continue
                residue_xyz = residue_center_xyz(residue)
                residue_distance_sq = distance_sq(residue_xyz, cofr_xyz_value)
                if residue_distance_sq is None or residue_distance_sq > radius_sq:
                    continue
                self._thread_rows.append(
                    NearbyThreadRow(
                        thread=thread,
                        residue=residue,
                        distance=math.sqrt(residue_distance_sq),
                    )
                )
            self._thread_rows.sort(key=lambda item: (item.distance, item.thread.key[0], item.thread.key[1], item.thread.key[2]))

        for row in self._thread_rows:
            self.thread_list.addItem(self._thread_row_preview(row))
        self.thread_list.blockSignals(False)

        if self._thread_rows:
            selected_index = 0
            if current_key is not None:
                for index, row in enumerate(self._thread_rows):
                    if row.thread.key == current_key:
                        selected_index = index
                        break
            self._set_current_thread_row(selected_index)
            self._set_status(
                "Showing {0} nearby annotated residue{1} within {2:.1f} A".format(
                    len(self._thread_rows),
                    "" if len(self._thread_rows) == 1 else "s",
                    radius,
                )
            )
        else:
            self._set_empty_detail_text(f"No nearby notes within {radius:.1f} A of CoFR.")
            self._set_status(f"No nearby notes within {radius:.1f} A of CoFR")
        self._update_detail_button_states()

    def _render_current_thread(self):
        row = self._current_thread_row()
        if row is None:
            self._set_empty_detail_text("Select a nearby note thread to view it.")
            self._update_detail_button_states()
            return
        thread = row.thread
        self._clear_detail_layout()

        header_label = QLabel(thread.label)
        header_label.setStyleSheet("font-weight: 700; font-size: 15px;")
        self.detail_layout.addWidget(header_label)

        subtitle_label = QLabel(
            "{0:.1f} A from CoFR - {1} note{2}".format(
                row.distance,
                len(thread.entries),
                "" if len(thread.entries) == 1 else "s",
            )
        )
        subtitle_label.setStyleSheet("color: palette(dark);")
        self.detail_layout.addWidget(subtitle_label)

        expanded_ids = self._expanded_note_ids_for_thread(thread)
        note_count = len(thread.entries)
        for index, entry in enumerate(thread.entries, start=1):
            title_text = entry_display_title(entry, fallback_from_note=True, max_length=96)
            card = CollapsibleNoteCard(
                f"Note {index} of {note_count} - {title_text}",
                author_text=entry.get("author") or "Unknown",
                timestamp_text=entry.get("modified_utc") or "Unknown",
                note_text=entry.get("note") or "",
                expanded=entry.get("id") in expanded_ids,
                toggled_callback=lambda checked, eid=entry.get("id"), current_thread=thread: self._set_note_expanded(current_thread, eid, checked),
            )
            self.detail_layout.addWidget(card)

        self.detail_layout.addStretch(1)
        self._update_detail_button_states()

    def _set_all_notes_expanded(self, expanded):
        row = self._current_thread_row()
        if row is None:
            return
        thread = row.thread
        state_key = self._thread_state_key(thread)
        if state_key is None:
            return
        if expanded:
            self._expanded_note_ids_by_thread[state_key] = {entry.get("id") for entry in thread.entries}
        else:
            self._expanded_note_ids_by_thread[state_key] = set()
        self._render_current_thread()

    def _expand_all_current_notes(self):
        self._set_all_notes_expanded(True)

    def _collapse_all_current_notes(self):
        self._set_all_notes_expanded(False)

    def _on_model_changed(self, *_args):
        if self._building_ui:
            return
        self._last_nearby_signature = None
        self._refresh_nearby_threads(force=True)

    def _on_thread_changed(self, *_args):
        self._render_current_thread()

    def _radius_changed(self, *_args):
        self._last_nearby_signature = None
        self._refresh_nearby_threads(force=True)

    def _models_changed_cb(self, *_args):
        self._last_nearby_signature = None
        self._refresh_models()

    def _atomic_changes_done_cb(self, *_args):
        self._last_nearby_signature = None
        self._refresh_nearby_threads(force=True)

    def _new_frame_cb(self, *_args):
        self._refresh_nearby_threads(force=False)
