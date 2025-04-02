class WaveformGroup:
    def __init__(self, name):
        self.name = name
        self.groups = {}
        self.waveforms = {}

    def __getitem__(self, key):
        if "/" in key:
            if key in self.waveforms:
                return self.waveforms[key]
        else:
            if key in self.groups:
                return self.groups[key]
        raise KeyError(f"'{key}' not found in groups or waveforms")
