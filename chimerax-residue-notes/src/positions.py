"""Positional notes use the associated model's Cartesian coordinate frame."""
import math
from .navigation import preserve_cofr_mode, set_navigation_clip


POSITION_FIELDS = ("position_x", "position_y", "position_z")


def position_xyz(entry):
    try:
        values = [entry[field] for field in POSITION_FIELDS]
        if any(isinstance(value, bool) for value in values):
            return None
        xyz = tuple(float(value) for value in values)
        return xyz if all(math.isfinite(value) for value in xyz) else None
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def position_label(entry):
    return "Position ({:.3f}, {:.3f}, {:.3f})".format(*position_xyz(entry))


def position_scene_xyz(model, entry):
    xyz = position_xyz(entry)
    if xyz is None:
        raise ValueError("The note has no valid Cartesian position.")
    return tuple(float(v) for v in model.scene_position * xyz)


def position_identifier_fields(model, scene_xyz):
    if scene_xyz is None:
        raise ValueError("The center of rotation is unavailable.")
    xyz = tuple(float(v) for v in model.scene_position.inverse() * scene_xyz)
    fields = dict(zip(POSITION_FIELDS, xyz))
    if position_xyz(fields) is None:
        raise ValueError("The center of rotation must have finite coordinates.")
    fields.update(target_kind="position", label_comp_id="", label_asym_id="", label_seq_id="",
                  auth_asym_id="", auth_seq_id=None, pdbx_PDB_ins_code="")
    return fields


class PositionHighlight:
    """A temporary child drawing, not an atom or a new session model."""
    def __init__(self):
        self.model = self.drawing = None

    def clear(self):
        model, drawing = self.model, self.drawing
        self.model = self.drawing = None
        if model is not None and drawing is not None and not model.deleted:
            model.remove_drawing(drawing)

    def show(self, model, entry):
        from chimerax.graphics import Drawing
        from chimerax.surface import sphere_geometry
        from numpy import array
        self.clear()
        vertices, normals, triangles = sphere_geometry(80)
        drawing = Drawing("Annotation position")
        drawing.set_geometry(vertices * 0.6 + array(position_xyz(entry), dtype='float32'), normals, triangles)
        drawing.color = (0, 220, 220, 255)
        drawing.pickable = False
        drawing.skip_bounds = True
        model.add_drawing(drawing)
        self.model, self.drawing = model, drawing


def navigate_to_position(session, model, entry, highlight):
    from numpy import array, dot
    xyz = array(position_scene_xyz(model, entry))
    view = session.main_view
    origin, direction = view.camera.position.origin(), view.camera.view_direction()
    # Centre the point without changing orientation or zoom, even with an off-axis CoFR.
    screen_centre = origin + dot(view.center_of_rotation - origin, direction) * direction
    with preserve_cofr_mode(session):
        view.translate(screen_centre - xyz, move_near_far_clip_planes=True)
        set_navigation_clip(view, xyz)
        view.center_of_rotation = xyz
    highlight.show(model, entry)
