from waveform_editor.group import WaveformGroup
from waveform_editor.yaml_parser import YamlParser


class WaveformConfiguration:
    def __init__(self):
        self.groups = {}
        # Since waveform names must be unique, we can store a flat mapping of waveform
        # names to the Waveform objects, for cheap look-up
        self.waveform_map = {}
        # TODO: This class can later be used to store additional information stored in
        # the YAML file, such as machine description URI, DD version,etc.

    def __getitem__(self, key):
        if key in self.groups:
            return self.groups[key]
        raise KeyError(f"'{key}' not found in groups")

    def load_yaml(self, yaml_str):
        self.groups.clear()
        self.waveform_map.clear()

        parser = YamlParser()
        parsed_data = parser.load_yaml(yaml_str)  # Get structured data (fully parsed)

        self.groups = parsed_data["groups"]
        self.waveform_map = parsed_data["waveform_map"]

    def add_waveform(self, waveform, path):
        current = self.groups
        for path_part in path:
            current = current[path_part]

        current.waveforms[waveform.name] = waveform
        self.waveform_map[waveform.name] = waveform

    def add_group(self, name, path):
        current = self.groups
        for path_part in path:
            current = current[path_part]

        current.groups[name] = WaveformGroup(name)
        return current.groups[name]

    def to_yaml(self):
        # TODO: write converter implementation
        self.print()
        return ""

    def print(self, indent=0):
        """Print the entire tree structure of the waveform configuration."""
        for group_name, group in self.groups.items():
            print(" " * indent + f"{group_name}:")
            group.print(indent + 4)

    def get_waveform(self, name):
        return self.waveform_map[name]
