# ChimeraX Residue Notes

Prototype ChimeraX bundle for reading and writing custom
`_cootnote_residue_note.*` [mmCIF annotations written by `coot1-trimmings`](https://github.com/olibclarke/coot1-trimmings/).

Current functionality:
- open a `Residue Notes` (or `Nearby Notes`) tool window
- auto-import embedded notes from an mmCIF file when possible
- browse annotated residues and jump to them in ChimeraX
- add, edit, and delete notes
- follow the current single selected residue, or fall back to the residue closest to CoFR
- export an annotated mmCIF and/or
- export the current note set as a plain Markdown table

Notes:
- this bundle stores notes in the same UTF-8 plaintext format as coot1_trimmings:
- `_cootnote_residue_note.id`
- `_cootnote_residue_note.label_comp_id`
- `_cootnote_residue_note.label_asym_id`
- `_cootnote_residue_note.label_seq_id`
- `_cootnote_residue_note.auth_asym_id`
- `_cootnote_residue_note.auth_seq_id`
- `_cootnote_residue_note.pdbx_PDB_ins_code`
- `_cootnote_residue_note.title`
- `_cootnote_residue_note.author`
- `_cootnote_residue_note.modified_utc`
- `_cootnote_residue_note.note` (contains the body of the note)

## Install
Download the bundle (whole `chimerax-residue-notes` folder), then:

In ChimeraX:

```chimerax
devel install /my/path/to/chimerax-residue-notes
```

Then in ChimeraX, type `resnotes`, and the tool should appear. I've included an example cif file with some notes so you can see how it works:

![example screenshot](./example_resnotes.png)

There is also a separate tool part of this bundle, `nearby_notes`, which will show notes attached to residues within 6Å of the center of rotation.

## Caveats

- Testing limited to a few models so far - let me know if you encounter any bugs!
- Export is explicit via the tool; it does not attempt to modify ChimeraX's default save behavior.
- Prototype generated with the assistance of the Codex LLM.
