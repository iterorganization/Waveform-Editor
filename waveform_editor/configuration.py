import io

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from waveform_editor.group import WaveformGroup
from waveform_editor.yaml_parser import YamlParser


class WaveformConfiguration:
    def __init__(self):
        self.groups = {}
        # Since waveform names must be unique, we can store a flat mapping of waveform
        # names to the WaveformGroup that this waveform belongs to, for cheap look-up
        # of waveforms
        self.waveform_map = {}
        self.dd_version = None
        self.machine_description = {}
        self.load_error = ""
        self.parser = YamlParser(self)

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

        group = self.waveform_map[name]
        del self.waveform_map[name]
        del group.waveforms[name]

    def remove_group(self, path):
        """Removes a group, and all the groups/waveforms in it.

        Args:
            path: A list representing the path to the group to be removed.
        """
        parent_group = self if len(path) == 1 else self.traverse(path[:-1])
        group = parent_group.groups.pop(path[-1])
        self._recursive_remove_waveforms(group)

    def _recursive_remove_waveforms(self, group):
        """Recursively remove all waveforms from a group and its nested subgroups from
        the waveform_map.

        Args:
            group: The group to remove the waveforms from.
        """
        for waveform in group.waveforms:
            del self.waveform_map[waveform]
        for subgroup in group.groups.values():
            self._recursive_remove_waveforms(subgroup)

    def add_group(self, name, path):
        """Adds a new waveform group at the specified path.

        Args:
            name: The name of the new group.
            path: A list representing the path where the new group should be added.

        Returns:
            The newly created waveform group.
        """
        if "/" in name:
            raise ValueError("Group name may not contain '/'.")
        if not name:
            raise ValueError("Group name may not be empty.")

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

    def dump(self):
        """Convert the configuration to a YAML string."""
        yaml = YAML()
        data = self._to_commented_map()
        stream = io.StringIO()
        yaml.dump(data, stream)
        return stream.getvalue()

    def parse_waveform(self, yaml_str):
        """Parse a YAML waveform string and return a waveform object.

        Args:
            yaml_str: The YAML string to parse.

        Returns:
            The parsed waveform object.
        """
        self.parser.parse_errors = []
        return self.parser.parse_waveform(yaml_str)

    def _to_commented_map(self):
        """Return the configuration as a nested CommentedMap."""
        result = CommentedMap()
        for group_name, group in self.groups.items():
            result[group_name] = group.to_commented_map()
        return result

    def print(self, indent=0):
        """Prints the waveform configuration as a hierarchical tree.

        Args:
            indent: The indentation level for formatting the output.
        """
        for group_name, group in self.groups.items():
            print(" " * indent + f"{group_name}:")
            group.print(indent + 4)

    def clear(self):
        """Clears the data stored in the configuration."""
        self.groups = {}
        self.waveform_map = {}
        self.dd_version = None
        self.machine_description = {}
        self.load_error = ""
