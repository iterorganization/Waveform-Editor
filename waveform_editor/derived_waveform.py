import re
from typing import Optional

import numpy as np

from waveform_editor.annotations import Annotations


class DerivedWaveform:
    def __init__(self, waveform=None, name="", config=None):
        self.dependent_waveforms = []
        self.name = name
        self.tendencies = None
        self.yaml = waveform
        self.config = config
        self.annotations = Annotations()

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        # pattern matches waveform names
        pattern = r"\b[A-Za-z0-9_()/]+(?:/[A-Za-z0-9_()/]+)+\b"
        matches = re.findall(pattern, self.yaml)

        # filter matches that are actual waveform paths
        var_map = {}
        for i, m in enumerate(matches):
            if m == self.name:
                error_msg = "Derived waveforms cannot depend on itself! \n"
                self.annotations.add(0, error_msg)
                return np.array([self.start, self.end]), np.array([0, 0])
            if m in self.config.waveform_map:
                var_name = f"var_{i}"
                var_map[m] = var_name
            else:
                error_msg = f"Waveform {m!r} does not exist! \n"
                self.annotations.add(0, error_msg)
                return np.array([self.start, self.end]), np.array([0, 0])

        # prepare a dict of variables to pass to eval
        eval_locals = {}
        for path, var_name in var_map.items():
            dependent_waveform = self.config[path]
            self.start = dependent_waveform.tendencies[0].start
            self.end = dependent_waveform.tendencies[-1].end
            # TODO: properly handle time
            if time is None:
                time = np.linspace(self.start, self.end, 1000)

            eval_locals[var_name] = self.config[path].get_value(time)[1]

        expr = self.yaml
        for path, var_name in var_map.items():
            expr = expr.replace(path, var_name)

        try:
            values = eval(expr, {}, eval_locals)
        except Exception as e:
            self.annotations.add(0, str(e))
            values = np.zeros_like(time)
        return time, values

    def get_derivative(self, time):
        # Derivative not implemented
        return np.zeros_like(time)

    def get_yaml_string(self):
        """Converts the internal YAML waveform description to a string.

        Returns:
            The YAML waveform description as a string.
        """
        return self.yaml
