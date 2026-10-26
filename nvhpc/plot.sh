#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd -P)"
VENV_DIR="${SCRIPT_DIR}/.plotting-venv"
REQUIREMENTS="${SCRIPT_DIR}/requirements-plotting.txt"
REQUIREMENTS_HASH="$(sha256sum "${REQUIREMENTS}" | cut -d ' ' -f 1)"
INSTALLED_HASH_FILE="${VENV_DIR}/.requirements.sha256"

if ! command -v python3 >/dev/null 2>&1; then
    printf 'Error: python3 is required to run the MPAS plotting utility.\n' >&2
    exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    python3 -m venv "${VENV_DIR}"
fi

# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

INSTALLED_HASH=""
if [[ -r "${INSTALLED_HASH_FILE}" ]]; then
    IFS= read -r INSTALLED_HASH < "${INSTALLED_HASH_FILE}" || true
fi

if [[ "${INSTALLED_HASH}" != "${REQUIREMENTS_HASH}" ]]; then
    if [[ -n "${INSTALLED_HASH}" ]] || ! python -c \
        'import cartopy, matplotlib, netCDF4, numpy, xarray' >/dev/null 2>&1; then
        python -m pip install -r "${REQUIREMENTS}"
    fi
    printf '%s\n' "${REQUIREMENTS_HASH}" > "${INSTALLED_HASH_FILE}"
elif ! python -c 'import cartopy, matplotlib, netCDF4, numpy, xarray' \
    >/dev/null 2>&1; then
    python -m pip install -r "${REQUIREMENTS}"
fi

exec python "${SCRIPT_DIR}/plot_mpas.py" "$@"
