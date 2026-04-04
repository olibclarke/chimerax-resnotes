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


def find_residue_by_note_key(model, key):
    if model is None or key is None:
        return None
    chain_id, resno, ins_code = key[:3]
    for residue in safe_model_residues(model):
        if residue.chain_id == chain_id and residue.number == resno and (residue.insertion_code or "") == (ins_code or ""):
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
