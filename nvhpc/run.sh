#!/usr/bin/env bash
#SBATCH -e err
#SBATCH -o out
#SBATCH --account=gpu-ghpcs
#SBATCH --qos=gpu
#SBATCH --nodes=1
#SBATCH --partition=u1-h100
#SBATCH --ntasks-per-node=12
#SBATCH --cpus-per-task=1
#SBATCH --time=30
#SBATCH --job-name="run_control_gfs_mpas_gnu"

#salloc --time=8:00:00 -A gpu-ghpcs -p u1-h100 -q gpu --gpus=h100:1

if [ "$#" -ne 1 ]; then
    printf 'Usage: %s /absolute/path/to/BASE_DIR\n' "$0" >&2
    exit 1
fi

case "$1" in
    /*) ;;
    *)
        printf 'Error: BASE_DIR must be an absolute path.\n' >&2
        exit 1
        ;;
esac

BASE_DIR="$1"

if [ ! -d "${BASE_DIR}" ]; then
    printf 'Error: BASE_DIR is not a directory: %s\n' "${BASE_DIR}" >&2
    exit 1
fi

# Create and enter run dir
RUN_DIR="${BASE_DIR}/run"
rm -rf -- "${RUN_DIR}"
mkdir -p -- "${RUN_DIR}" || exit 1
cd -- "${RUN_DIR}" || exit 1

# Copy baseline input and executable
cp -prd "${BASE_DIR}"/../baseline_input/* .
cp -prd "${BASE_DIR}/build/ufs_model" .

# Load nvhpc module
module purge
module use "${BASE_DIR}/opt/nvhpc/modulefiles"
module load nvhpc-hpcx/26.9
export NVHPC_CUDA_HOME=$CUDA_ROOT

# Load spack environment
. "${BASE_DIR}/opt/spack/share/spack/setup-env.sh"
spack env activate moonshot

# Show loaded modules
module list

# Set runtime variables
export MPI_TYPE_DEPTH=20
export OMP_STACKSIZE=512M
export OMP_NUM_THREADS=1
export ESMF_RUNTIME_COMPLIANCECHECK=OFF:depth=4
export ESMF_RUNTIME_PROFILE=ON
export ESMF_RUNTIME_PROFILE_OUTPUT="SUMMARY"
export PSM_RANKS_PER_CONTEXT=4
export PSM_SHAREDCONTEXTS=1

# Avoid job errors because of filesystem synchronization delays
sync && sleep 1

# Run
#srun --label --distribution=block:block -n 12 ./ufs_model
mpiexec -n 12 ./ufs_model
#srun --mpi=pmix --label --distribution=block:block -n 12 ./ufs_model
