# ChimeraX Residue Notes

Version 0.2.6. Maintainer: Oliver Clarke <olibclarke@gmail.com>.
Licensed under the [MIT license](license.txt).

Requires Python 3.10 or newer and declares ChimeraX 1.11 or newer as the
intended compatibility floor. The native GUI has been tested on macOS with
ChimeraX 1.12.dev202603110023; stable 1.11 and Windows/Linux are not yet tested.
No separate Gemmi installation is needed to use the bundle.

ChimeraX bundle for reading, browsing, editing, and exporting the custom
`_cootnote_residue_note.*` mmCIF annotations used by `coot_trimmings`.

The bundle currently provides two tools:

- `Residue Notes`
  - full editor for note threads attached to residues, single-chain regions, or Cartesian positions
  - add, edit, delete, import, export, and Markdown export
- `Nearby Notes`
  - read-only browser for annotated residues near the current center of rotation

## Current behavior

Navigation preserves the current center-of-rotation mode and pivot indicator
settings. For example, `cofron` remains in effect after clicking a residue,
region, or positional note, or using Previous/Next.

The main `Residue Notes` tool:

- follows a single selected residue when there is one
- otherwise falls back to the residue closest to the current center of rotation
- stores an optional short `title` per note
- supports title-only region labels for motifs or domains
- navigates to region notes and selects their residues without changing structure colours
- shows notes as collapsible cards rather than one plain text block
- remembers the author for the current ChimeraX session
- can export either:
  - annotated mmCIF
  - Markdown table

The `Nearby Notes` tool:

- is read-only by design
- follows the current center of rotation
- shows note threads within a user-set radius
- includes a region when any member residue is within the radius
- shares in-memory notes with the main tool, including newly added or edited notes
- uses the same collapsible note-card display as the main tool

## Commands

Install in ChimeraX with:

```chimerax
devel install "/path/to/chimerax-residue-notes"
```

Open the main tool:

```chimerax
resnotes
```

Open the nearby-notes pane:

```chimerax
nearby_notes
```

Useful command-line actions:

```chimerax
resnotes import /path/to/annotated_model.cif
resnotes export /path/to/output.annotated.cif overwrite true
resnotes export-markdown /path/to/output.annotations.md overwrite true
resnotes refresh
nearby_notes
```

You can also target a specific atomic model explicitly:

```chimerax
resnotes import /path/to/annotated_model.cif #2
resnotes export /path/to/output.annotated.cif #2 overwrite true
resnotes export-markdown /path/to/output.annotations.md #2 overwrite true
nearby_notes #2
```

## Region Notes

Select residues in ChimeraX, then choose **Add note from selection** in
`resnotes`. One selected residue creates a residue note; a contiguous polymer
selection in one chain creates a region note directly, without entering endpoints.
Partial atom selections use their containing residues. Disjoint selections and
selections spanning models or chains are rejected rather than silently expanded.
Protein/nucleic residues with an incomplete ChimeraX polymer assignment can
still be annotated when their residue type and backbone atoms identify them.
Repeated copies of a residue ID share the range annotation; selecting just one
copy is rejected if that would broaden the selection. No atoms are merged,
deleted, or repaired by the notes tool.

Alternatively, **Choose range...** lets you enter the chain, start, and end
manually or prefill them from the selection. Insertion codes are
supported, for example `75A` to `80B`. Endpoints must belong to the same polymer
chain. The range includes the modelled residues between them, even when residue
numbering has gaps. A title alone is enough to label a motif such as a selectivity
filter; longer explanatory text is optional.

Alternatively, choose **Pick endpoints** in the range dialog, then left-click
the first and last residues in the 3D view. Atoms and ribbons can both be picked;
dragging still rotates the view. A cyan sphere marks the first endpoint, and an
orange sphere marks the last while the note editor is open. Markers sit on CA
(or P, falling back to the residue centre) and are not saved as atoms.
The button becomes **Cancel picking** while
waiting. Completion, cancellation, closing the editor, or changing models
restores the previous left-mouse binding. No note is added until the note editor
is submitted.

Click the region thread in either notes pane, or use Previous/Next in the editor,
to centre and select the entire range. Its centre is recomputed from the
current atoms rather than stored as a stale Cartesian point. Navigation never
changes atom/ribbon colours or visibility; the native selection outline identifies
the range. A symmetric, camera-aligned clipping slab is centred on the range,
at least 10 A deep and extending at least 10 A beyond its atoms in depth.
Stale scene-fixed front/back clips are replaced by this near/far slab so they
cannot hide the new target.

In Coot's annotation browser, **Add region note...** offers two-click picking
or an entered chain/range. Region navigation uses the user-coloured CA view on
compatible builds. Both applications preserve region notes in annotated mmCIF
and Markdown exports. Export remains explicit.

## Positional Notes

Choose **Add note at center of rotation** in `resnotes` to annotate an unknown
density, binding site, or other point without selecting or naming a residue.
The current CoFR is captured when the editor opens, even if it is off-centre in
the view. It is not changed to the view centre. Only the title, author, and text
are editable; editing a note does not relocate its point.

Click a positional thread, or navigate with Previous/Next, to centre it and show
a temporary cyan sphere. The current orientation and zoom are retained, with a
symmetric 10 A clipping slab centred on the point (equivalent to `symclip 5`). The
marker is a non-pickable drawing, not a model atom, and is cleared when switching
threads/models, refreshing, or closing the tool. Nearby Notes includes positional
threads by their distance from the CoFR; clicking one navigates to that point.

Positions are stored in the associated model's file-coordinate frame. They
follow rigid model transforms in ChimeraX, but are independent of residue
numbering and coordinate edits. Annotated export explicitly uses that same frame
for atoms and notes, including after moving/rotating the model. The exported
positions therefore match Coot's Cartesian coordinates. Notes still need an
associated atomic model for import/export, but no residue identifier is invented.

## Annotation format

The bundle now writes notes in a plain-text UTF-8 mmCIF loop with stronger
residue identifiers:

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
- `_cootnote_residue_note.note`
- `_cootnote_residue_note.target_kind` (`residue`, `region`, or `position`)
- `_cootnote_residue_note.end_label_comp_id`
- `_cootnote_residue_note.end_label_asym_id`
- `_cootnote_residue_note.end_label_seq_id`
- `_cootnote_residue_note.end_auth_asym_id`
- `_cootnote_residue_note.end_auth_seq_id`
- `_cootnote_residue_note.end_pdbx_PDB_ins_code`
- `_cootnote_residue_note.position_x`
- `_cootnote_residue_note.position_y`
- `_cootnote_residue_note.position_z`

Important details:

- new exports are written in the plain-text schema above
- region rows identify both endpoints; ordinary residue notes leave end fields unassigned
- position rows use finite XYZ coordinates and leave residue/end identifiers unassigned
- files without `target_kind` or end fields still load as ordinary residue notes
- malformed, cross-chain, or ambiguous ranges are not silently attached to another residue
- older `_b64` title/author/note fields are still read for backward compatibility
- residue matching prefers the stronger label-based identifiers, with auth-based information retained for display and interoperability

## Notes

- Export is explicit; the bundle does not try to patch ChimeraX's default `save format mmcif` behavior globally.
- Annotated mmCIF export works by saving the current model and then reinjecting the custom note loop.
- Markdown export writes one row per note with `Target`, `Title`, `Author`, `Timestamp`, and `Note`.
- If a note has no explicit title, the UI falls back to the first line of the note text for previews.

## Status

Tool Shed release preparation and remaining checks are documented in
[SUBMISSION.md](SUBMISSION.md). An annotated-mmCIF or Markdown export is required
to preserve new notes. ChimeraX session saving does not preserve these tool notes.

This is still a lightweight working bundle rather than a polished general-release tool, but it is now substantially beyond the original prototype:

- editable note threads
- nearby read-only note browsing
- optional note titles
- single-chain region notes with selection-only navigation and padded symmetric clipping
- positional notes at the current CoFR with temporary point markers
- stronger mmCIF residue identifiers
- plain-text UTF-8 note storage
- explicit annotated mmCIF and Markdown export
