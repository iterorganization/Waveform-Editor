import io
import logging

import param
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from waveform_editor.dependency_graph import DependencyGraph
from waveform_editor.derived_waveform import DerivedWaveform
from waveform_editor.group import WaveformGroup
from waveform_editor.yaml_globals import YamlGlobals
from waveform_editor.yaml_parser import YamlParser

logger = logging.getLogger(__name__)


class WaveformConfiguration(param.Parameterized):
    has_changed = param.Boolean()
    DEFAULT_START = 0
    DEFAULT_END = 1

    def __init__(self):
        super().__init__()
        self.groups = {}
        # Since waveform names must be unique, we can store a flat mapping of waveform
        # names to the WaveformGroup that this waveform belongs to, for cheap look-up
        # of waveforms
        self.waveform_map = {}
        self.globals = YamlGlobals()
        self.load_error = ""
        self.parser = YamlParser(self)
        self.dependency_graph = DependencyGraph()
        self.start = self.DEFAULT_START
        self.end = self.DEFAULT_END

        # Trigger has_changed boolean when a global param is changed
        for param_name in self.globals.param:
            self.globals.param.watch(self._set_changed, param_name)

    def _set_changed(self, event):
        self.has_changed = True

    def __getitem__(self, key):
        """Retrieves a waveform or group by name/path.

        Args:
            key: The name of the waveform or group to retrieve.

        Returns:
            The requested waveform or group.
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
        """Parses a YAML string and populates configuration.

        Args:
            yaml_str: The YAML string to load YAML for.
        """
        self.clear()
        try:
            self.parser.load_yaml(yaml_str)
            self._calculate_bounds()
            for name, group in self.waveform_map.items():
                waveform = group[name]
                if isinstance(waveform, DerivedWaveform):
                    waveform.prepare_expression()
            self.has_changed = False
        except Exception as e:
            self.clear()
            logger.warning("Got unexpected error: %s", e, exc_info=e)
            self.load_error = str(e)

    def add_waveform(self, waveform, path):
        """Adds a waveform to a specific group in the configuration.

        Args:
            waveform: The waveform object to add.
            path: A list representing the path where the new waveform should be created.
        """
        self._validate_name(waveform.name)
        if not path:
            raise ValueError("Waveforms must be added at a specific group path.")

        if isinstance(waveform, DerivedWaveform):
            self.dependency_graph.add_node(waveform.name, waveform.dependencies)

        group = self.traverse(path)
        group.waveforms[waveform.name] = waveform
        self.waveform_map[waveform.name] = group
        self._calculate_bounds()
        self.has_changed = True

    def rename_waveform(self, old_name, new_name):
        """Renames an existing waveform.

        Args:
            old_name: The name of the waveform to rename.
            new_name: The name to rename the old waveform to.
        """

        self._validate_name(new_name)
        if old_name not in self.waveform_map:
            raise ValueError(
                f"Waveform '{old_name}' does not exist in the configuration."
            )

        group = self.waveform_map.pop(old_name)
        waveform = group.waveforms.pop(old_name)

        waveform.name = new_name

        group.waveforms[new_name] = waveform
        self.waveform_map[new_name] = group

        dependents = self.dependency_graph.rename_node(old_name, new_name)
        for dependent_name in dependents:
            dependent_waveform = self[dependent_name]
            dependent_waveform.rename_dependency(old_name, new_name)
        self.has_changed = True

    def check_safe_to_replace(self, waveform):
        """Validate that a waveform is safe to replace.

        Args:
            waveform: The waveform to validate for replacement.
        """
        self.dependency_graph.check_safe_to_replace(
            waveform.name, waveform.dependencies
        )
        for dependent_wf in waveform.dependencies:
            if dependent_wf not in self.waveform_map:
                raise ValueError(
                    f"Cannot depend on waveform '{dependent_wf}', it does not exist!"
                )

    def _validate_name(self, name):
        """Check that name contains a '/' and doesn't exist already. If not, a
        ValueError is raised.

        Args:
            name: The waveform name to validate.
        """
        if "/" not in name:
            raise ValueError(
                "Waveforms in configurations must contain '/' in their name."
            )
        if name in self.waveform_map:
            raise ValueError("The waveform already exists in this configuration.")

    def replace_waveform(self, waveform):
        """Replaces an existing waveform with a new waveform.

        Args:
            waveform: The new waveform object to replace the old one.
        """
        if waveform.name not in self.waveform_map:
            raise ValueError(
                f"Waveform '{waveform.name}' does not exist in the configuration."
            )

        if isinstance(waveform, DerivedWaveform):
            self.dependency_graph.replace_node(waveform.name, waveform.dependencies)
        elif waveform.name in self.dependency_graph:
            self.dependency_graph.remove_node(waveform.name)

        group = self.waveform_map[waveform.name]
        group.waveforms[waveform.name] = waveform
        self._calculate_bounds()
        self.has_changed = True

    def remove_waveform(self, name):
        """Removes an existing waveform.

        Args:
            name: The name of the waveform to be removed.
        """
        if name not in self.waveform_map:
            raise ValueError(f"Waveform '{name}' does not exist in the configuration.")
        self.dependency_graph.check_safe_to_remove(name)

        if name in self.dependency_graph:
            self.dependency_graph.remove_node(name)
        group = self.waveform_map[name]
        del self.waveform_map[name]
        del group.waveforms[name]
        self._calculate_bounds()
        self.has_changed = True

    def remove_group(self, path):
        """Removes a group, and all the groups/waveforms in it.

        Args:
            path: A list representing the path to the group to be removed.
        """
        parent_group = self if len(path) == 1 else self.traverse(path[:-1])
        group = parent_group.groups[path[-1]]

        to_remove = self._collect_waveforms_in_group(group)

        for wf_name, grp in self.waveform_map.items():
            if wf_name not in to_remove:
                wf = grp[wf_name]
                if isinstance(wf, DerivedWaveform) and to_remove.intersection(
                    wf.dependencies
                ):
                    raise RuntimeError(
                        f"Cannot remove group {group.name}. "
                        f"{wf.name!r} depends on a waveform in it."
                    )

        del parent_group.groups[path[-1]]
        self._recursive_remove_waveforms(group)
        self._calculate_bounds()
        for name in to_remove:
            if name in self.dependency_graph:
                self.dependency_graph.remove_node(name)
        self.has_changed = True

    def _collect_waveforms_in_group(self, group):
        """Collect all waveform names within a group, including nested subgroups.

        Args:
            group: The group to collect the waveforms for.

        Returns:
            Set of waveform names.
        """
        waveforms = set()
        groups_to_process = [group]
        while groups_to_process:
            current = groups_to_process.pop()
            waveforms.update(current.waveforms.keys())
            groups_to_process.extend(current.groups.values())
        return waveforms

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
        self.has_changed = True
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
        result = CommentedMap(self.globals.get())
        for group_name, group in self.groups.items():
            result[group_name] = group.to_commented_map()
        return result

    def _calculate_bounds(self):
        min_start = float("inf")
        max_end = float("-inf")

        for name in self.waveform_map:
            waveform = self[name]
            if not isinstance(waveform, DerivedWaveform) and waveform.tendencies:
                min_start = min(min_start, waveform.tendencies[0].start)
                max_end = max(max_end, waveform.tendencies[-1].end)

        self.start = min_start if min_start != float("inf") else self.DEFAULT_START
        self.end = max_end if max_end != float("-inf") else self.DEFAULT_END

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
        self.globals.reset()
        self.load_error = ""
        self.start = self.DEFAULT_START
        self.end = self.DEFAULT_END
        self.has_changed = False
