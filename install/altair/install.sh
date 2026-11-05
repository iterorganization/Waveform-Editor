#!/bin/bash
# Install the Waveform-Editor + NICE (inverse & direct, IMAS + MUSCLE3) from scratch on
# altair (CEA cluster). See README.md next to this script.
#
# Usage: bash install/altair/install.sh [INSTALL_DIR]
#   INSTALL_DIR defaults to ~/public/waveform-editor-nice and must not exist yet.
#   The Waveform-Editor is cloned from the repository this script is in, at the last
#   commit of its current branch (or of WFE_BRANCH): uncommitted changes are not
#   included. Takes about 30 min and needs ~4 GB in the home quota.
set -eo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SRC=$(git -C "$HERE" rev-parse --show-toplevel)
R=${1:-$HOME/public/waveform-editor-nice}
WFE_BRANCH=${WFE_BRANCH:-$(git -C "$SRC" branch --show-current)}
NICE_REPO=${NICE_REPO:-https://gitlab.inria.fr/blfauger/nice.git}
NICE_COMMIT=${NICE_COMMIT:-36d11a69cf33c09ce5e4ad08a4bff12ca310b9c1}
# The C++ library NICE links to and the Python package must be the same version
MUSCLE3_VERSION=0.10.0

if [ -e "$R" ] && [ -n "$(ls -A "$R")" ]; then
    echo "error: $R exists and is not empty; move or delete it first" >&2
    exit 1
fi
if [ -n "$(git -C "$SRC" status --porcelain --untracked-files=no -- install waveform_editor)" ]; then
    echo "warning: uncommitted changes in $SRC are not installed, only the last" \
        "commit of $WFE_BRANCH" >&2
fi

step() { echo "== $(date +%H:%M:%S) $*"; }
source "$HERE/permissions.sh"

step "Directories in $R"
mkdir -p "$R/src" "$R/logs" "$R/chrome"
R=$(cd "$R" && pwd)
L=$R/logs

step "Sources: NICE $NICE_COMMIT, Waveform-Editor $WFE_BRANCH, MUSCLE3 $MUSCLE3_VERSION"
git clone -q "$NICE_REPO" "$R/nice"
git -C "$R/nice" checkout -q "$NICE_COMMIT"
git -C "$R/nice" submodule update --init --depth 1 > "$L/nice_submodules.log" 2>&1
git clone -q --branch "$WFE_BRANCH" "$SRC" "$R/Waveform-Editor"
wget -q -P "$R/src" "https://github.com/multiscale/muscle3/archive/$MUSCLE3_VERSION/muscle3-$MUSCLE3_VERSION.tar.gz"
tar -C "$R/src" -xf "$R/src/muscle3-$MUSCLE3_VERSION.tar.gz"

step "Machine descriptions on altair"
bash "$HERE/set_machine_descriptions.sh" "$R/Waveform-Editor"

step "Environment and GUI launchers"
cp "$HERE/env.sh" "$HERE/start-gui-socket.sh" "$R/"
chmod +x "$R/start-gui-socket.sh"
cp -r "$HERE/windows" "$R/"
# The Windows launcher starts the GUI with the start-gui-socket.sh of this installation
sed -i "s#/home/MS013565/public/waveform-editor-nice#$R#g" "$R"/windows/*
# The module scripts may return non-zero statuses that are not errors
set +e
source "$R/env.sh"
set -e

step "MUSCLE3 C++ libraries"
cd "$R/src/muscle3-$MUSCLE3_VERSION"
make -j8 > "$L/muscle3_build.log" 2>&1
PREFIX=$R/deps make install >> "$L/muscle3_build.log" 2>&1

step "SuiteSparse (bundled in NICE)"
cd "$R/nice/external/SuiteSparse"
make BLAS=-lblas LAPACK=-llapack > "$L/suitesparse_build.log" 2>&1

step "NICE inverse and direct executables"
cd "$R/nice/src"
cp Makefile.TEMPLATE Makefile
sed -i 's/^CHOOSE_SYSTEM_SUITESPARSE = yes/CHOOSE_SYSTEM_SUITESPARSE = no/' Makefile
make -j16 lib > "$L/nice_build.log" 2>&1
make nice_imas_inv_muscle3 nice_imas_dir_muscle3 >> "$L/nice_build.log" 2>&1

step "Python environment with the Waveform-Editor"
cd "$R"
python -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install "./Waveform-Editor[test]" "muscle3==$MUSCLE3_VERSION" > "$L/venv_pip.log" 2>&1
pip check

step "Chrome for PNG export"
plotly_get_chrome -y --path "$R/chrome" > "$L/chrome_install.log" 2>&1

step "Permissions for colleagues"
share_path "$R"
check_shared "$R" || { echo "error: colleagues cannot use $R" >&2; exit 1; }

step "Check"
if ldd "$R/nice/run/nice_imas_inv_muscle3" "$R/nice/run/nice_imas_dir_muscle3" | grep "not found"; then
    echo "error: libraries of the NICE executables are missing" >&2
    exit 1
fi
waveform-editor --version
echo
echo "Done. To use it:  source $R/env.sh && waveform-editor gui"
