"""Temporary region highlighting, independent of note storage and UI widgets."""


class RegionHighlight:
    colour = (255, 165, 0, 255)

    def __init__(self):
        self._atoms = []
        self._residues = []

    def clear(self):
        for atom, colour, display, shown in self._atoms:
            if getattr(atom, "deleted", False):
                continue
            if tuple(atom.color) == self.colour:
                atom.color = colour
            if shown:
                atom.display = display
        for residue, colour in self._residues:
            if not getattr(residue, "deleted", False) and tuple(residue.ribbon_color) == self.colour:
                residue.ribbon_color = colour
        self._atoms.clear()
        self._residues.clear()

    def show(self, residues):
        self.clear()
        visible = any(getattr(r, "ribbon_display", False) or any(a.display for a in r.atoms) for r in residues)
        try:
            for residue in residues:
                self._residues.append((residue, tuple(residue.ribbon_color)))
                residue.ribbon_color = self.colour
                for atom in residue.atoms:
                    shown = not visible and atom.name.strip() in ("CA", "P")
                    self._atoms.append((atom, tuple(atom.color), atom.display, shown))
                    atom.color = self.colour
                    if shown:
                        atom.display = True
        except Exception:
            self.clear()
            raise


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


def navigate_to_region(session, residues, highlight):
    from chimerax.atomic import concatenate
    from chimerax.geometry import Bounds
    atoms = concatenate([r.atoms for r in residues])
    bounds = atoms.scene_bounds
    if bounds is None:
        raise ValueError("The annotated region has no atoms to navigate to.")
    highlight.show(residues)
    session.selection.clear()
    atoms.selected = True
    centre = bounds.center()
    # Keep a little context even for a very small motif.
    bounds = Bounds(bounds.xyz_min-3.0, bounds.xyz_max+3.0)
    view = session.main_view
    view.view_all(bounds, pad=0.2)
    # Like native `view`, move an existing near/far slab to the new target.
    direction = view.camera.view_direction()
    for name, sign in (("near", -1), ("far", 1)):
        if view.clip_planes.find_plane(name) is not None:
            view.clip_planes.set_clip_position(name, centre + sign * bounds.radius() * direction, view)
    view.center_of_rotation = centre
