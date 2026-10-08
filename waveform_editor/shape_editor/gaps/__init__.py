"""The gaps between a plasma and the machine around it, per machine."""

from waveform_editor.settings import NiceSettings
from waveform_editor.shape_editor.gaps.iter import IterGaps
from waveform_editor.shape_editor.gaps.west import WestGaps

# The gaps of each machine preset that has them
MACHINE_GAPS = {
    NiceSettings.PRESET_ITER: IterGaps(),
    NiceSettings.PRESET_WEST: WestGaps(),
}
