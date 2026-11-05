#!/bin/bash
# Update the Waveform-Editor of an existing installation made by install.sh, without
# rebuilding NICE and MUSCLE3. See README.md next to this script.
#
# Usage: bash install/altair/update.sh [INSTALL_DIR]
#   INSTALL_DIR defaults to ~/public/waveform-editor-nice.
#   Installs the last commit of the current branch of the repository this script is
#   in (or of WFE_BRANCH): uncommitted changes are not included.
set -eo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SRC=$(git -C "$HERE" rev-parse --show-toplevel)
R=$(cd "${1:-$HOME/public/waveform-editor-nice}" && pwd)
WFE_BRANCH=${WFE_BRANCH:-$(git -C "$SRC" branch --show-current)}

[ -f "$R/venv/bin/activate" ] || { echo "error: no installation in $R" >&2; exit 1; }
if [ -n "$(git -C "$SRC" status --porcelain --untracked-files=no -- install waveform_editor)" ]; then
    echo "warning: uncommitted changes in $SRC are not installed, only the last" \
        "commit of $WFE_BRANCH" >&2
fi

step() { echo "== $(date +%H:%M:%S) $*"; }
source "$HERE/permissions.sh"

step "Waveform-Editor: $WFE_BRANCH of $SRC"
# The previous machine description change is discarded, and made again below
git -C "$R/Waveform-Editor" fetch -q --tags "$SRC" "$WFE_BRANCH"
git -C "$R/Waveform-Editor" checkout -q -f FETCH_HEAD
git -C "$R/Waveform-Editor" log --oneline -1

step "Machine descriptions on altair"
bash "$HERE/set_machine_descriptions.sh" "$R/Waveform-Editor"

step "Environment and GUI launchers"
cp "$HERE/env.sh" "$HERE/start-gui-socket.sh" "$R/"
chmod +x "$R/start-gui-socket.sh"
cp -r "$HERE/windows" "$R/"
sed -i "s#/home/MS013565/public/waveform-editor-nice#$R#g" "$R"/windows/*
set +e
source "$R/env.sh"
set -e

step "Reinstall in the Python environment"
log=$R/logs/venv_pip_update_$(date +%Y%m%d_%H%M).log
# Dependencies are only added when the new version needs them; muscle3 stays pinned
pip install "$R/Waveform-Editor[test]" "muscle3==0.10.0" > "$log" 2>&1
pip check

step "Permissions for colleagues"
share_path "$R"
check_shared "$R" || { echo "error: colleagues cannot use $R" >&2; exit 1; }
waveform-editor --version
