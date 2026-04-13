from chimerax.atomic import selected_residues


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
    if model is None or entry is None:
        return None
    for residue in safe_model_residues(model):
        if annotation_entry_matches_residue(entry, residue):
            return residue
    return None


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
