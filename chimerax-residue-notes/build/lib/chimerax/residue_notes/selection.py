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


def closest_residue_to_xyz(model, xyz):
    if model is None or xyz is None:
        return None
    best_residue = None
    best_distance_sq = None
    for residue in safe_model_residues(model):
        residue_xyz = residue_center_xyz(residue)
        if residue_xyz is None:
            continue
        dx = residue_xyz[0] - xyz[0]
        dy = residue_xyz[1] - xyz[1]
        dz = residue_xyz[2] - xyz[2]
        distance_sq = dx * dx + dy * dy + dz * dz
        if best_distance_sq is None or distance_sq < best_distance_sq:
            best_distance_sq = distance_sq
            best_residue = residue
    return best_residue
