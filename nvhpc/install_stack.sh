#!/usr/bin/env bash

set -e

# Absolute script path; resolves directory symlinks, but not a symlink to the script itself.
BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd -P)"

# Install spack
if [[ ! -d opt/spack ]]; then
  git clone --depth=2 https://github.com/spack/spack.git opt/spack
fi
. opt/spack/share/spack/setup-env.sh

# Create moonshot environment
if [[ ! -d opt/spack/var/spack/environments/moonshot ]]; then
  spack env create moonshot
fi
spack env activate moonshot

# Load the compilers
module use opt/nvhpc/modulefiles
module load nvhpc-hpcx/26.9
module load gcc/12.4.0

# Find the gcc compiler
gcc_path=$(dirname $(which gcc))
gcc_prefix=$(dirname $gcc_path)

echo "Found gcc: ${gcc_path}"

cat <<EOF > opt/spack/var/spack/environments/moonshot/spack.yaml
spack:
  # add package specs to the "specs" list
  specs:
  - cmake@3.30.9
  - hdf5@1.14.3
  - netcdf-c@4.9.2
  - netcdf-fortran@4.6.1
  - parallelio@2.6.2 +fortran~ipo~logging+mpi~ncint+pnetcdf+shared~timing
  - esmf@8.8.0 ~debug~external-lapack+external-parallelio+mpi+netcdf~pnetcdf+python+shared
    # - fms@2025.03 +gfs_phys+internal_file_nml~ipo~large_file+openmp+pic~portable_kinds~quad_precision~shared~yaml precision:=32,64
  - fms@2026.02 +gfs_phys+internal_file_nml~ipo~large_file+openmp+pic~portable_kinds~quad_precision~shared~yaml precision:=32,64
  - sp@2.5.0
  - w3emc@2.10.0 precision:=4,8,d
  view: true
  concretizer:
    unify: true
  packages:
    c:
      prefer:
      - nvhpc@26.9  # This makes it the system-wide default for this env
    cxx:
      prefer:
      - nvhpc@26.9  # This makes it the system-wide default for this env
    fortran:
      prefer:
      - nvhpc@26.9  # This makes it the system-wide default for this env
    nvhpc:
      externals:
      - spec: nvhpc@26.9~blas~lapack~mpi
        prefix: ${NVHPC_ROOT}/compilers
        extra_attributes:
          compilers:
            c: ${NVHPC_ROOT}/compilers/bin/nvc
            cxx: ${NVHPC_ROOT}/compilers/bin/nvc++
            fortran: ${NVHPC_ROOT}/compilers/bin/nvfortran
    gcc:
      externals:
      - spec: gcc@12.4.0 languages:='c,c++,fortran'
        prefix: ${gcc_prefix}
        extra_attributes:
          compilers:
            c: ${gcc_path}/gcc
            cxx: ${gcc_path}/g++
            fortran: ${gcc_path}/gfortran

    openmpi:
      externals:
      - spec: openmpi@5.0.10rc2%nvhpc@26.9    # Match the version bundled in your 26.9 HPC-X module
        prefix: ${NVHPC_ROOT}/comm_libs/13.3/hpcx/hpcx-2.50/ompi5
      buildable: false # Prevents Spack from overriding this and compiling its own Open MPI
    zstd:
      require:
      - '@1.5.6 %gcc@12.4.0'
    libiconv:
      require:
      - '@1.17 %gcc@12.4.0'
    diffutils:
      require:
      - '@3.8 %gcc@12.4.0'
    gettext:
      require:
      - '@0.22.5 %gcc@12.4.0'
    libmd:
      require:
      - '@1.0.4  %gcc@12.4.0'
    libffi:
      require:
      - '@3.4.6 %gcc@12.4.0'
    py-cython:
      require:
      - '@3.0.11 %gcc@12.4.0'
    ninja:
      require:
      - '@1.12.1 %gcc@12.4.0'
    py-mpi4py:
      require:
      - '@4.0.1%gcc@12.4.0'
    py-numpy:
      require:
      - '@1.26.4%gcc@12.4.0'
    m4:
      require:
      - '%gcc@12.4.0'
    libxcrypt:
      require:
      - '%gcc@12.4.0'
    bacio:
      require:
      - '@2.4.1'
#   repos:
#     builtin:
#       destination: ${PWD}/opt/spack-packages
  develop:
    fms:
      spec: fms@=2026.02
EOF

# For now, we have to patch FMS for nvhpc compatibility
spack develop fms@2026.02
FMS_source=$(spack location -c fms)
echo "Develop path for FMS: ${FMS_source}"
cd ${FMS_source}
if patch --dry-run --reverse -p1 < "${BASE_DIR}/nvhpc_compatibility.patch" >/dev/null 2>&1; then
  echo "NVHPC compatibility patch is already applied; skipping"
else
  patch -p1 < "${BASE_DIR}/nvhpc_compatibility.patch"
fi

# Concretize and install
spack concretize -f
spack install
