import logging
import os
from pathlib import Path

import imas
import param
import yaml

logger = logging.getLogger(__name__)

_xdg = os.environ.get("XDG_CONFIG_HOME")
_config_home = Path(_xdg) if _xdg else Path.home() / ".config"
CONFIG_FILE = _config_home / "waveform_editor.yaml"


class MachineDescription(param.Parameterized):
    """Holds the URI and load state for a single machine description IDS."""

    uri = param.String()
    loaded = param.Boolean(default=False, precedence=-1)

    def __init__(self, ids_name: str, **params):
        super().__init__(**params)
        self.ids_name = ids_name
        self.param.uri.label = f"'{ids_name}' machine description URI"
        self.custom_uri = ""


class NiceSettings(param.Parameterized):
    INVERSE_MODE = "NICE Inverse"
    DIRECT_MODE = "NICE Direct"
    PRESET_ITER = "ITER"
    PRESET_WEST = "WEST"
    PRESET_CUSTOM = "Custom"

    # Preset machine description URIs
    # TODO: Update URIs so they are from the MD database
    PRESET_URIS = {
        PRESET_ITER: {
            "pf_active": "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/ITER/4/666666/3",  # noqa E501
            "pf_passive": "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/ITER/4/666666/3",  # noqa E501
            "wall": "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/ITER/4/666666/3",
            "iron_core": "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/ITER/4/666666/3",  # noqa E501
        },
        PRESET_WEST: {
            "pf_active": "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/west_test_dd4",  # noqa E501
            "pf_passive": "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/west_test_dd4",  # noqa E501
            "wall": "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/west_test_dd4",
            "iron_core": "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/west_test_dd4",  # noqa E501
        },
    }

    machine_preset = param.Selector(default=PRESET_CUSTOM, label="Machine Preset")
    inv_executable = param.String(
        default="nice_imas_inv_muscle3",
        label="NICE inverse executable path",
        doc="Path to NICE inverse IMAS MUSCLE3 executable",
    )
    dir_executable = param.String(
        default="nice_imas_dir_muscle3",
        label="NICE direct executable path",
        doc="Path to NICE direct IMAS MUSCLE3 executable",
    )
    environment = param.Dict(
        default={},
        label="NICE environment variables",
        doc="Environment variables for NICE",
    )

    md_pf_active = param.ClassSelector(
        class_=MachineDescription,
        default=MachineDescription("pf_active"),
        precedence=-1,
    )
    md_pf_passive = param.ClassSelector(
        class_=MachineDescription,
        default=MachineDescription("pf_passive"),
        precedence=-1,
    )
    md_wall = param.ClassSelector(
        class_=MachineDescription,
        default=MachineDescription("wall"),
        precedence=-1,
    )
    md_iron_core = param.ClassSelector(
        class_=MachineDescription,
        default=MachineDescription("iron_core"),
        precedence=-1,
    )

    verbose = param.Integer(label="NICE verbosity (set to 1 for more verbose output)")
    mode = param.Selector(
        objects=[INVERSE_MODE, DIRECT_MODE], default=INVERSE_MODE, precedence=-1
    )
    are_required_filled = param.Boolean(precedence=-1)
    is_direct_mode = param.Boolean(precedence=-1)
    is_inverse_mode = param.Boolean(precedence=-1)

    def __init__(self, **params):
        super().__init__(**params)
        self._available_presets = self._load_machine_description_presets()
        self.param.machine_preset.objects = [
            *self._available_presets.keys(),
            self.PRESET_CUSTOM,
        ]

        self.machine_descriptions = (
            self.md_pf_active,
            self.md_pf_passive,
            self.md_wall,
            self.md_iron_core,
        )

        for md in self.machine_descriptions:
            md.param.watch(self._check_required_params_filled, ["uri", "loaded"])
            md.param.watch(self._sync_custom_uri, ["uri"])
        self.param.watch(
            self._check_required_params_filled,
            ["inv_executable", "dir_executable", "mode"],
        )

    def _load_machine_description_presets(self):
        """Load the machine description presets from PRESET_URIS"""
        available = {}

        for preset_name, preset in self.PRESET_URIS.items():
            try:
                for ids_name, uri in preset.items():
                    with imas.DBEntry(uri, "r") as entry:
                        entry.get(ids_name, lazy=True)

            except Exception as err:
                logger.warning(
                    "Machine Description Preset '%s' could not be loaded: %s",
                    preset_name,
                    err,
                )
                continue

            available[preset_name] = preset

        return available

    @param.depends("mode", watch=True, on_init=True)
    def set_mode_flags(self):
        self.is_direct_mode = self.mode == self.DIRECT_MODE
        self.is_inverse_mode = self.mode == self.INVERSE_MODE

    @param.depends("machine_preset", watch=True)
    def set_machine_preset(self):
        preset = self._available_presets.get(self.machine_preset)

        if preset is None:
            uris = tuple(md.custom_uri for md in self.machine_descriptions)
        else:
            uris = (
                preset["pf_active"],
                preset["pf_passive"],
                preset["wall"],
                preset["iron_core"],
            )

        for md, uri in zip(self.machine_descriptions, uris, strict=True):
            md.uri = uri

    def _check_required_params_filled(self, *events):
        if not all(md.uri and md.loaded for md in self.machine_descriptions):
            self.are_required_filled = False
            return

        if self.mode == self.INVERSE_MODE:
            self.are_required_filled = bool(self.inv_executable)
        else:
            self.are_required_filled = bool(self.dir_executable)

    def apply_settings(self, params):
        """Update parameters from a dictionary, skipping unknown keys."""
        for md in self.machine_descriptions:
            md_name = f"md_{md.ids_name}"
            if md_name in params:
                md.uri = md.custom_uri = params.pop(md_name)
        for key in list(params):
            if key not in self.param or key == "name":
                logger.warning(f"Removing unknown NICE setting: {key}")
                params.pop(key)
        self.param.update(**params)

    def _sync_custom_uri(self, event):
        if self.machine_preset == self.PRESET_CUSTOM:
            event.obj.custom_uri = event.new

    def to_dict(self):
        """Returns a dictionary representation of current parameter values, excluding
        params with a precendence of -1."""
        result = {}
        for p in self.param:
            param_obj = self.param[p]
            if p != "name" and param_obj.precedence != -1:
                result[p] = getattr(self, p)

        for md in self.machine_descriptions:
            result[f"md_{md.ids_name}"] = md.custom_uri

        return result


class UserSettings(param.Parameterized):
    gs_solver = param.Selector(objects=["NICE"], default="NICE")

    nice = param.ClassSelector(class_=NiceSettings, default=NiceSettings())

    def __init__(self, **params):
        super().__init__(**params)
        self._load_settings()
        self._save_settings()
        self.param.watch(self._save_settings, list(self.param))
        self.nice.param.watch(self._save_settings, list(self.nice.param))
        for md in self.nice.machine_descriptions:
            md.param.watch(self._save_settings, ["uri"])

    def _load_settings(self):
        """Load settings from disk and apply them to the current instance."""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                settings = yaml.safe_load(f) or {}
        else:
            settings = {}

        if "nice" in settings:
            self.nice.apply_settings(settings["nice"])

        base_settings = {k: v for k, v in settings.items() if k != "nice"}
        for key in list(base_settings):
            if key not in self.param or key in ("name", "nice"):
                logger.warning(f"Removing unknown setting: {key}")
                base_settings.pop(key)
        self.param.update(**base_settings)

    def _save_settings(self, event=None):
        """Serialize current configuration to disk in YAML format."""
        config = {
            p: getattr(self, p) for p in self.param if p != "name" and p != "nice"
        }

        if self.gs_solver == "NICE":
            config["nice"] = self.nice.to_dict()

        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            yaml.safe_dump(config, f)
        logger.debug(f"Saved options to {CONFIG_FILE}")


settings = UserSettings()  # Global config object
