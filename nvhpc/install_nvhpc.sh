#!/usr/bin/env bash

set -e

# Run this script from the directory where you want the installer files and
# the local opt/ installation directory to be created.
# Remove the tarball and extracted installer only after a successful install;
# retain them if any installation step fails.
# Download the NVHPC 26.9 Linux x86_64 CUDA multi tarball if it is not already
# present in the current directory.
if [[ ! -f nvhpc_2026_269_Linux_x86_64_cuda_multi.tar.gz ]]; then
  wget https://developer.download.nvidia.com/hpc-sdk/26.9/nvhpc_2026_269_Linux_x86_64_cuda_multi.tar.gz
  echo
fi

# Unpack the installer into the current directory.
tar -xpzf nvhpc_2026_269_Linux_x86_64_cuda_multi.tar.gz

# Create the installation target under the current directory.
mkdir -p ./opt/nvhpc

# Configure a silent, single-target installation at the absolute path derived
# from the current working directory.
export NVHPC_SILENT="true"
export NVHPC_INSTALL_DIR="$PWD/opt/nvhpc"
export NVHPC_INSTALL_TYPE="single"

# Run the installer extracted from the tarball.
nvhpc_2026_269_Linux_x86_64_cuda_multi/install

rm -f nvhpc_2026_269_Linux_x86_64_cuda_multi.tar.gz
rm -rf nvhpc_2026_269_Linux_x86_64_cuda_multi
