from waveform_editor.group import WaveformGroup
from waveform_editor.yaml_parser import YamlParser


class WaveformConfiguration:
    def __init__(self):
        self.groups = {}
        # Since waveform names must be unique, we can store a flat mapping of waveform
        # names to the WaveformGroup that this waveform belongs to, for cheap look-up
        # of waveforms
        self.waveform_map = {}
        self.load_error = ""

    def __getitem__(self, key):
        """Retrieves a waveform group by name.

        Args:
            key: The name of the group to retrieve.

        Returns:
            The requested waveform group.
        """
        if "/" in key:
            if key in self.waveform_map:
                group = self.waveform_map[key]
                return group[key]
            raise KeyError(f"{key!r} not found in waveform map.")
        else:
            if key in self.groups:
                return self.groups[key]
            raise KeyError(f"{key!r} not found in groups")

    def load_yaml(self, yaml_str):
        """Loads waveform configuration from a YAML string.

        Args:
            yaml_str: The YAML string containing waveform configuration data.
        """
        parser = YamlParser()
        self.load_error = ""
        parsed_data = parser.load_yaml(yaml_str)

        if parsed_data is None:
            self.load_error = parser.load_yaml_error
        else:
            self.groups = parsed_data["groups"]
            self.waveform_map = parsed_data["waveform_map"]

    def add_waveform(self, waveform, path):
        """Adds a waveform to a specific group in the configuration.

        Args:
            waveform: The waveform object to add.
            path: A list representing the path where the new waveform should be created.
        """
        if "/" not in waveform.name:
            raise ValueError(
                "Waveforms in configurations must contain '/' in their name."
            )
        if not path:
            raise ValueError("Waveforms must be added at a specific group path.")

        if waveform.name in self.waveform_map:
            raise ValueError("The waveform already exists in this configuration.")
        group = self.traverse(path)
        group.waveforms[waveform.name] = waveform
        self.waveform_map[waveform.name] = group

    def replace_waveform(self, waveform):
        """Replaces an existing waveform with a new waveform.

        Args:
            waveform: The new waveform object to replace the old one.
        """
        if waveform.name not in self.waveform_map:
            raise ValueError(
                f"Waveform '{waveform.name}' does not exist in the configuration."
            )
        else:
            group = self.waveform_map[waveform.name]
            group.waveforms[waveform.name] = waveform

    def remove_waveform(self, name):
        """Removes an existing waveform.

        Args:
            name: The name of the waveform to be removed.
        """
        if name not in self.waveform_map:
            raise ValueError(f"Waveform '{name}' does not exist in the configuration.")
        else:
            group = self.waveform_map[name]
            self.waveform_map.pop(name)
            group.waveforms.pop(name)

    def remove_group(self, path):
        """Removes a group, and all the groups/waveforms in it.

        Args:
            path: A list representing the path to the group to be removed.
        """
        parent_group = self.traverse(path[:-1])
        group_name_to_remove = path[-1]

        group_to_remove = parent_group.groups[group_name_to_remove]
        for waveform_name in group_to_remove.waveforms:
            self.waveform_map.pop(waveform_name, None)

        # Convert to list to prevent changing size during iteration
        for child_group_name in list(group_to_remove.groups):
            self.remove_group(path + [child_group_name])

        del parent_group.groups[group_name_to_remove]

    def add_group(self, name, path):
        """Adds a new waveform group at the specified path.

        Args:
            name: The name of the new group.
            path: A list representing the path where the new group should be added.

        Returns:
            The newly created waveform group.
        """
        group = self.traverse(path).groups if path else self.groups

        if name in group:
            raise ValueError(f"{name} already exists at path: {path or 'root'}.")

        group[name] = WaveformGroup(name)
        return group[name]

    def traverse(self, path):
        """Traverse through nested groups and return the WaveformGroup at the given
        path.

        Args:
            path: List of strings containing the nested group names.
        """
        current = self.groups
        for path_part in path:
            current = current[path_part]
        return current

    def to_yaml(self):
        # TODO: write converter implementation that keeps the raw string in output.
        # Ensure that comments are not removed, and formatting of tendencies
        # is preserved.
        self.print()
        raise NotImplementedError

    def print(self, indent=0):
        """Prints the waveform configuration as a hierarchical tree.

        Args:
            indent: The indentation level for formatting the output.
        """
        for group_name, group in self.groups.items():
            print(" " * indent + f"{group_name}:")
            group.print(indent + 4)
