# Tool Shed Submission Preparation

## Listing Draft

- Bundle: ChimeraX-ResidueNotes
- Display name: Residue Notes
- Version: 0.2.6
- Author: Oliver Clarke
- Public maintainer contact: olibclarke@gmail.com
- Project: https://github.com/olibclarke/chimerax-resnotes
- Support: https://github.com/olibclarke/chimerax-resnotes/issues
- License: MIT; full terms are in license.txt and the wheel.
- Suggested listing categories: User Interface, Input/Output, Structure Analysis.

### Summary

Annotate residues, regions, and unknown-density sites; exchange notes with Coot
through annotated mmCIF files.

### Description

Residue Notes adds editable annotation threads to molecular structures in
ChimeraX. Attach a note to one residue, a contiguous single-chain selection, or
the current center of rotation without inventing a residue for an unknown site.

Navigate between annotations with native range selection or temporary point markers.
Structure colours and visibility are left unchanged. Range and positional
navigation centres a symmetric, generously padded clipping slab on the target.
Optional endpoint picking marks both residues and restores the previous mouse
binding when finished. Nearby Notes provides a read-only browser of annotations
around the current center of rotation.

Export annotated mmCIF to preserve editable notes with the model and exchange
them with Coot Trimmings. Export Markdown for a readable report. Older residue
notes and legacy Base64 text remain readable. Markers do not add model atoms.

**Saving is explicit:** ordinary model saving and ChimeraX session saving do not
preserve newly created notes. Export annotated mmCIF before closing the model.
Positional notes follow rigid model transforms, but not local atom edits.

The bundle uses ChimeraX-provided Python libraries. Users do not need a separate
Gemmi, Coot, CCP4, or system-Python installation.

### Release Notes

0.2.6 reduces the minimum clipping slab to 10 A total (symclip 5), retaining
the depth-dependent padding for ranges.

0.2.5 selects ranges without changing atom/ribbon colours or visibility.
Range and positional navigation centres a near/far clipping slab on the target:
at least 40 A deep, plus 10 A beyond each depth extreme for a larger range.
Existing scene-fixed front/back clipping planes are replaced to avoid hiding
the target. CoFR mode and pivot settings remain unchanged.

0.2.4 keeps the user's center-of-rotation mode and pivot-indicator settings
unchanged when navigating to residue, region, and positional notes.

0.2.3 prepares the region/positional-note release for distribution: MIT licensing,
public maintainer and project metadata, declared runtime dependencies, an accurate
Python compatibility floor, and checks of the actual built wheel.

0.2.2 introduced positional notes at the current center of rotation, exact
selection-to-region conversion, temporary endpoint markers, and corrected range
navigation, including transformed models and clipped views.

## Build And Verify

From the bundle folder:

```sh
python3 -B -m unittest test_positions test_regions test_release test_navigation -v
python3 -B tools/prepare_toolshed_release.py --output release/0.2.6 --test-install
```

For a non-default ChimeraX executable, add `--chimerax /path/to/ChimeraX`.
The optional Coot interoperability test uses `COOT_TRIMMINGS_SCRIPT` when set.
The GUI check uses the repository's public annotated_example.cif; the source-only
development checkout also supports the existing 3CH3 test model next to it.

The output directory contains the wheel to upload, SHA256SUMS, manifest.json,
build/install/GUI/uninstall logs, an annotated test export, and a current GUI
screenshot. Only upload the wheel; the test exports/logs are not installer files.
The checks run in temporary profiles and never install into the user's profile.
The wheel is pure Python (`py310-none-any`); that is not a cross-platform test claim.

## Compatibility And Remaining Checks

- Python minimum: 3.10 (the source uses union-type annotations).
- Intended ChimeraX compatibility floor: 1.11, declared via ChimeraX-Core.
- Tested native runtime so far: macOS, ChimeraX 1.12.dev202603110023.
- Stable-release test: still required before claiming stable 1.11 support.
- Windows/Linux checks: not yet performed; request tester feedback before
  advertising these as verified platforms.
- Session persistence is intentionally not implemented; annotated export is the
  persistence mechanism and must remain prominent in the listing and help.

Do not interpret the metadata's minimum version or wheel tag as proof that all
ChimeraX releases/platforms have been tested. If stable-release testing exposes
an API incompatibility, fix it or raise the declared minimum before uploading.

## Submit

1. Confirm the final wheel passes the checks, and review the screenshot.
2. Sign in with the maintainer's Google account at https://cxtoolshed.rbvi.ucsf.edu/.
3. Choose Submit a Bundle and upload the .whl, not the source ZIP.
4. Supply the listing text, public contact, MIT terms, source/support URLs, and
   screenshot. A publication citation is optional; none is claimed here.
5. The first submission requires inspection/approval by the ChimeraX team.

This preparation does not upload or submit anything to the Tool Shed.

References:
- https://chimerax.readthedocs.io/en/latest/writing_bundles.html
- https://chimerax.readthedocs.io/en/latest/tutorials/bundle_info.html
