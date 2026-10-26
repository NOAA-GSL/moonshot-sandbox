#!/usr/bin/env python3
"""Plot a cell-centered field from an MPAS history NetCDF file."""

import argparse
from datetime import datetime
from pathlib import Path
import re
import sys

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    import numpy as np
    import xarray as xr
except ImportError as error:
    raise SystemExit(
        "Plotting dependencies are missing. Run this utility through "
        "`./plot.sh` to create and populate its virtual environment."
    ) from error


_HISTORY_TIME = re.compile(
    r"^history\.(\d{4}-\d{2}-\d{2}_\d{2}\.\d{2}\.\d{2})\.nc$"
)
_VERTICAL_DIMS = {"nVertLevels", "nVertLevelsP1"}


def _single_time(dataset):
    if "Time" in dataset.sizes:
        count = dataset.sizes["Time"]
        if count != 1:
            raise ValueError(
                f"Expected exactly one time record in the history file; found {count}."
            )
        return dataset.isel(Time=0)
    return dataset


def _valid_time(dataset, input_path):
    dataset = _single_time(dataset)
    if "xtime" in dataset:
        xtime = dataset["xtime"]
        value = np.asarray(xtime.values)
        if value.ndim == 0:
            value = value.item()
        if isinstance(value, (bytes, np.bytes_)):
            text = value.decode("ascii")
        elif isinstance(value, (str, np.str_)):
            text = str(value)
        else:
            text = b"".join(value.reshape(-1).tolist()).decode("ascii")
        text = text.strip(" \x00").replace("_", "T")
        try:
            return datetime.fromisoformat(text.replace(" ", "T")).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError as error:
            raise ValueError(f"Could not parse MPAS xtime value {text!r}.") from error

    match = _HISTORY_TIME.match(input_path.name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d_%H.%M.%S").strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError as error:
            raise ValueError(
                f"Could not parse timestamp in {input_path.name!r}."
            ) from error
    raise ValueError(
        "The file has no xtime variable and its name does not contain an "
        "MPAS history timestamp."
    )


def _field_values(dataset, variable, level):
    dataset = _single_time(dataset)
    if variable not in dataset:
        available = ", ".join(dataset.data_vars)
        raise ValueError(
            f"Variable {variable!r} was not found. Available data variables: "
            f"{available}"
        )

    field = dataset[variable]
    vertical_dims = [dim for dim in field.dims if dim in _VERTICAL_DIMS]
    if vertical_dims:
        if len(vertical_dims) != 1:
            raise ValueError(
                f"Variable {variable!r} has multiple vertical dimensions: "
                f"{vertical_dims}."
            )
        if level is None:
            raise ValueError(
                f"Variable {variable!r} has vertical levels; specify --level "
                "(level indices are numbered starting at 0)."
            )
        vertical_dim = vertical_dims[0]
        if not 0 <= level < field.sizes[vertical_dim]:
            raise ValueError(
                f"Level index {level} is out of range for {variable!r} "
                f"(0-{field.sizes[vertical_dim] - 1})."
            )
        field = field.isel({vertical_dim: level})
    elif level is not None:
        raise ValueError(f"Variable {variable!r} has no vertical level dimension.")

    field = field.squeeze()
    if field.dims != ("nCells",):
        raise ValueError(
            f"Expected {variable!r} to contain one value per MPAS cell after "
            f"selecting time and level; remaining dimensions are {field.dims}."
        )
    return np.asarray(field.values), field.attrs


def _cell_coordinates(dataset):
    for name in ("latCell", "lonCell"):
        if name not in dataset:
            raise ValueError(f"MPAS mesh coordinate {name!r} is missing.")
    lat = np.array(dataset["latCell"].values, dtype=float, copy=True)
    lon = np.array(dataset["lonCell"].values, dtype=float, copy=True)
    for name, coordinate in (("latCell", lat), ("lonCell", lon)):
        units = str(dataset[name].attrs.get("units", "")).lower()
        if "degree" in units:
            continue
        coordinate *= 180.0 / np.pi
    lon = (lon + 180.0) % 360.0 - 180.0
    if not np.all(np.isfinite(lat)) or not np.all(np.isfinite(lon)):
        raise ValueError("MPAS cell coordinates contain non-finite values.")
    return lat, lon


def _triangulation(dataset, lat, lon, values):
    if "cellsOnVertex" not in dataset:
        raise ValueError("MPAS mesh connectivity variable 'cellsOnVertex' is missing.")

    connectivity = dataset["cellsOnVertex"]
    cells = np.asarray(connectivity.values)
    if "vertexDegree" in connectivity.dims:
        axis = connectivity.dims.index("vertexDegree")
        cells = np.moveaxis(cells, axis, -1)
    if cells.ndim != 2 or cells.shape[1] != 3:
        raise ValueError(
            "Expected cellsOnVertex to contain three cell indices per vertex."
        )

    valid = np.all(cells > 0, axis=1)
    triangles = cells[valid].astype(np.int64) - 1
    if triangles.size == 0 or np.any(triangles >= values.size):
        raise ValueError("MPAS mesh connectivity contains no valid cell triangles.")

    triangles = triangles[np.all(np.isfinite(values[triangles]), axis=1)]
    if triangles.size == 0:
        raise ValueError("No valid triangles remain to plot.")

    triangle_lons = lon[triangles]
    triangle_lats = np.clip(lat[triangles], -90.0, 90.0)
    triangle_values = values[triangles]
    at_pole = np.isclose(np.abs(triangle_lats), 90.0, rtol=0, atol=1e-5)
    reference = triangle_lons[
        np.arange(triangles.shape[0]), np.argmin(at_pole, axis=1)
    ][:, None]
    triangle_lons = reference + (triangle_lons - reference + 180.0) % 360.0 - 180.0

    # A pole represents every longitude; expand its point into a cap edge.
    polar_rows = np.flatnonzero(np.any(at_pole, axis=1))
    extra_lons, extra_lats, extra_values = [], [], []
    for row in polar_rows:
        pole = np.flatnonzero(at_pole[row])[0]
        left, right = [index for index in range(3) if index != pole]
        triangle_lons[row, pole] = triangle_lons[row, left]
        extra_lons.append(
            [triangle_lons[row, left], triangle_lons[row, right],
             triangle_lons[row, right]]
        )
        extra_lats.append(
            [triangle_lats[row, pole], triangle_lats[row, right],
             triangle_lats[row, pole]]
        )
        extra_values.append(
            [triangle_values[row, pole], triangle_values[row, right],
             triangle_values[row, pole]]
        )
    if polar_rows.size:
        triangle_lons = np.concatenate((triangle_lons, extra_lons))
        triangle_lats = np.concatenate((triangle_lats, extra_lats))
        triangle_values = np.concatenate((triangle_values, extra_values))

    # Retain seam-crossing triangles on both sides and let the map clip them.
    plot_lons, plot_lats, plot_values = [], [], []
    for offset in (-360.0, 0.0, 360.0):
        shifted = triangle_lons + offset
        visible = (shifted.max(axis=1) > -180.0) & (shifted.min(axis=1) < 180.0)
        plot_lons.append(shifted[visible])
        plot_lats.append(triangle_lats[visible])
        plot_values.append(triangle_values[visible])

    plot_lons = np.concatenate(plot_lons).ravel()
    plot_lats = np.concatenate(plot_lats).ravel()
    plot_values = np.concatenate(plot_values).ravel()
    plot_triangles = np.arange(plot_values.size).reshape(-1, 3)
    triangulation = mtri.Triangulation(plot_lons, plot_lats, plot_triangles)
    return triangulation, plot_values


def _output_path(input_path, variable, level):
    suffix = f"_level-{level}" if level is not None else ""
    return input_path.with_name(f"{input_path.stem}_{variable}{suffix}.png")


def main():
    parser = argparse.ArgumentParser(
        description="Plot a cell-centered field from an MPAS history file."
    )
    parser.add_argument("input", type=Path, help="MPAS history NetCDF file")
    parser.add_argument("variable", help="Cell-centered variable to plot")
    parser.add_argument(
        "--grid",
        type=Path,
        help=(
            "MPAS grid NetCDF file (default: x1.40962.init.nc next to the "
            "history file)"
        ),
    )
    parser.add_argument(
        "--level",
        type=int,
        help="0-based vertical level index to plot (required for 3-D fields)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="PNG output path (default: next to the input file)",
    )
    parser.add_argument(
        "--no-map-features",
        action="store_true",
        help="Omit coastlines and country borders (useful without network access)",
    )
    args = parser.parse_args()

    if args.level is not None and args.level < 0:
        parser.error("--level must be 0 or greater.")
    if not args.input.is_file():
        parser.error(f"Input file does not exist: {args.input}")
    grid_path = args.grid or args.input.parent / "x1.40962.init.nc"
    if not grid_path.is_file():
        parser.error(
            f"MPAS grid file does not exist: {grid_path}. Pass its location "
            "with --grid."
        )

    with xr.open_dataset(args.input, decode_times=False) as history, xr.open_dataset(
        grid_path, decode_times=False
    ) as grid:
        valid_time = _valid_time(history, args.input)
        values, attributes = _field_values(
            history, args.variable, args.level
        )
        lat, lon = _cell_coordinates(grid)
        if values.size != lat.size:
            raise ValueError(
                f"Variable {args.variable!r} has {values.size} values but the "
                f"mesh has {lat.size} cells."
            )
        triangulation, plot_values = _triangulation(grid, lat, lon, values)

        figure, axes = plt.subplots(
            figsize=(14, 7),
            subplot_kw={"projection": ccrs.PlateCarree()},
            layout="constrained",
        )
        # PlateCarree data coordinates keep wrapped copies outside the map
        # until clipping; a geographic transform would wrap them back again.
        mesh = axes.tripcolor(
            triangulation,
            plot_values,
            shading="gouraud",
            cmap="viridis",
        )
        axes.set_global()
        if not args.no_map_features:
            axes.coastlines(color="black", linewidth=0.5)
            axes.add_feature(
                cfeature.BORDERS,
                edgecolor="black",
                linewidth=0.35,
            )

        label = str(attributes.get("long_name", args.variable.replace("_", " ")))
        label = label[:1].upper() + label[1:]
        level_label = f", level index {args.level}" if args.level is not None else ""
        axes.set_title(
            f"{label}{level_label} for MPAS forecast, {valid_time}"
        )
        units = attributes.get("units")
        colorbar = figure.colorbar(mesh, ax=axes, shrink=0.85, pad=0.04)
        if units:
            colorbar.set_label(f"Units: {units}")

        output = args.output or _output_path(args.input, args.variable, args.level)
        figure.savefig(output, dpi=150)
        plt.close(figure)

    print(f"Saved plot to {output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        sys.exit(f"Error: {error}")
