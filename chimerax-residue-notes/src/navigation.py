"""Keep note navigation from changing the user's rotation behaviour."""
from contextlib import contextmanager

MIN_CLIP_HALF_WIDTH = 5.0
RANGE_CLIP_PADDING = 10.0


def set_navigation_clip(view, centre, coordinates=None):
    """Centre a padded, camera-aligned slab on the navigation target."""
    from numpy import array, dot, isfinite
    centre = array(centre, dtype=float)
    direction = array(view.camera.view_direction(), dtype=float)
    if not isfinite(centre).all() or not isfinite(direction).all():
        raise ValueError('Cannot clip around a non-finite navigation target')
    half_width = MIN_CLIP_HALF_WIDTH
    if coordinates is not None and len(coordinates):
        coordinates = array(coordinates, dtype=float)
        if not isfinite(coordinates).all():
            raise ValueError('Cannot clip a range with non-finite coordinates')
        depths = dot(coordinates - centre, direction)
        half_width = max(half_width, float(abs(depths).max()) + RANGE_CLIP_PADDING)
    if not isfinite(centre).all() or not isfinite(direction).all() or not isfinite(half_width):
        raise ValueError('Cannot clip around a non-finite navigation target')
    planes = view.clip_planes
    # Old scene-fixed front/back planes must not hide the newly centred target.
    for name in ('front', 'back'):
        planes.remove_plane(name)
    for name, sign in (('near', -1), ('far', 1)):
        planes.set_clip_position(name, centre + sign * half_width * direction, view)
    return half_width


@contextmanager
def preserve_cofr_mode(session):
    view = session.main_view
    method = view.center_of_rotation_method
    try:
        yield
    finally:
        # Assigning a pivot coordinate silently changes ChimeraX's mode to fixed.
        if view.center_of_rotation_method != method:
            view.center_of_rotation_method = method
