#!/usr/bin/env bash

# Absolute script path; resolves directory symlinks, but not a symlink to the script itself.
BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd -P)"

# Get the ufs-weather-model
if [[ ! -d ufs-weather-model ]]; then
  git clone --recursive https://github.com/christopherwharrop-noaa/ufs-weather-model.git
fi

# Patch it
tar -xzvf ${BASE_DIR}/nvhpc_ufs_working_changes.tar.gz

# Create and enter build dir
BUILD_DIR=${BASE_DIR}/build
rm -rf ${BUILD_DIR}
mkdir -p ${BUILD_DIR}
cd ${BUILD_DIR}

# Load nvhpc module
module purge
module use ${BASE_DIR}/opt/nvhpc/modulefiles
module load nvhpc-hpcx/26.9
export NVHPC_CUDA_HOME=$CUDA_ROOT

# Load spack environment
. ${BASE_DIR}/opt/spack/share/spack/setup-env.sh
spack env activate moonshot

# Show loaded modules
module list

# Set compilers
export MPI_CC=mpicc
export MPI_CXX=mpicxx
export MPI_FC=mpifort
export FC=mpifort
export CC=mpicc
export CXX=mpicxx
export FC=mpifort
export FC=mpifort

# Path to the ufs-weather-model clone
UFS_WEATHER_MODEL_DIR=${BASE_DIR}/ufs-weather-model

# Required CMake options
CMAKE_OPTS="-DAPP=ATMMPAS -DCCPP_SUITES=MPAS_RRFS -D32BIT=ON -DMPI=ON -DCMAKE_BUILD_TYPE=Release"
export ESMF_ROOT=$(spack location -i esmf)
echo $CMAKE_PREFIX_PATH

# Number of parallel build procs to use
BUILD_JOBS=1

# Build the code
cmake ${UFS_WEATHER_MODEL_DIR} ${CMAKE_OPTS}
make -j ${BUILD_JOBS} VERBOSE=1
