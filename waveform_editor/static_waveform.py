import numpy as np

from waveform_editor.base_waveform import BaseWaveform


class StaticWaveform(BaseWaveform):
    """A waveform that assigns a single static value to a DD node.

    Used for non-numeric or non-time-dependent fields, e.g. a ``{value: ec}`` constant
    that names an identifier. The value is written verbatim by the exporter; it is not a
    time series and has no analytic tendencies.
    """

    def __init__(self, value, *, yaml_str="", name="waveform", dd_version=None):
        super().__init__(yaml_str, name, dd_version)
        self.yaml_str = yaml_str
        self.value = value

    def get_value(
        self, time: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        # A static value is not a time series; nothing to plot.
        if time is None:
            time = np.array([])
        return time, np.zeros_like(time, dtype=float)

    def get_yaml_string(self) -> str:
        return self.yaml_str
