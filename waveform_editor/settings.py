import logging
import os
from pathlib import Path

import param
import yaml

logger = logging.getLogger(__name__)

_xdg = os.environ.get("XDG_CONFIG_HOME")
_config_home = Path(_xdg) if _xdg else Path.home() / ".config"
CONFIG_FILE = _config_home / "waveform_editor.yaml"


class NiceSettings(param.Parameterized):
    INVERSE_MODE = "NICE Inverse"
    DIRECT_MODE = "NICE Direct"
    PRESET_ITER = "ITER"
    PRESET_WEST = "WEST"
    PRESET_CUSTOM = "Custom"
    BASE_REQUIRED = (
        "md_pf_active",
        "md_pf_passive",
        "md_wall",
        "md_iron_core",
    )
    # TODO: Update preset machine descriptions
    ITER_PF_ACTIVE = "PLACEHOLDER_ITER_PF_ACTIVE"
    ITER_PF_PASSIVE = "PLACEHOLDER_ITER_PF_PASSIVE"
    ITER_WALL = "PLACEHOLDER_ITER_WALL"
    ITER_IRON_CORE = "PLACEHOLDER_ITER_IRON_CORE"
    WEST_PF_ACTIVE = "PLACEHOLDER_WEST_PF_ACTIVE"
    WEST_PF_PASSIVE = "PLACEHOLDER_WEST_PF_PASSIVE"
    WEST_WALL = "PLACEHOLDER_WEST_WALL"
    WEST_IRON_CORE = "PLACEHOLDER_WEST_IRON_CORE"

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
    md_pf_active_loaded = param.Boolean(default=False, precedence=-1)
    md_pf_passive_loaded = param.Boolean(default=False, precedence=-1)
    md_wall_loaded = param.Boolean(default=False, precedence=-1)
    md_iron_core_loaded = param.Boolean(default=False, precedence=-1)

    custom_md_pf_active = param.String(
        label="custom 'pf_active' machine description URI"
    )
    custom_md_pf_passive = param.String(
        label="custom 'pf_passive' machine description URI"
    )
    custom_md_wall = param.String(label="custom 'wall' machine description URI")
    custom_md_iron_core = param.String(
        label="custom 'iron_core' machine description URI"
    )

    md_pf_active = param.String(
        label="'pf_active' machine description URI", precedence=-1
    )
    md_pf_passive = param.String(
        label="'pf_passive' machine description URI", precedence=-1
    )
    md_wall = param.String(label="'wall' machine description URI", precedence=-1)
    md_iron_core = param.String(
        label="'iron_core' machine description URI", precedence=-1
    )

    verbose = param.Integer(label="NICE verbosity (set to 1 for more verbose output)")
    mode = param.Selector(
        objects=[INVERSE_MODE, DIRECT_MODE], default=INVERSE_MODE, precedence=-1
    )
    are_required_filled = param.Boolean(precedence=-1)
    is_direct_mode = param.Boolean(precedence=-1)
    is_inverse_mode = param.Boolean(precedence=-1)

    @param.depends("mode", watch=True, on_init=True)
    def set_mode_flags(self):
        self.is_direct_mode = self.mode == self.DIRECT_MODE
        self.is_inverse_mode = self.mode == self.INVERSE_MODE

    @param.depends("md_pf_active", watch=True)
    def sync_md_pf_active(self):
        if self.machine_preset == self.PRESET_CUSTOM:
            self.custom_md_pf_active = self.md_pf_active

    @param.depends("md_pf_passive", watch=True)
    def sync_md_pf_passive(self):
        if self.machine_preset == self.PRESET_CUSTOM:
            self.custom_md_pf_passive = self.md_pf_passive

    @param.depends("md_wall", watch=True)
    def sync_md_wall(self):
        if self.machine_preset == self.PRESET_CUSTOM:
            self.custom_md_wall = self.md_wall

    @param.depends("md_iron_core", watch=True)
    def sync_md_iron_core(self):
        if self.machine_preset == self.PRESET_CUSTOM:
            self.custom_md_iron_core = self.md_iron_core

    @param.depends("machine_preset", watch=True)
    def set_machine_preset(self):
        # TODO: update placeholders to default URI
        if self.machine_preset == self.PRESET_ITER:
            self.md_pf_active = self.ITER_PF_ACTIVE
            self.md_pf_passive = self.ITER_PF_PASSIVE
            self.md_wall = self.ITER_WALL
            self.md_iron_core = self.ITER_IRON_CORE
        elif self.machine_preset == self.PRESET_WEST:
            self.md_pf_active = self.WEST_PF_ACTIVE
            self.md_pf_passive = self.WEST_PF_PASSIVE
            self.md_wall = self.WEST_WALL
            self.md_iron_core = self.WEST_IRON_CORE
        else:  # custom
            self.md_pf_active = self.custom_md_pf_active
            self.md_pf_passive = self.custom_md_pf_passive
            self.md_wall = self.custom_md_wall
            self.md_iron_core = self.custom_md_iron_core

    @param.depends(
        *BASE_REQUIRED, "inv_executable", "dir_executable", "mode", watch=True
    )
    def check_required_params_filled(self):
        base_ready = all(getattr(self, p) for p in self.BASE_REQUIRED)

        if not base_ready:
            self.are_required_filled = False
            return

        if self.mode == self.INVERSE_MODE:
            self.are_required_filled = bool(self.inv_executable)
        else:
            self.are_required_filled = bool(self.dir_executable)

    def apply_settings(self, params):
        """Update parameters from a dictionary, skipping unknown keys."""
        for key in list(params):
            if key not in self.param or key == "name":
                logger.warning(f"Removing unknown NICE setting: {key}")
                params.pop(key)
        self.param.update(**params)
        self.set_machine_preset()

    def to_dict(self):
        """Returns a dictionary representation of current parameter values, excluding
        params with a precendence of -1."""
        result = {}
        for p in self.param:
            param_obj = self.param[p]
            if p != "name" and param_obj.precedence != -1:
                result[p] = getattr(self, p)
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
