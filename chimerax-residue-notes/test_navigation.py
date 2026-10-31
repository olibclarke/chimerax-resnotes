"""Navigation preserves CoFR modes without restoring an obsolete pivot point."""
import ast
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np


ROOT = Path(__file__).resolve().parent
package = ModuleType('navigation_under_test')
package.__path__ = [str(ROOT/'src')]
sys.modules[package.__name__] = package
navigation = importlib.import_module(package.__name__+'.navigation')
regions = importlib.import_module(package.__name__+'.regions')


class Planes:
    def __init__(self):
        self.values = {}

    def remove_plane(self, name):
        self.values.pop(name, None)

    def set_clip_position(self, name, point, view):
        self.values[name] = SimpleNamespace(plane_point=np.array(point))

    def find_plane(self, name):
        return self.values.get(name)


class View:
    def __init__(self, mode):
        self.center_of_rotation_method = mode
        self._point = (0, 0, 0)
        self.indicator = object()

    @property
    def center_of_rotation(self):
        return self._point

    @center_of_rotation.setter
    def center_of_rotation(self, xyz):
        self._point = xyz
        self.center_of_rotation_method = 'fixed'


class NavigationTests(unittest.TestCase):
    def clip_view(self, direction=(0, 0, -1)):
        return SimpleNamespace(clip_planes=Planes(),
                               camera=SimpleNamespace(view_direction=lambda: direction))

    def test_position_creates_symmetric_generous_slab_from_unclipped_view(self):
        view = self.clip_view()
        centre = np.array((100, -50, 20))
        half = navigation.set_navigation_clip(view, centre)
        near, far = [view.clip_planes.find_plane(name).plane_point for name in ('near', 'far')]
        self.assertTrue(np.allclose((near+far)/2, centre))
        self.assertAlmostEqual(np.linalg.norm(far-near), 10)
        self.assertEqual(half, 5)

    def test_large_range_is_padded_in_the_actual_view_direction(self):
        view = self.clip_view((1, 0, 0))
        centre = np.array((10, 20, 30))
        coordinates = [centre+(-70, 0, 0), centre+(50, 0, 0)]
        half = navigation.set_navigation_clip(view, centre, coordinates)
        self.assertEqual(half, 80)
        for name, sign in (('near', -1), ('far', 1)):
            self.assertTrue(np.allclose(view.clip_planes.find_plane(name).plane_point,
                                        centre+np.array((sign*80, 0, 0))))

    def test_wide_but_shallow_range_does_not_make_an_excessively_deep_slab(self):
        view = self.clip_view()
        half = navigation.set_navigation_clip(view, (0, 0, 0), [(-1000, 0, 0), (1000, 0, 0)])
        self.assertEqual(half, 10)

    def test_old_scene_clips_are_removed_but_custom_planes_are_preserved(self):
        view = self.clip_view()
        for name in ('front', 'back', 'custom'):
            view.clip_planes.values[name] = object()
        custom = view.clip_planes.values['custom']
        navigation.set_navigation_clip(view, (1, 2, 3))
        self.assertEqual(set(view.clip_planes.values), {'near', 'far', 'custom'})
        self.assertIs(view.clip_planes.values['custom'], custom)

    def test_invalid_targets_do_not_modify_clipping(self):
        for centre, coords in (((float('nan'), 0, 0), None), ((0, 0, 0), [(0, float('inf'), 0)])):
            view = self.clip_view()
            with self.assertRaises(ValueError):
                navigation.set_navigation_clip(view, centre, coords)
            self.assertFalse(view.clip_planes.values)

    def test_range_navigation_selects_without_editing_colours_or_visibility(self):
        class ProtectedResidue:
            @property
            def color(self):
                return (10, 20, 30, 255)
            @property
            def ribbon_color(self):
                return (40, 50, 60, 255)
            @property
            def display(self):
                return False
            @property
            def ribbon_display(self):
                return False
        class Bounds:
            def __init__(self, lo, hi):
                self.xyz_min, self.xyz_max = np.array(lo), np.array(hi)
            def center(self):
                return (self.xyz_min+self.xyz_max)/2
        bounds = Bounds((-1, -2, -3), (3, 4, 5))
        atoms = SimpleNamespace(scene_bounds=bounds,
                                scene_coords=np.array([bounds.xyz_min, bounds.xyz_max]), selected=False)
        view = View('center of view')
        view.view_all = Mock()
        view.camera = SimpleNamespace(view_direction=lambda: (0, 0, -1))
        view.clip_planes = Planes()
        clear = Mock()
        session = SimpleNamespace(main_view=view, selection=SimpleNamespace(clear=clear))
        atomic = ModuleType('chimerax.atomic')
        atomic.concatenate = lambda _arrays: atoms
        geometry = ModuleType('chimerax.geometry')
        geometry.Bounds = Bounds
        residue = ProtectedResidue()
        residue.atoms = atoms
        with patch.dict(sys.modules, {'chimerax': ModuleType('chimerax'),
                                     'chimerax.atomic': atomic, 'chimerax.geometry': geometry}):
            regions.navigate_to_region(session, [residue])
        clear.assert_called_once()
        self.assertIs(atoms.selected, True)
        self.assertEqual(view.center_of_rotation_method, 'center of view')
        self.assertEqual(residue.ribbon_color, (40, 50, 60, 255))
        self.assertFalse(residue.display)

    def test_preserves_each_mode_and_retains_new_pivot(self):
        for mode in ('fixed', 'center of view', 'front center'):
            view = View(mode)
            indicator = view.indicator
            with navigation.preserve_cofr_mode(SimpleNamespace(main_view=view)):
                view.center_of_rotation = (10, 20, 30)
            self.assertEqual(view.center_of_rotation_method, mode)
            self.assertEqual(view.center_of_rotation, (10, 20, 30))
            self.assertIs(view.indicator, indicator)

    def test_mode_is_restored_if_navigation_raises(self):
        view = View('center of view')
        with self.assertRaisesRegex(ValueError, 'navigation failed'):
            with navigation.preserve_cofr_mode(SimpleNamespace(main_view=view)):
                view.center_of_rotation = (1, 2, 3)
                raise ValueError('navigation failed')
        self.assertEqual(view.center_of_rotation_method, 'center of view')

    def test_unchanged_mode_does_not_trigger_a_recompute(self):
        class UnchangedView:
            @property
            def center_of_rotation_method(self):
                return 'center of view'
            @center_of_rotation_method.setter
            def center_of_rotation_method(self, _method):
                raise AssertionError('Unnecessary mode reset')
        with navigation.preserve_cofr_mode(SimpleNamespace(main_view=UnchangedView())):
            pass

    def test_residue_navigation_restores_mode_on_normal_and_fallback_paths(self):
        tree = ast.parse((ROOT/'src/tool.py').read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == 'ResidueNotesTool')
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                      and node.name == '_goto_residue_with_context')
        for mode in ('fixed', 'center of view', 'front center'):
            for fail_zoom in (False, True):
                view = View(mode)
                calls = []
                def run(_session, command):
                    calls.append(command)
                    if command.startswith('view'):
                        view.center_of_rotation_method = 'center of view'
                    if command.startswith('cofr'):
                        view.center_of_rotation = (10, 20, 30)
                    if fail_zoom and command.startswith('zoom'):
                        raise RuntimeError('test fallback')
                ns = dict(run=run, preserve_cofr_mode=navigation.preserve_cofr_mode)
                exec(compile(ast.Module(body=[method], type_ignores=[]), 'residue navigation', 'exec'), ns)
                residue = SimpleNamespace(atoms=[object() for _ in range(8)], atomspec='#1/A:10')
                ns[method.name](SimpleNamespace(session=SimpleNamespace(main_view=view)), residue)
                self.assertEqual(view.center_of_rotation_method, mode)
                self.assertTrue(any(command.startswith('view') for command in calls))


if __name__ == '__main__':
    unittest.main()
