class WaveformConfiguration:
    def __init__(self):
        self.groups = {}
        # Since waveform names must be unique, we can store a flat mapping of waveform
        # names to the Waveform objects, for cheap look-up
        self.waveform_map = {}
        # TODO: This class can later be used to store additional information stored in
        # the YAML file, such as machine description URI, DD version,etc.

    def print(self, indent=0):
        """Print the entire tree structure of the waveform configuration."""
        for group_name, group in self.groups.items():
            print(" " * indent + f"{group_name}:")
            group.print(indent + 4)

    def get_waveform(self, name):
        return self.waveform_map[name]
