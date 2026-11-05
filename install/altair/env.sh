# Environment for the Waveform-Editor + NICE (inverse & direct, IMAS + MUSCLE3)
# installation on altair (CEA cluster). Usage (bash):
#
#     source <installation>/env.sh
#     waveform-editor gui
#
# NB: this purges your currently loaded modules. install.sh copies this file to the
# root of the installation, which it then finds from its own location.

export WFE_NICE_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

type module > /dev/null 2>&1 || source /etc/profile.d/modules.sh
module purge
module load mamba/python-3.11 gcc/13.2.0 hdf5/1.8.12-gcc-13.2.0 uda/2.8.1 \
    blitz/1.0.2-gcc-13.2.0 papi/5.7.0-gcc-13.2.0 mdsplus/7.131.5-gcc-13.2.0 \
    lapack/3.9.1-gcc-13.2.0 IMAS/4.1.0-5.4.3-python-3.11-hdf5-1.8.12-gcc-13.2.0

# MUSCLE3 C++ libraries (built from source)
export PKG_CONFIG_PATH=$WFE_NICE_ROOT/deps/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}
export LD_LIBRARY_PATH=$WFE_NICE_ROOT/deps/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
# SuiteSparse built inside the NICE source tree
export LD_LIBRARY_PATH=$WFE_NICE_ROOT/nice/external/SuiteSparse/lib:$LD_LIBRARY_PATH

# NICE executables (nice_imas_inv_muscle3, nice_imas_dir_muscle3)
export PATH=$WFE_NICE_ROOT/nice/run:$PATH

# Headless Chrome used by kaleido for PNG export (installed with plotly_get_chrome)
export BROWSER_PATH=$WFE_NICE_ROOT/chrome/chrome-linux64/chrome

# Python environment with the Waveform-Editor (skipped while building it)
if [ -f "$WFE_NICE_ROOT/venv/bin/activate" ]; then
    source "$WFE_NICE_ROOT/venv/bin/activate"
fi
