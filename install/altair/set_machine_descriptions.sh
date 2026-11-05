#!/bin/bash
# Point the ITER and WEST machine description presets of a Waveform-Editor source tree
# from the SDCC data (/home/ITER/blokhus/...) to the copies on altair, and choose the
# default preset.
#
# Usage: set_machine_descriptions.sh [WAVEFORM_EDITOR_DIR]
#   WAVEFORM_EDITOR_DIR defaults to the repository this script is in.
#   The data locations and the default preset can be changed with the variables
#   ITER_MD, WEST_MD and DEFAULT_PRESET (ITER, WEST or CUSTOM).
set -eo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WFE_DIR=${1:-$(git -C "$HERE" rev-parse --show-toplevel)}
ITER_MD=${ITER_MD:-/home/MS013565/public/imasdb/ITER/4}
WEST_MD=${WEST_MD:-/home/MS013565/public/imasdb/WEST_MD/4/555/1}
DEFAULT_PRESET=${DEFAULT_PRESET:-WEST}
SETTINGS=$WFE_DIR/waveform_editor/settings.py

[ -f "$SETTINGS" ] || { echo "error: $SETTINGS not found" >&2; exit 1; }

# The SDCC data: ITER in .../ITER/4/{666666,111002}/3, WEST in .../west_test_dd4
sed -i \
    -e "s#/home/ITER/blokhus/public/imasdb/ITER/4/#$ITER_MD/#g" \
    -e "s#/home/ITER/blokhus/public/imasdb/west_test_dd4#$WEST_MD#g" \
    -e "s#machine_preset = param.Selector(default=PRESET_[A-Z]*,#machine_preset = param.Selector(default=PRESET_$DEFAULT_PRESET,#" \
    "$SETTINGS"

status=0
if grep -n "/home/ITER/" "$SETTINGS"; then
    echo "error: the paths above were not replaced; settings.py changed upstream?" >&2
    status=1
fi
if [ "$DEFAULT_PRESET" != CUSTOM ] && ! grep -q "self.set_machine_preset()" "$SETTINGS"; then
    echo "warning: settings.py does not apply the default preset at start-up," \
        "so its data stays empty until another preset is chosen" >&2
fi
source "$HERE/permissions.sh"
for d in "$ITER_MD/666666/3" "$ITER_MD/111002/3" "$WEST_MD"; do
    if [ ! -f "$d/master.h5" ]; then
        echo "warning: no machine description data in $d" >&2
    elif ! check_shared "$d"; then
        echo "warning: colleagues cannot read $d; its owner can fix it with:" \
            "chmod -R go+rX $d" >&2
    fi
done

echo "Machine descriptions in $SETTINGS:"
grep -nE "imas:hdf5|machine_preset = " "$SETTINGS"
exit $status
