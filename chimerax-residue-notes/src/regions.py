"""Region selection/navigation and non-atomic endpoint markers."""
from .navigation import preserve_cofr_mode, set_navigation_clip


class EndpointHighlight:
    """Non-pickable, model-local spheres that never enter the atom table."""
    def __init__(self):
        self._drawings = []

    def clear(self):
        for model, drawing in self._drawings:
            if not model.deleted:
                model.remove_drawing(drawing)
        self._drawings.clear()

    def show(self, residues):
        from chimerax.graphics import Drawing
        from chimerax.surface import sphere_geometry
        self.clear()
        vertices, normals, triangles = sphere_geometry(80)
        try:
            for residue, colour in zip(residues, ((0, 220, 220, 255), (255, 120, 40, 255))):
                atom = residue.find_atom("CA") or residue.find_atom("P")
                xyz = atom.coord if atom is not None else residue.atoms.coords.mean(axis=0)
                drawing = Drawing("Note range endpoint")
                drawing.set_geometry(vertices * 0.8 + xyz, normals, triangles)
                drawing.color = colour
                drawing.pickable = False
                drawing.skip_bounds = True
                residue.structure.add_drawing(drawing)
                self._drawings.append((residue.structure, drawing))
        except Exception:
            self.clear()
            raise


def navigate_to_region(session, residues):
    from chimerax.atomic import concatenate
    from chimerax.geometry import Bounds
    atoms = concatenate([r.atoms for r in residues])
    bounds = atoms.scene_bounds
    if bounds is None:
        raise ValueError("The annotated region has no atoms to navigate to.")
    session.selection.clear()
    atoms.selected = True
    centre = bounds.center()
    # Keep a little context even for a very small motif.
    bounds = Bounds(bounds.xyz_min-3.0, bounds.xyz_max+3.0)
    view = session.main_view
    with preserve_cofr_mode(session):
        view.view_all(bounds, pad=0.2)
        set_navigation_clip(view, centre, atoms.scene_coords)
        view.center_of_rotation = centre
