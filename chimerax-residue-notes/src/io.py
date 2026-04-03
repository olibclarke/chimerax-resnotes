import base64
import os
import shlex
import tempfile
from datetime import datetime, timezone


CATEGORY_PREFIX = "_cootnote_residue_note."
ROW_TAGS = [
    "id",
    "auth_asym_id",
    "auth_seq_id",
    "pdbx_PDB_ins_code",
    "label_comp_id",
    "author_b64",
    "modified_utc",
    "note_b64",
]
FULL_TAGS = [CATEGORY_PREFIX + tag for tag in ROW_TAGS]


def default_author():
    return os.environ.get("USER", "").strip() or "unknown"


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def text_or_empty(value):
    if value in (None, ".", "?"):
        return ""
    return str(value)


def encode_text(value):
    return base64.b64encode(text_or_empty(value).encode("utf-8")).decode("ascii")


def decode_text(value):
    text = text_or_empty(value)
    if not text:
        return ""
    try:
        return base64.b64decode(text.encode("ascii")).decode("utf-8")
    except Exception:
        return text


def normalize_entry(raw_entry, fallback_id=None):
    try:
        entry_id = int(text_or_empty(raw_entry.get("id")) or fallback_id)
        auth_asym_id = text_or_empty(raw_entry.get("auth_asym_id")).strip()
        auth_seq_id = int(text_or_empty(raw_entry.get("auth_seq_id")).strip())
    except Exception:
        return None
    if not auth_asym_id:
        return None
    note_text = text_or_empty(raw_entry.get("note")).strip()
    if not note_text:
        return None
    return {
        "id": entry_id,
        "auth_asym_id": auth_asym_id,
        "auth_seq_id": auth_seq_id,
        "pdbx_PDB_ins_code": text_or_empty(raw_entry.get("pdbx_PDB_ins_code")).strip(),
        "label_comp_id": text_or_empty(raw_entry.get("label_comp_id")).strip() or "?",
        "author": text_or_empty(raw_entry.get("author")).strip() or default_author(),
        "modified_utc": text_or_empty(raw_entry.get("modified_utc")).strip() or now_utc(),
        "note": note_text,
    }


def _tokenize_mmcif_lines(lines):
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        if line.startswith(";"):
            multiline_lines = [line[1:].rstrip("\n")]
            index += 1
            while index < len(lines) and not lines[index].startswith(";"):
                multiline_lines.append(lines[index].rstrip("\n"))
                index += 1
            if index < len(lines):
                index += 1
            yield "\n".join(multiline_lines)
            continue
        for token in shlex.split(line, comments=False, posix=True):
            yield token
        index += 1


def _annotation_loop_bounds(lines):
    index = 0
    while index < len(lines):
        if lines[index].strip() != "loop_":
            index += 1
            continue
        loop_start = index
        index += 1
        tags = []
        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped or stripped.startswith("#"):
                index += 1
                continue
            if stripped.startswith("_"):
                tags.extend(token for token in stripped.split() if token.startswith("_"))
                index += 1
                continue
            break
        if tags and all(tag.startswith(CATEGORY_PREFIX) for tag in tags):
            data_start = index
            loop_end = index
            while loop_end < len(lines):
                stripped = lines[loop_end].strip()
                if stripped.startswith(("loop_", "_", "data_", "save_")):
                    break
                loop_end += 1
            return loop_start, data_start, loop_end, tags
    return None


def read_annotations(path):
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()
    loop_info = _annotation_loop_bounds(lines)
    if loop_info is None:
        return []
    _loop_start, data_start, _loop_end, tags = loop_info
    data_lines = lines[data_start:_loop_end]
    tokens = list(_tokenize_mmcif_lines(data_lines))
    if not tags:
        return []
    row_width = len(tags)
    entries = []
    for row_index in range(0, len(tokens), row_width):
        row_tokens = tokens[row_index:row_index + row_width]
        if len(row_tokens) < row_width:
            break
        row_map = dict(zip(tags, row_tokens))
        normalized = normalize_entry(
            {
                "id": row_map.get(CATEGORY_PREFIX + "id"),
                "auth_asym_id": row_map.get(CATEGORY_PREFIX + "auth_asym_id"),
                "auth_seq_id": row_map.get(CATEGORY_PREFIX + "auth_seq_id"),
                "pdbx_PDB_ins_code": row_map.get(CATEGORY_PREFIX + "pdbx_PDB_ins_code"),
                "label_comp_id": row_map.get(CATEGORY_PREFIX + "label_comp_id"),
                "author": decode_text(row_map.get(CATEGORY_PREFIX + "author_b64")),
                "modified_utc": row_map.get(CATEGORY_PREFIX + "modified_utc"),
                "note": decode_text(row_map.get(CATEGORY_PREFIX + "note_b64")),
            },
            fallback_id=(row_index // row_width) + 1,
        )
        if normalized is not None:
            entries.append(normalized)
    return entries


def _strip_existing_annotation_loop(text):
    lines = text.splitlines(keepends=True)
    loop_info = _annotation_loop_bounds(lines)
    if loop_info is None:
        return text
    loop_start, _data_start, loop_end, _tags = loop_info
    return "".join(lines[:loop_start] + lines[loop_end:])


def _annotation_loop_text(entries):
    if not entries:
        return ""
    rows = []
    for entry in sorted(entries, key=lambda item: (item.get("auth_asym_id", ""), item.get("auth_seq_id", 0), item.get("id", 0))):
        rows.append(
            "{0} {1} {2} {3} {4} {5} {6} {7}".format(
                text_or_empty(entry.get("id")) or "?",
                text_or_empty(entry.get("auth_asym_id")) or "?",
                text_or_empty(entry.get("auth_seq_id")) or "?",
                text_or_empty(entry.get("pdbx_PDB_ins_code")) or "?",
                text_or_empty(entry.get("label_comp_id")) or "?",
                encode_text(entry.get("author")),
                text_or_empty(entry.get("modified_utc")) or "?",
                encode_text(entry.get("note")),
            )
        )
    loop_lines = ["\n#\n", "loop_\n"]
    for tag in FULL_TAGS:
        loop_lines.append(tag + "\n")
    for row in rows:
        loop_lines.append(row + "\n")
    loop_lines.append("#\n")
    return "".join(loop_lines)


def _atomic_write_text(output_path, text):
    output_dir = os.path.dirname(os.path.abspath(output_path)) or "."
    output_suffix = os.path.splitext(output_path)[1] or ".cif"
    temp_handle, temp_path = tempfile.mkstemp(
        prefix=".resnotes_",
        suffix=output_suffix,
        dir=output_dir,
        text=True,
    )
    try:
        with os.fdopen(temp_handle, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp_path, output_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def write_annotations(input_path, output_path, entries):
    with open(input_path, "r", encoding="utf-8") as handle:
        original_text = handle.read()
    stripped_text = _strip_existing_annotation_loop(original_text).rstrip() + "\n"
    updated_text = stripped_text + _annotation_loop_text(entries)
    _atomic_write_text(output_path, updated_text)


def _markdown_cell(value):
    text = text_or_empty(value).replace("|", "\\|").replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", "<br>")


def _markdown_residue_label(entry):
    return "{0}:{1}{2} {3}".format(
        text_or_empty(entry.get("auth_asym_id")) or "?",
        text_or_empty(entry.get("auth_seq_id")) or "?",
        text_or_empty(entry.get("pdbx_PDB_ins_code")) or "",
        text_or_empty(entry.get("label_comp_id")) or "?",
    )


def markdown_table_text(entries):
    lines = [
        "| Residue | Author | Timestamp | Note |",
        "| --- | --- | --- | --- |",
    ]
    for entry in sorted(entries, key=lambda item: (item.get("auth_asym_id", ""), item.get("auth_seq_id", 0), item.get("pdbx_PDB_ins_code", ""), item.get("id", 0))):
        lines.append(
            "| {0} | {1} | {2} | {3} |".format(
                _markdown_cell(_markdown_residue_label(entry)),
                _markdown_cell(entry.get("author")) or "Unknown",
                _markdown_cell(entry.get("modified_utc")) or "",
                _markdown_cell(entry.get("note")) or "",
            )
        )
    return "\n".join(lines) + "\n"


def write_markdown_table(output_path, entries):
    _atomic_write_text(output_path, markdown_table_text(entries))
