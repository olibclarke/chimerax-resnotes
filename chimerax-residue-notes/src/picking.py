"""Temporary two-click range picking; ordinary drags still rotate the view."""
from chimerax.mouse_modes.std_modes import RotateMouseMode

from .selection import is_polymer_residue, region_identifier_fields
from .regions import EndpointHighlight


class RegionEndpointPicker(RotateMouseMode):
    name = "residue notes pick endpoints"

    def __init__(self, session, model, on_complete, on_status, is_live):
        super().__init__(session)
        self.model = model
        self._complete = on_complete
        self._status = on_status
        self._is_live = is_live
        self._first = None
        self._previous_mode = None
        self._dragged = False
        self.active = False
        self._markers = EndpointHighlight()

    def start(self):
        modes = self.session.ui.mouse_modes
        self._previous_mode = modes.mode("left", [], exact=True)
        self.active = True
        try:
            modes.bind_mouse_mode("left", [], self)
        except Exception:
            self.stop()
            raise
        self._status("Click the first residue (atom or ribbon); drag to rotate. Cancel picking to stop.")

    def stop(self):
        self._markers.clear()
        if not self.active:
            return
        self.active = False
        modes = self.session.ui.mouse_modes
        # Do not undo an intentional mouse-mode change made while picking.
        if modes.mode("left", [], exact=True) is self:
            modes.bind_mouse_mode("left", [], self._previous_mode)
        self._first = None

    def mouse_down(self, event):
        self._dragged = False
        super().mouse_down(event)

    def mouse_drag(self, event):
        self._dragged = True
        super().mouse_drag(event)

    def mouse_up(self, event):
        clicked = self.active and not self._dragged and self.mouse_down_position is not None
        super().mouse_up(event)
        if clicked:
            self.pick_at(*event.position())

    def pick_at(self, x, y):
        if not self.active:
            return
        if not self._is_live():
            self.stop()
            self._complete(None)
            return
        pick = self.view.picked_object(x, y)
        atom = getattr(pick, "atom", None)
        residue = atom.residue if atom is not None else getattr(pick, "residue", None)
        if residue is None or getattr(residue, "deleted", False):
            self._status("Click an atom or ribbon residue in the annotation model.")
            return
        if residue.structure is not self.model:
            self._status("Choose both endpoints in the annotation model.")
            return
        if not is_polymer_residue(residue):
            self._status("Region endpoints must be polymer residues.")
            return
        label = f"{residue.chain_id}:{residue.number}{residue.insertion_code or ''} {residue.name}"
        if self._first is None:
            self._first = residue
            self._markers.show((residue,))
            self._status(f"Clicked residue: {label} | Click the last residue.")
            return
        if getattr(self._first, "deleted", False):
            self._first = None
            self._markers.clear()
            self._status("The first endpoint was deleted; click a new first residue.")
            return
        try:
            region_identifier_fields(self._first, residue)
        except ValueError as error:
            self._status(str(error))
            return
        endpoints = (self._first, residue)
        self.stop()
        self._status(f"Clicked residue: {label}")
        self._complete(endpoints)
