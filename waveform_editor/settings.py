import logging
import os
from pathlib import Path

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
        self.param.uri.label = f"'{ids_name}' machine description URI"
        self.custom_uri = ""


class NiceSettings(param.Parameterized):
    INVERSE_MODE = "NICE Inverse"
    DIRECT_MODE = "NICE Direct"
    PRESET_ITER = "ITER"
    PRESET_WEST = "WEST"
    PRESET_CUSTOM = "Custom"
    # TODO: Update preset machine descriptions URIs from MD database
    ITER_PF_ACTIVE = "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/ITER/4/666666/3"
    ITER_PF_PASSIVE = "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/ITER/4/666666/3"
    ITER_WALL = "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/ITER/4/666666/3"
    ITER_IRON_CORE = "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/ITER/4/666666/3"
    WEST_PF_ACTIVE = "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/west_test_dd4"
    WEST_PF_PASSIVE = "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/west_test_dd4"
    WEST_WALL = "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/west_test_dd4"
    WEST_IRON_CORE = "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/west_test_dd4"

    machine_preset = param.Selector(
        objects=[PRESET_ITER, PRESET_WEST, PRESET_CUSTOM],
        default=PRESET_CUSTOM,
        label="Machine Preset",
    )
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

    md_pf_active = param.ClassSelector(class_=MachineDescription, precedence=-1)
    md_pf_passive = param.ClassSelector(class_=MachineDescription, precedence=-1)
    md_wall = param.ClassSelector(class_=MachineDescription, precedence=-1)
    md_iron_core = param.ClassSelector(class_=MachineDescription, precedence=-1)

    verbose = param.Integer(label="NICE verbosity (set to 1 for more verbose output)")
    mode = param.Selector(
        objects=[INVERSE_MODE, DIRECT_MODE], default=INVERSE_MODE, precedence=-1
    )
    are_required_filled = param.Boolean(precedence=-1)
    is_direct_mode = param.Boolean(precedence=-1)
    is_inverse_mode = param.Boolean(precedence=-1)

    def __init__(self, **params):
        params.setdefault("md_pf_active", MachineDescription("pf_active"))
        params.setdefault("md_pf_passive", MachineDescription("pf_passive"))
        params.setdefault("md_wall", MachineDescription("wall"))
        params.setdefault("md_iron_core", MachineDescription("iron_core"))
        super().__init__(**params)
        self._preset_switch = False
        for md in self._mds():
            md.param.watch(self._check_required_params_filled, ["uri"])
        self.param.watch(
            self._check_required_params_filled,
            ["inv_executable", "dir_executable", "mode"],
        )
        self.set_mode_flags()
        self._check_required_params_filled()

    def _mds(self):
        return [self.md_pf_active, self.md_pf_passive, self.md_wall, self.md_iron_core]

    @param.depends("mode", watch=True, on_init=True)
    def set_mode_flags(self):
        self.is_direct_mode = self.mode == self.DIRECT_MODE
        self.is_inverse_mode = self.mode == self.INVERSE_MODE

    @param.depends("machine_preset", watch=True)
    def set_machine_preset(self, event=None):
        if event is not None and event.old == self.PRESET_CUSTOM:
            for md in self._mds():
                md.custom_uri = md.uri
        presets = {
            self.PRESET_ITER: (
                self.ITER_PF_ACTIVE,
                self.ITER_PF_PASSIVE,
                self.ITER_WALL,
                self.ITER_IRON_CORE,
            ),
            self.PRESET_WEST: (
                self.WEST_PF_ACTIVE,
                self.WEST_PF_PASSIVE,
                self.WEST_WALL,
                self.WEST_IRON_CORE,
            ),
        }
        uris = presets.get(self.machine_preset) or tuple(
            md.custom_uri for md in self._mds()
        )
        self._preset_switch = True
        try:
            for md, uri in zip(self._mds(), uris, strict=True):
                md.uri = uri
        finally:
            self._preset_switch = False

    def _check_required_params_filled(self, *events):
        base_ready = all(md.uri for md in self._mds())
        if not base_ready:
            self.are_required_filled = False
            return
        if self.mode == self.INVERSE_MODE:
            self.are_required_filled = bool(self.inv_executable)
        else:
            self.are_required_filled = bool(self.dir_executable)

    def apply_settings(self, params):
        """Update parameters from a dictionary, skipping unknown keys."""
        md_keys = {"md_pf_active", "md_pf_passive", "md_wall", "md_iron_core"}
        for key in list(params):
            if key in md_keys:
                md = getattr(self, key)
                md.uri = md.custom_uri = params.pop(key)
            elif key not in self.param or key == "name":
                logger.warning(f"Removing unknown NICE setting: {key}")
                params.pop(key)
        self.param.update(**params)
        self.set_machine_preset()

    def to_dict(self):
        """Returns a dictionary representation of current parameter values, excluding
        params with a precedence of -1."""
        if self.machine_preset == self.PRESET_CUSTOM:
            for md in self._mds():
                md.custom_uri = md.uri
        result = {}
        for p in self.param:
            if p == "name" or self.param[p].precedence == -1:
                continue
            result[p] = getattr(self, p)
        for attr in ("md_pf_active", "md_pf_passive", "md_wall", "md_iron_core"):
            result[attr] = getattr(self, attr).custom_uri
        return result


class UserSettings(param.Parameterized):
    gs_solver = param.Selector(objects=["NICE"], default="NICE")

    nice = param.ClassSelector(class_=NiceSettings, default=None, constant=True)

    def __init__(self, **params):
        params.setdefault("nice", NiceSettings())
        super().__init__(**params)
        self._load_settings()
        self._save_settings()
        self.param.watch(self._save_settings, list(self.param))
        self.nice.param.watch(self._save_settings, list(self.nice.param))
        for md in self.nice._mds():
            md.param.watch(self._save_on_uri_change, ["uri"])

    def _save_on_uri_change(self, event=None):
        if not self.nice._preset_switch:
            self._save_settings()

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
