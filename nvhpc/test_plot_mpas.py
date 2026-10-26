"""Regression tests for MPAS level selection and periodic map geometry."""

import unittest

import numpy as np
import xarray as xr

from plot_mpas import _cell_coordinates, _field_values, _single_time, _triangulation


class PlotMpasTests(unittest.TestCase):
    def grid(self, cells):
        return xr.Dataset(
            {"cellsOnVertex": (("nVertices", "vertexDegree"), cells)}
        )

    def test_level_selection_is_zero_based(self):
        history = xr.Dataset(
            {"pressure": (("Time", "nCells", "nVertLevels"), [[[10, 20], [30, 40]]])}
        )
        values, _ = _field_values(history, "pressure", 0)
        np.testing.assert_array_equal(values, [10, 30])
        values, _ = _field_values(history, "pressure", 1)
        np.testing.assert_array_equal(values, [20, 40])
        for level in (-1, 2):
            with self.subTest(level=level):
                with self.assertRaisesRegex(ValueError, "out of range"):
                    _field_values(history, "pressure", level)

    def test_interface_level_selection_is_zero_based(self):
        history = xr.Dataset(
            {"w": (("Time", "nCells", "nVertLevelsP1"), [[[1, 2, 3], [4, 5, 6]]])}
        )
        values, _ = _field_values(history, "w", 0)
        np.testing.assert_array_equal(values, [1, 4])
        values, _ = _field_values(history, "w", 2)
        np.testing.assert_array_equal(values, [3, 6])
        with self.assertRaisesRegex(ValueError, "out of range"):
            _field_values(history, "w", 3)

    def test_single_time_record_is_selected(self):
        history = xr.Dataset({"value": ("Time", [42])})
        selected = _single_time(history)
        self.assertNotIn("Time", selected.dims)
        self.assertEqual(selected["value"].item(), 42)

    def test_empty_or_multiple_time_records_are_rejected(self):
        for count in (0, 2):
            with self.subTest(count=count):
                history = xr.Dataset({"value": ("Time", np.arange(count))})
                with self.assertRaisesRegex(ValueError, "exactly one time record"):
                    _single_time(history)

    def test_coordinates_wrap_without_mutating_grid(self):
        grid = xr.Dataset(
            {
                "latCell": ("nCells", [0.0, 0.5]),
                "lonCell": ("nCells", [0.0, 1.5 * np.pi]),
            }
        )
        original = grid.lonCell.values.copy()
        _, lon = _cell_coordinates(grid)
        np.testing.assert_allclose(lon, [0, -90])
        np.testing.assert_array_equal(grid.lonCell, original)

    def test_seam_triangles_are_retained_on_both_sides(self):
        values = np.array([10.0, 20.0, 30.0])
        mesh, colors = _triangulation(
            self.grid([[1, 2, 3]]),
            np.array([0.0, 1.0, 2.0]),
            np.array([179.0, -179.0, 178.0]),
            values,
        )
        self.assertEqual(mesh.triangles.shape, (2, 3))
        x = mesh.x[mesh.triangles]
        self.assertTrue(np.any((x.min(axis=1) < -180) & (x.max(axis=1) > -180)))
        self.assertTrue(np.any((x.min(axis=1) < 180) & (x.max(axis=1) > 180)))
        self.assertTrue(np.all(np.ptp(x, axis=1) < 180))
        np.testing.assert_array_equal(colors.reshape(-1, 3), [values, values])

    def test_interior_triangle_is_not_duplicated(self):
        mesh, colors = _triangulation(
            self.grid([[1, 2, 3]]),
            np.array([0.0, 1.0, 2.0]),
            np.array([10.0, 11.0, 9.0]),
            np.array([10.0, 20.0, 30.0]),
        )
        self.assertEqual(mesh.triangles.shape, (1, 3))
        np.testing.assert_array_equal(colors, [10, 20, 30])

    def test_pole_has_cap_edge_instead_of_point(self):
        for latitude in (-90.0, 90.0):
            with self.subTest(latitude=latitude):
                mesh, colors = _triangulation(
                    self.grid([[1, 2, 3]]),
                    np.array([latitude, latitude * 0.99, latitude * 0.99]),
                    np.array([118.0, -103.0, -31.0]),
                    np.array([10.0, 20.0, 30.0]),
                )
                pole_points = np.isclose(mesh.y, latitude)
                self.assertEqual(mesh.triangles.shape, (2, 3))
                self.assertEqual(np.ptp(mesh.x[pole_points]), 72)
                np.testing.assert_array_equal(colors[pole_points], 10)

    def test_missing_values_are_not_rendered(self):
        with self.assertRaisesRegex(ValueError, "No valid triangles"):
            _triangulation(
                self.grid([[1, 2, 3]]),
                np.array([0.0, 1.0, 2.0]),
                np.array([10.0, 11.0, 9.0]),
                np.array([10.0, np.nan, 30.0]),
            )


if __name__ == "__main__":
    unittest.main()
