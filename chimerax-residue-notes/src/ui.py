import html
from dataclasses import dataclass

from Qt.QtCore import Qt
from Qt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


@dataclass
class ResidueNotesWidgets:
    container: QWidget
    model_combo: QComboBox
    refresh_models_button: QPushButton
    source_label: QLabel
    active_residue_label: QLabel
    status_label: QLabel
    import_auto_button: QPushButton
    import_file_button: QPushButton
    export_file_button: QPushButton
    export_markdown_button: QPushButton
    add_button: QPushButton
    edit_button: QPushButton
    delete_button: QPushButton
    thread_list: QListWidget
    detail_scroll: QScrollArea
    detail_container: QWidget
    detail_layout: QVBoxLayout
    expand_all_button: QPushButton
    collapse_all_button: QPushButton
    prev_button: QPushButton
    next_button: QPushButton


class NoteEditDialog(QDialog):
    def __init__(self, parent=None, *, initial_title="", initial_author="", initial_note=""):
        super().__init__(parent)
        self.setWindowTitle("Residue Note")
        self.resize(560, 420)

        root = QVBoxLayout()
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        self.setLayout(root)

        form = QFormLayout()
        form.setSpacing(8)
        root.addLayout(form)

        self.title_edit = QLineEdit(initial_title)
        self.title_edit.setPlaceholderText("Optional short title")
        form.addRow("Title:", self.title_edit)

        self.author_edit = QLineEdit(initial_author)
        form.addRow("Author:", self.author_edit)

        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlainText(initial_note)
        self.note_edit.setMinimumHeight(220)
        form.addRow("Note:", self.note_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.note_edit.setFocus()

    def values(self):
        return (
            self.title_edit.text(),
            self.author_edit.text(),
            self.note_edit.toPlainText(),
        )


def prompt_for_note_fields(parent=None, *, initial_title="", initial_author="", initial_note=""):
    dialog = NoteEditDialog(
        parent,
        initial_title=initial_title,
        initial_author=initial_author,
        initial_note=initial_note,
    )
    exec_method = getattr(dialog, "exec", None) or getattr(dialog, "exec_", None)
    if exec_method is None or exec_method() != QDialog.Accepted:
        return None
    return dialog.values()


class CollapsibleNoteCard(QFrame):
    def __init__(
        self,
        header_text,
        *,
        author_text="Unknown",
        timestamp_text="Unknown",
        note_text="",
        expanded=False,
        toggled_callback=None,
        parent=None,
    ):
        super().__init__(parent)
        self._toggled_callback = toggled_callback
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("noteCard")
        self.setStyleSheet(
            "#noteCard { border: 1px solid palette(mid); border-radius: 4px; }"
        )

        root = QVBoxLayout()
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)
        self.setLayout(root)

        self.toggle_button = QToolButton(self)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setText(header_text)
        self.toggle_button.setStyleSheet("font-weight: 600; text-align: left;")
        self.toggle_button.toggled.connect(self._on_toggled)
        root.addWidget(self.toggle_button)

        self.body_widget = QWidget(self)
        body_layout = QVBoxLayout()
        body_layout.setContentsMargins(8, 0, 4, 2)
        body_layout.setSpacing(4)
        self.body_widget.setLayout(body_layout)
        root.addWidget(self.body_widget)

        author_label = QLabel(f"<b>Author:</b> {html.escape(author_text or 'Unknown')}")
        author_label.setTextFormat(Qt.RichText)
        author_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        body_layout.addWidget(author_label)

        timestamp_label = QLabel(f"<b>Timestamp:</b> {html.escape(timestamp_text or 'Unknown')}")
        timestamp_label.setTextFormat(Qt.RichText)
        timestamp_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        body_layout.addWidget(timestamp_label)

        note_label = QLabel(self._note_html(note_text))
        note_label.setTextFormat(Qt.RichText)
        note_label.setWordWrap(True)
        note_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        body_layout.addWidget(note_label)

        self._on_toggled(expanded)

    @staticmethod
    def _note_html(note_text):
        text = (note_text or "").rstrip()
        if not text:
            return "<i>(empty)</i>"
        return html.escape(text).replace("\n", "<br>")

    def _on_toggled(self, checked):
        self.body_widget.setVisible(bool(checked))
        self.toggle_button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        if self._toggled_callback is not None:
            self._toggled_callback(bool(checked))


def build_residue_notes_ui(parent, callbacks):
    container = QWidget(parent)
    root = QVBoxLayout()
    root.setContentsMargins(6, 6, 6, 6)
    root.setSpacing(8)
    container.setLayout(root)

    model_row = QHBoxLayout()
    model_row.setSpacing(8)
    model_row.addWidget(QLabel("Model:"))
    model_combo = QComboBox()
    model_combo.currentIndexChanged.connect(callbacks["on_model_changed"])
    model_row.addWidget(model_combo, 1)
    refresh_models_button = QPushButton("Refresh models")
    refresh_models_button.clicked.connect(callbacks["refresh_models"])
    model_row.addWidget(refresh_models_button)
    root.addLayout(model_row)

    source_label = QLabel("Source: unknown")
    active_residue_label = QLabel("Selected residue: none")
    status_label = QLabel("Status: ready")
    root.addWidget(source_label)
    root.addWidget(active_residue_label)
    root.addWidget(status_label)

    import_export_row = QHBoxLayout()
    import_export_row.setSpacing(8)
    import_auto_button = QPushButton("Import embedded")
    import_auto_button.clicked.connect(callbacks["import_model_source"])
    import_export_row.addWidget(import_auto_button)
    import_file_button = QPushButton("Import from file...")
    import_file_button.clicked.connect(callbacks["import_file"])
    import_export_row.addWidget(import_file_button)
    export_file_button = QPushButton("Export annotated mmCIF...")
    export_file_button.clicked.connect(callbacks["export_file"])
    import_export_row.addWidget(export_file_button)
    export_markdown_button = QPushButton("Export Markdown...")
    export_markdown_button.clicked.connect(callbacks["export_markdown"])
    import_export_row.addWidget(export_markdown_button)
    root.addLayout(import_export_row)

    note_row = QHBoxLayout()
    note_row.setSpacing(8)
    add_button = QPushButton("Add note")
    add_button.clicked.connect(callbacks["add_note"])
    note_row.addWidget(add_button)
    edit_button = QPushButton("Edit note")
    edit_button.clicked.connect(callbacks["edit_note"])
    note_row.addWidget(edit_button)
    delete_button = QPushButton("Delete note")
    delete_button.clicked.connect(callbacks["delete_note"])
    note_row.addWidget(delete_button)
    root.addLayout(note_row)

    thread_list = QListWidget()
    thread_list.setAlternatingRowColors(True)
    thread_list.setUniformItemSizes(True)
    thread_list.setMinimumWidth(180)
    thread_list.currentRowChanged.connect(callbacks["thread_changed"])
    thread_list.itemClicked.connect(callbacks["thread_clicked"])

    thread_label = QLabel("Annotated residues")
    thread_label.setStyleSheet("font-weight: 600;")
    thread_panel = QWidget()
    thread_layout = QVBoxLayout()
    thread_layout.setContentsMargins(0, 0, 0, 0)
    thread_layout.setSpacing(4)
    thread_panel.setLayout(thread_layout)
    thread_layout.addWidget(thread_label)
    thread_layout.addWidget(thread_list, 1)

    detail_scroll = QScrollArea()
    detail_scroll.setWidgetResizable(True)
    detail_scroll.setMinimumWidth(240)
    detail_container = QWidget()
    detail_layout = QVBoxLayout()
    detail_layout.setContentsMargins(0, 0, 0, 0)
    detail_layout.setSpacing(8)
    detail_container.setLayout(detail_layout)
    detail_scroll.setWidget(detail_container)
    detail_label = QLabel("Notes")
    detail_label.setStyleSheet("font-weight: 600;")
    detail_header_row = QHBoxLayout()
    detail_header_row.setSpacing(6)
    detail_header_row.addWidget(detail_label)
    detail_header_row.addStretch(1)
    expand_all_button = QPushButton("Expand all")
    expand_all_button.clicked.connect(callbacks["expand_all_notes"])
    detail_header_row.addWidget(expand_all_button)
    collapse_all_button = QPushButton("Collapse all")
    collapse_all_button.clicked.connect(callbacks["collapse_all_notes"])
    detail_header_row.addWidget(collapse_all_button)
    detail_panel = QWidget()
    detail_panel_layout = QVBoxLayout()
    detail_panel_layout.setContentsMargins(0, 0, 0, 0)
    detail_panel_layout.setSpacing(4)
    detail_panel.setLayout(detail_panel_layout)
    detail_panel_layout.addLayout(detail_header_row)
    detail_panel_layout.addWidget(detail_scroll, 1)

    body_splitter = QSplitter(Qt.Horizontal)
    body_splitter.addWidget(thread_panel)
    body_splitter.addWidget(detail_panel)
    body_splitter.setStretchFactor(0, 0)
    body_splitter.setStretchFactor(1, 1)
    body_splitter.setChildrenCollapsible(False)
    body_splitter.setSizes([220, 320])
    root.addWidget(body_splitter, 1)

    nav_row = QHBoxLayout()
    nav_row.setSpacing(8)
    prev_button = QPushButton("<-- Prev")
    prev_button.clicked.connect(callbacks["previous_thread"])
    nav_row.addWidget(prev_button)
    next_button = QPushButton("Next -->")
    next_button.clicked.connect(callbacks["next_thread"])
    nav_row.addWidget(next_button)
    root.addLayout(nav_row)

    parent.setLayout(QVBoxLayout())
    parent.layout().addWidget(container)

    return ResidueNotesWidgets(
        container=container,
        model_combo=model_combo,
        refresh_models_button=refresh_models_button,
        source_label=source_label,
        active_residue_label=active_residue_label,
        status_label=status_label,
        import_auto_button=import_auto_button,
        import_file_button=import_file_button,
        export_file_button=export_file_button,
        export_markdown_button=export_markdown_button,
        add_button=add_button,
        edit_button=edit_button,
        delete_button=delete_button,
        thread_list=thread_list,
        detail_scroll=detail_scroll,
        detail_container=detail_container,
        detail_layout=detail_container.layout(),
        expand_all_button=expand_all_button,
        collapse_all_button=collapse_all_button,
        prev_button=prev_button,
        next_button=next_button,
    )
