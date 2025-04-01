class WaveformGroup:
    def __init__(self, name):
        self.name = name
        self.groups = []
        self.waveforms = {}

    def _repr_recursive(self, level=0):
        indent = "  " * level
        result = f"{indent}WaveformGroup({self.name})\n"

        if self.waveforms:
            for name, waveform in self.waveforms.items():
                result += f"{indent}  {name}: {waveform.tendencies}\n"

        for group in self.groups:
            result += group._repr_recursive(level + 1)

        return result

    def __repr__(self):
        return self._repr_recursive()
