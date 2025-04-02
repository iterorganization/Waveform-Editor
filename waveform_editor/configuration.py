class WaveformConfiguration:
    def __init__(self):
        self.groups = {}
        # TODO: This class can later be used to store additional information stored in
        # the YAML file, such as machine description URI, DD version,etc.

    def print(self, indent=0):
        """Print the entire tree structure of the waveform configuration."""
        for group_name, group in self.groups.items():
            print(" " * indent + f"{group_name}:")
            group.print(indent + 4)
