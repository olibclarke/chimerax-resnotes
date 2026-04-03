from dataclasses import dataclass

from Qt.QtCore import Qt
from Qt.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
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
    detail_text: QPlainTextEdit
    prev_button: QPushButton
    next_button: QPushButton


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
    thread_list.setMinimumWidth(280)
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

    detail_text = QPlainTextEdit()
    detail_text.setReadOnly(True)
    detail_text.setMinimumWidth(440)
    detail_text.setLineWrapMode(QPlainTextEdit.WidgetWidth)
    detail_label = QLabel("Notes")
    detail_label.setStyleSheet("font-weight: 600;")
    detail_panel = QWidget()
    detail_layout = QVBoxLayout()
    detail_layout.setContentsMargins(0, 0, 0, 0)
    detail_layout.setSpacing(4)
    detail_panel.setLayout(detail_layout)
    detail_layout.addWidget(detail_label)
    detail_layout.addWidget(detail_text, 1)

    body_splitter = QSplitter(Qt.Horizontal)
    body_splitter.addWidget(thread_panel)
    body_splitter.addWidget(detail_panel)
    body_splitter.setStretchFactor(0, 0)
    body_splitter.setStretchFactor(1, 1)
    body_splitter.setChildrenCollapsible(False)
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
        detail_text=detail_text,
        prev_button=prev_button,
        next_button=next_button,
    )
