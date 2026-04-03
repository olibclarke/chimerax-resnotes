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


def thread_preview(thread, max_preview=56):
    note_count = len(thread.entries)
    preview = thread.entries[-1]["note"].splitlines()[0].strip()
    if len(preview) > max_preview:
        preview = preview[: max_preview - 1].rstrip() + "..."
    suffix = "note" if note_count == 1 else "notes"
    if preview:
        return f"{thread.label} ({note_count} {suffix}) - {preview}"
    return f"{thread.label} ({note_count} {suffix})"


def _note_body_lines(note_text):
    lines = (note_text or "").splitlines()
    if not lines:
        return ["(empty)"]
    return lines


def thread_detail_text(thread):
    note_count = len(thread.entries)
    lines = [
        thread.label,
        f"{note_count} note{'s' if note_count != 1 else ''}",
        "=" * 48,
        "",
    ]
    for index, entry in enumerate(thread.entries, start=1):
        lines.append(f"Note {index} of {note_count}")
        lines.append(f"Author:    {entry.get('author') or 'Unknown'}")
        lines.append(f"Timestamp: {entry.get('modified_utc') or 'Unknown'}")
        lines.append("")
        lines.append("Text:")
        for body_line in _note_body_lines(entry.get("note")):
            lines.append(f"  {body_line}")
        if index != len(thread.entries):
            lines.extend(["", "-" * 40, ""])
    return "\n".join(lines)
