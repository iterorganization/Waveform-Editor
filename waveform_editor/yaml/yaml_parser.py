import ast
import logging
import re
from io import StringIO

import imas
import yaml
from imas.ids_path import IDSPath
from ruamel.yaml import YAML

from waveform_editor.import_waveform import ImportWaveform
from waveform_editor.static_waveform import StaticWaveform
from waveform_editor.waveform import Waveform
from waveform_editor.yaml.yaml_globals import CURRENT_SCHEMA_VERSION

logger = logging.getLogger(__name__)


def _is_import_entry(entry):
    """Whether a parsed waveform entry declares an import (``{ref: ...}``)."""
    return isinstance(entry, dict) and (
        "user_ref" in entry or entry.get("user_type") in ("import", "reference")
    )


def _looks_like_expression(value):
    """Whether a bare string value should be read as an expression rather than a
    literal string constant.

    Waveform references are quoted strings, so an expression is anything *dynamic* (it
    contains a quoted reference) or *functional* (it uses a call or an operator). A
    plain word (``nbi``) or an unparseable string is a literal constant. The explicit
    ``{value: ...}`` / ``{expression: ...}`` forms override this heuristic.
    """
    try:
        tree = ast.parse(value, mode="eval")
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return True  # a quoted waveform reference -> dynamic
        if isinstance(
            node, (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Call)
        ):
            return True  # uses an operator or function -> functional
    return False


def _import_is_non_scalar(name, entry, dd_version):
    """Whether an import must be an ImportWaveform rather than a 0D segment.

    True for wildcard paths (``.../*``) and for any path whose DD leaf is not a scalar
    (a value per radial point, an array of structure, etc.); such imports cannot be
    combined with analytic segments and own the whole waveform.
    """
    source = entry.get("user_path") or name
    if "*" in source:
        return True
    try:
        ids_name, path = source.split("/", 1)
        ids = imas.IDSFactory(version=dd_version).new(ids_name)
        metadata = IDSPath(path).goto_metadata(ids.metadata)
    except (imas.exception.IDSNameError, ValueError, KeyError):
        # Unknown path: let the (sole-content) ImportWaveform path handle/report it.
        return True
    return metadata.ndim != 0


class LineNumberYamlLoader(yaml.SafeLoader):
    def _check_for_duplicates(self, node, deep):
        seen = set()

        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                # Mock a problem mark so we can pass the line number of the error
                problem_mark = yaml.Mark(
                    "<duplicate>", 0, node.start_mark.line, 0, 0, 0
                )
                raise yaml.MarkedYAMLError(
                    problem=f"Found duplicate entry {key!r}.",
                    problem_mark=problem_mark,
                )
            seen.add(key)

    def construct_mapping(self, node, deep=False):
        # The line numbers must be extracted to be able to display the error messages
        mapping = super().construct_mapping(node, deep)

        # Prepend "user_" to all keys
        mapping = {f"user_{key}": value for key, value in mapping.items()}
        mapping["line_number"] = node.start_mark.line

        # Check if all entries of the duplicate mapping are unique, as the yaml
        # SafeLoader silently ignores duplicate keys
        self._check_for_duplicates(node, deep)

        return mapping


class YamlParser:
    def __init__(self, config):
        self.yaml = YAML()
        self.config = config
        self.parse_errors = []

    def load_yaml(self, yaml_str):
        """Parses a YAML string and populates the WaveformConfiguration.

        Args:
            yaml_str: The YAML string to load YAML for.
        """
        self.parse_errors = []

        yaml_data = self.yaml.load(yaml_str) if yaml_str else {}
        globals = yaml_data.get("globals", {})
        file_version = globals.get("version")
        if file_version is None or file_version < CURRENT_SCHEMA_VERSION:
            logger.warning(
                "Configuration schema version (%s) is older than the current version "
                "(%s). A bare string is now an expression only if it references "
                "another waveform or uses an operator/function; a plain word is a "
                "literal constant. Use `{value: ...}` or `{expression: ...}` to be "
                "explicit.",
                file_version,
                CURRENT_SCHEMA_VERSION,
            )
        self.config.globals.set_globals(globals)

        if not isinstance(yaml_data, dict):
            raise ValueError("Input yaml_data must be a dictionary.")

        for group_name, group_content in yaml_data.items():
            if group_name == "globals":
                continue

            if not isinstance(group_content, dict):
                raise ValueError("Waveforms must belong to a group.")

            self._recursive_load(group_content, group_name, [])

    def _recursive_load(self, data_dict, group_name, path):
        """Recursively builds a hierarchy of WaveformGroup objects from a nested
        dictionary.

        Args:
            data_dict: Input data containing waveform groups and waveforms.
            group_name: Name of the current group.
            path: The list of parent group names representing the current path.

        Returns:
            The populated waveform group.
        """
        current_group = self.config.add_group(group_name, path)

        for key, value in data_dict.items():
            if isinstance(value, dict):
                self._recursive_load(value, key, path + [group_name])
            else:
                yaml_str = self.generate_yaml_str(key, value)
                waveform = self.parse_waveform(yaml_str)
                self.config.add_waveform(waveform, path + [group_name])

        return current_group

    def generate_yaml_str(self, key, value):
        """Generate YAML string for a key-value pair, ensuring comments are retained.

        Args:
            key: Key of the yaml string.
            value: Corresponding value for the key.
        """
        stream = StringIO()
        self.yaml.dump({key: value}, stream)
        return stream.getvalue()

    def parse_waveform(self, yaml_str):
        """Loads a YAML structure from a string and stores its tendencies into a list.

        Args:
            yaml_str: YAML content as a string.
        """
        try:
            loader = LineNumberYamlLoader
            # Parse scientific notation as a float, instead of a string. For
            # more information see: https://stackoverflow.com/a/30462009/8196245
            loader.add_implicit_resolver(
                "tag:yaml.org,2002:float",
                re.compile(
                    """^(?:
                     [-+]?(?:[0-9][0-9_]*)\\.[0-9_]*(?:[eE][-+]?[0-9]+)?
                    |[-+]?(?:[0-9][0-9_]*)(?:[eE][-+]?[0-9]+)
                    |\\.[0-9_]+(?:[eE][-+][0-9]+)?
                    |[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\\.[0-9_]*
                    |[-+]?\\.(?:inf|Inf|INF)
                    |\\.(?:nan|NaN|NAN))$""",
                    re.X,
                ),
                list("-+0123456789."),
            )
            waveform_yaml = yaml.load(yaml_str, Loader=loader)

            if not isinstance(waveform_yaml, dict):
                raise yaml.YAMLError(
                    f"Expected a dictionary but got {type(waveform_yaml).__name__!r}"
                )

            # Find first key in the yaml that starts with "user_"
            for waveform_key in waveform_yaml:
                if waveform_key.startswith("user_"):
                    break
            else:
                raise RuntimeError("Missing key")

            name = waveform_key.removeprefix("user_")
            waveform = waveform_yaml[waveform_key]
            if waveform is None:
                raise yaml.YAMLError("Cannot have an empty waveform.")
            if not isinstance(waveform, (list, int, float, str)):
                raise yaml.YAMLError(
                    "Waveform must either be a list of tendencies or a bare constant "
                    "value (number or string)."
                )
            line_number = waveform_yaml.get("line_number", 0)
            dd_version = self.config.globals.dd_version
            if isinstance(waveform, list):
                # A single {value: <string>} entry is a static string constant (e.g.
                # an identifier name).
                if (
                    len(waveform) == 1
                    and isinstance(waveform[0], dict)
                    and isinstance(waveform[0].get("user_value"), str)
                ):
                    return StaticWaveform(
                        waveform[0]["user_value"],
                        yaml_str=yaml_str,
                        name=name,
                        dd_version=dd_version,
                    )
                # A non-0D or wildcard import owns the whole waveform (and may list
                # several overlays); 0D imports stay as tendency segments, combinable
                # with analytic ones.
                if (
                    waveform
                    and all(_is_import_entry(entry) for entry in waveform)
                    and _import_is_non_scalar(name, waveform[0], dd_version)
                ):
                    return ImportWaveform(
                        waveform,
                        yaml_str=yaml_str,
                        name=name,
                        dd_version=dd_version,
                    )
                return Waveform(
                    waveform=waveform,
                    yaml_str=yaml_str,
                    line_number=line_number,
                    name=name,
                    dd_version=dd_version,
                    config=self.config,
                )
            # A bare scalar is shorthand. A number is a constant; a string that
            # references other waveforms or uses operators/functions is an expression,
            # otherwise it is a static (literal) string constant.
            if isinstance(waveform, str):
                if _looks_like_expression(waveform):
                    entry = {"user_expression": waveform, "line_number": line_number}
                else:
                    return StaticWaveform(
                        waveform, yaml_str=yaml_str, name=name, dd_version=dd_version
                    )
            else:
                entry = {"user_value": waveform, "line_number": line_number}
            return Waveform(
                waveform=[entry],
                yaml_str=yaml_str,
                line_number=line_number,
                name=name,
                dd_version=dd_version,
                config=self.config,
            )
        except yaml.YAMLError as e:
            self.parse_errors.append(str(e))
            empty_waveform = Waveform()
            empty_waveform.annotations.add_yaml_error(e)
            return empty_waveform
