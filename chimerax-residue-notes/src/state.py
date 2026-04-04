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


def note_thread_key(entry):
    return (
        entry["auth_asym_id"],
        int(entry["auth_seq_id"]),
        entry.get("pdbx_PDB_ins_code", ""),
        entry.get("label_comp_id", ""),
    )


def thread_key_for_residue(residue):
    if residue is None:
        return None
    return (
        residue.chain_id,
        int(residue.number),
        residue.insertion_code or "",
    )


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
        chain_id, resno, ins_code, comp_id = key
        threads.append(
            ResidueNoteThread(
                key=key,
                label=f"{chain_id}:{resno}{ins_code or ''} {comp_id}",
                entries=sorted_entries,
            )
        )
    threads.sort(key=lambda item: (item.key[0], item.key[1], item.key[2], item.entries[-1]["id"]))
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
