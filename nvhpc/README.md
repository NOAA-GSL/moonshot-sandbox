# Running the NVHPC Test Case

1. Install the nvhpc compiler

   ```sh
   ./install_nvhpc.sh
   ```

2. Install the dependencies

   ```sh
   ./install_stack.sh
   ```

   Occasionally, Spack glitches can cause transient failures during fetches/builds.
   If this happens, just run the install script again.

3. Build the ufs-weather-model test case

   ```sh
   ./build.sh
   ```

4. Run the test case

   ```sh
   sbatch ./run.sh $PWD
   ```

## Plotting MPAS output

The plotting utility reads cell-centered fields and valid time from an MPAS
history file, and cell coordinates and mesh connectivity from the grid file
`x1.40962.init.nc`. The grid file is expected next to the history file by
default; use `--grid path/to/grid.nc` if it is elsewhere.
Plotting uses a separate Python virtual environment and does not require
activating the `moonshot` Spack environment. The first run creates the
environment and installs the plotting packages listed in
`requirements-plotting.txt`. Later runs reuse the environment and skip package
installation unless the requirements change or a required package is missing.
It requires Python 3 with `venv` support and, when packages need installing,
access to the configured Python package index.

For example, to plot pressure at vertical level index 32 from a completed run:

```sh
./plot.sh run/history.2023-03-10_18.00.00.nc pressure --level 32
```

The PNG is saved next to the NetCDF file by default. Use `--output path.png` to
choose a different location. 
Level indices are 0-based: `--level 0` selects the first (lowest) layer.
Coastlines and country borders are shown by default;
use `--no-map-features` to omit them when Natural Earth map data is unavailable.
