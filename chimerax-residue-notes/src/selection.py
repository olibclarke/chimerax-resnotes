from chimerax.atomic import selected_residues


def is_polymer_residue(residue):
    if getattr(residue, "polymer_type", 0) != getattr(residue, "PT_NONE", 0):
        return True
    # Incomplete chain/entity assignments can leave real backbone residues PT_NONE.
    name = getattr(residue, "name", "").upper()
    if name in {"ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
                "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
                "MSE", "SEC", "PYL", "ASX", "GLX", "UNK"}:
        backbone = ("N", "CA", "C")
    elif name in {"A", "C", "G", "U", "T", "I", "DA", "DC", "DG", "DT", "DU", "DI"}:
        backbone = ("C3'", "C4'", "O3'")
    else:
        return False
    find_atom = getattr(residue, "find_atom", None)
    return find_atom is not None and all(find_atom(name) is not None for name in backbone)


def selected_residues_for_model(session, model=None):
    residues = list(selected_residues(session) or [])
    if model is None:
        return residues
    return [residue for residue in residues if residue.structure is model]


def single_selected_residue(session, model=None):
    residues = selected_residues_for_model(session, model=model)
    if len(residues) == 1:
        return residues[0]
    return None


def safe_model_residues(model):
    if model is None:
        return []
    try:
        return list(model.residues)
    except Exception:
        return []


def cofr_xyz(session):
    main_view = getattr(session, "main_view", None)
    if main_view is None:
        return None
    for attr_name in ("center_of_rotation", "center_of_rotation_point"):
        try:
            value = getattr(main_view, attr_name)
        except Exception:
            continue
        if callable(value):
            try:
                value = value()
            except Exception:
                continue
        if value is None:
            continue
        try:
            if len(value) == 3:
                return (float(value[0]), float(value[1]), float(value[2]))
        except Exception:
            continue
    return None


def cofr_key(session):
    xyz = cofr_xyz(session)
    if xyz is None:
        return None, None
    return xyz, tuple(round(value, 2) for value in xyz)


def residue_center_xyz(residue):
    atoms = getattr(residue, "atoms", None)
    if atoms is None or len(atoms) == 0:
        return None
    for attr_name in ("scene_coords", "coords"):
        try:
            coords = getattr(atoms, attr_name)
        except Exception:
            continue
        try:
            if len(coords) == 0:
                continue
            n_atoms = len(coords)
            sum_x = sum(float(coord[0]) for coord in coords)
            sum_y = sum(float(coord[1]) for coord in coords)
            sum_z = sum(float(coord[2]) for coord in coords)
            return (sum_x / n_atoms, sum_y / n_atoms, sum_z / n_atoms)
        except Exception:
            continue
    return None


def distance_sq(xyz_a, xyz_b):
    if xyz_a is None or xyz_b is None:
        return None
    dx = xyz_a[0] - xyz_b[0]
    dy = xyz_a[1] - xyz_b[1]
    dz = xyz_a[2] - xyz_b[2]
    return dx * dx + dy * dy + dz * dz


def residue_label_asym_id(residue):
    chain_id = getattr(residue, "mmcif_chain_id", None)
    if isinstance(chain_id, str) and chain_id.strip():
        return chain_id.strip()
    return (getattr(residue, "chain_id", None) or "").strip()


def residue_label_seq_id(residue):
    pt_none = getattr(residue, "PT_NONE", 0)
    if getattr(residue, "polymer_type", pt_none) == pt_none:
        return ""
    model = getattr(residue, "structure", None)
    label_asym_id = residue_label_asym_id(residue)
    if model is None or not label_asym_id:
        return ""
    position = 0
    for candidate in safe_model_residues(model):
        if getattr(candidate, "polymer_type", pt_none) == pt_none:
            continue
        if residue_label_asym_id(candidate) != label_asym_id:
            continue
        position += 1
        if candidate is residue:
            return str(position)
    return ""


def residue_identifier_fields(residue):
    if residue is None:
        return None
    return {
        "label_comp_id": getattr(residue, "name", None) or "?",
        "label_asym_id": residue_label_asym_id(residue),
        "label_seq_id": residue_label_seq_id(residue),
        "auth_asym_id": getattr(residue, "chain_id", None) or "",
        "auth_seq_id": int(getattr(residue, "number")),
        "pdbx_PDB_ins_code": getattr(residue, "insertion_code", None) or "",
    }


def _entry_text(entry, key):
    value = entry.get(key)
    if value in (None, ".", "?"):
        return ""
    return str(value).strip()


def _entry_int(entry, key):
    try:
        return int(_entry_text(entry, key))
    except Exception:
        return None


def annotation_entry_matches_residue(entry, residue):
    if entry.get("target_kind") == "position":
        return False
    residue_fields = residue_identifier_fields(residue)
    if residue_fields is None:
        return False

    entry_label_comp_id = _entry_text(entry, "label_comp_id") or "?"
    residue_label_comp_id = _entry_text(residue_fields, "label_comp_id") or "?"
    if entry_label_comp_id != residue_label_comp_id:
        return False

    entry_label_asym_id = _entry_text(entry, "label_asym_id")
    entry_label_seq_id = _entry_text(entry, "label_seq_id")
    residue_label_asym_id_value = _entry_text(residue_fields, "label_asym_id")
    residue_label_seq_id_value = _entry_text(residue_fields, "label_seq_id")
    if entry_label_asym_id and residue_label_asym_id_value:
        if entry_label_asym_id == residue_label_asym_id_value:
            if entry_label_seq_id or residue_label_seq_id_value:
                if entry_label_seq_id == residue_label_seq_id_value:
                    return True
            else:
                entry_auth_asym_id = _entry_text(entry, "auth_asym_id")
                residue_auth_asym_id = _entry_text(residue_fields, "auth_asym_id")
                entry_auth_seq_id = _entry_int(entry, "auth_seq_id")
                residue_auth_seq_id = _entry_int(residue_fields, "auth_seq_id")
                entry_ins_code = _entry_text(entry, "pdbx_PDB_ins_code")
                residue_ins_code = _entry_text(residue_fields, "pdbx_PDB_ins_code")
                if (
                    entry_auth_asym_id == residue_auth_asym_id
                    and entry_auth_seq_id == residue_auth_seq_id
                    and entry_ins_code == residue_ins_code
                ):
                    return True

    entry_auth_asym_id = _entry_text(entry, "auth_asym_id")
    residue_auth_asym_id = _entry_text(residue_fields, "auth_asym_id")
    entry_auth_seq_id = _entry_int(entry, "auth_seq_id")
    residue_auth_seq_id = _entry_int(residue_fields, "auth_seq_id")
    entry_ins_code = _entry_text(entry, "pdbx_PDB_ins_code")
    residue_ins_code = _entry_text(residue_fields, "pdbx_PDB_ins_code")
    return (
        entry_auth_asym_id == residue_auth_asym_id
        and entry_auth_seq_id == residue_auth_seq_id
        and entry_ins_code == residue_ins_code
    )


def find_residue_for_annotation(model, entry):
    if model is None or entry is None or entry.get("target_kind") == "position":
        return None
    for residue in safe_model_residues(model):
        if annotation_entry_matches_residue(entry, residue):
            return residue
    return None


def _region_endpoint(model, entry, residues):
    # Author identifiers are normally unique; disambiguate using label identifiers
    # when a file intentionally reuses author numbering across polymer chains.
    candidates = [r for r in residues
                  if r.chain_id == _entry_text(entry, "auth_asym_id")
                  and r.number == _entry_int(entry, "auth_seq_id")
                  and (r.insertion_code or "") == _entry_text(entry, "pdbx_PDB_ins_code")
                  and (_entry_text(entry, "label_comp_id") in ("", "?")
                       or r.name == _entry_text(entry, "label_comp_id"))]
    if len(candidates) == 1:
        return candidates[0]
    candidates = [r for r in candidates if residue_label_asym_id(r) == _entry_text(entry, "label_asym_id")]
    if len(candidates) == 1:
        return candidates[0]
    label_seq = _entry_text(entry, "label_seq_id")
    if label_seq:
        seq_matches = [r for r in candidates if residue_label_seq_id(r) == label_seq]
        if len(seq_matches) == 1:
            return seq_matches[0]
    # Notes address residue identifiers, not individual copies of the same ID.
    if candidates and len({r.name for r in candidates}) == 1:
        return candidates[0]
    return None


def find_residues_for_annotation(model, entry):
    if model is None or entry is None or entry.get("target_kind") == "position":
        return []
    if entry.get("target_kind") != "region":
        residue = find_residue_for_annotation(model, entry)
        return [residue] if residue is not None else []
    residues = safe_model_residues(model)
    end_entry = {key: entry.get("end_" + key) for key in
                 ("label_comp_id", "label_asym_id", "label_seq_id", "auth_asym_id", "auth_seq_id", "pdbx_PDB_ins_code")}
    first = _region_endpoint(model, entry, residues)
    last = _region_endpoint(model, end_entry, residues)
    if first is None or last is None:
        return []
    if residue_label_asym_id(first) != residue_label_asym_id(last):
        return []
    chain_residues = [r for r in residues if r.chain_id == first.chain_id
                      and residue_label_asym_id(r) == residue_label_asym_id(first)
                      and is_polymer_residue(r)]
    if first not in chain_residues or last not in chain_residues:
        return []
    identifiers = [(r.number, r.insertion_code or "") for r in chain_residues]
    if len(set(identifiers)) != len(identifiers):
        # Model order may contain whole repeated chain blocks. An index slice
        # between blocks would wrongly include most of the chain.
        lower, upper = sorted(((first.number, first.insertion_code or ""),
                               (last.number, last.insertion_code or "")))
        return [r for r, key in zip(chain_residues, identifiers) if lower <= key <= upper]
    lower, upper = sorted((chain_residues.index(first), chain_residues.index(last)))
    return chain_residues[lower:upper+1]


def region_identifier_fields(first, last):
    if first.structure is not last.structure or residue_label_asym_id(first) != residue_label_asym_id(last) or first.chain_id != last.chain_id:
        raise ValueError("Choose polymer endpoints in the same model and chain.")
    if not all(is_polymer_residue(r) for r in (first, last)):
        raise ValueError("Region notes require polymer endpoints.")
    residues = safe_model_residues(first.structure)
    if residues.index(first) > residues.index(last):
        first, last = last, first
    fields = residue_identifier_fields(first)
    fields.update({"end_"+key: value for key, value in residue_identifier_fields(last).items()})
    fields["target_kind"] = "region"
    return fields


def selection_note_fields(residues, model):
    """Describe exactly the selection, without filling unselected gaps."""
    selected = set(residues)
    if not selected:
        raise ValueError("Select a residue or a contiguous range first.")
    if any(r.structure is not model for r in selected):
        raise ValueError("Select residues only in the annotation model.")
    if len(selected) == 1:
        return residue_identifier_fields(next(iter(selected)))
    ordered = [r for r in safe_model_residues(model) if r in selected]
    if len(ordered) != len(selected):
        raise ValueError("The selected residues are no longer available.")
    fields = region_identifier_fields(ordered[0], ordered[-1])
    members = find_residues_for_annotation(model, fields)
    if set(members) != selected:
        raise ValueError("Select one contiguous polymer range in one chain; unselected gaps are not included.")
    return fields


def closest_residue_to_xyz(model, xyz):
    if model is None or xyz is None:
        return None
    best_residue = None
    best_distance_sq = None
    for residue in safe_model_residues(model):
        residue_xyz = residue_center_xyz(residue)
        residue_distance_sq = distance_sq(residue_xyz, xyz)
        if residue_distance_sq is None:
            continue
        if best_distance_sq is None or residue_distance_sq < best_distance_sq:
            best_distance_sq = residue_distance_sq
            best_residue = residue
    return best_residue
