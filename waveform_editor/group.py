from ruamel.yaml.comments import CommentedMap


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

    def to_commented_map(self):
        result = CommentedMap()
        if self.groups:
            for group_name, group in self.groups.items():
                result[group_name] = group.to_commented_map()
        if self.waveforms:
            for waveform in self.waveforms.values():
                result[waveform.name] = waveform.yaml
        return result

    def print(self, indent=0):
        """Prints the group as a hierarchical tree.

        Args:
            indent: The indentation level for formatting the output.
        """
        for group_name, group in self.groups.items():
            print(" " * indent + f"{group_name}:")
            group.print(indent + 4)

        for waveform_name in self.waveforms:
            print(" " * indent + waveform_name)
