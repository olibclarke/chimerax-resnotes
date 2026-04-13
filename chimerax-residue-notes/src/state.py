from dataclasses import dataclass, field


@dataclass
class ModelNoteState:
    entries: list = field(default_factory=list)
    source_path: str | None = None
    loaded_from_source: bool = False


@dataclass
class ResidueNoteThread:
    key: tuple
    label: str
    entries: list


def _text_or_empty(value):
    if value in (None, ".", "?"):
        return ""
    return str(value)


def _safe_int(value, default=None):
    try:
        return int(_text_or_empty(value).strip())
    except Exception:
        return default


def _normalized_label_seq_id(value):
    return _text_or_empty(value).strip()


def _canonical_identifier_key(
    label_asym_id,
    label_seq_id,
    auth_asym_id,
    auth_seq_id,
    pdbx_pdb_ins_code,
    label_comp_id,
):
    return (
        _text_or_empty(label_asym_id).strip(),
        _normalized_label_seq_id(label_seq_id),
        _text_or_empty(auth_asym_id).strip(),
        _safe_int(auth_seq_id, default=None),
        _text_or_empty(pdbx_pdb_ins_code).strip(),
        _text_or_empty(label_comp_id).strip() or "?",
    )


def note_thread_key(entry):
    return _canonical_identifier_key(
        entry.get("label_asym_id"),
        entry.get("label_seq_id"),
        entry.get("auth_asym_id"),
        entry.get("auth_seq_id"),
        entry.get("pdbx_PDB_ins_code"),
        entry.get("label_comp_id"),
    )


def _residue_label_from_entry(entry):
    chain_id = _text_or_empty(entry.get("auth_asym_id")) or _text_or_empty(entry.get("label_asym_id")) or "?"
    seq_id = _text_or_empty(entry.get("auth_seq_id")) or _text_or_empty(entry.get("label_seq_id")) or "?"
    ins_code = _text_or_empty(entry.get("pdbx_PDB_ins_code"))
    comp_id = _text_or_empty(entry.get("label_comp_id")) or "?"
    return f"{chain_id}:{seq_id}{ins_code} {comp_id}"


def group_threads(entries):
    grouped = {}
    for entry in entries:
        grouped.setdefault(note_thread_key(entry), []).append(entry)
    threads = []
    for key, thread_entries in grouped.items():
        sorted_entries = sorted(
            thread_entries,
            key=lambda item: (item.get("modified_utc", ""), item.get("id", 0)),
        )
        threads.append(
            ResidueNoteThread(
                key=key,
                label=_residue_label_from_entry(sorted_entries[0]),
                entries=sorted_entries,
            )
        )
    threads.sort(
        key=lambda item: (
            item.key[2] or item.key[0],
            item.key[3] if item.key[3] is not None else float("inf"),
            item.key[4],
            item.key[5],
            item.entries[-1]["id"],
        )
    )
    return threads


def next_note_id(entries):
    return max([int(entry.get("id", 0)) for entry in entries] + [0]) + 1


def explicit_entry_title(entry):
    return (entry.get("title") or "").strip()


def entry_display_title(entry, fallback_from_note=True, max_length=None):
    title = explicit_entry_title(entry)
    if not title and fallback_from_note:
        note_lines = [line.strip() for line in (entry.get("note") or "").splitlines() if line.strip()]
        if note_lines:
            title = note_lines[0]
    if not title:
        title = "Untitled note"
    if max_length is not None and len(title) > max_length:
        title = title[: max_length - 1].rstrip() + "..."
    return title


def thread_preview(thread, max_preview=56):
    note_count = len(thread.entries)
    preview = entry_display_title(thread.entries[-1], fallback_from_note=True, max_length=max_preview)
    suffix = "note" if note_count == 1 else "notes"
    if preview:
        return f"{thread.label} ({note_count} {suffix}) - {preview}"
    return f"{thread.label} ({note_count} {suffix})"
