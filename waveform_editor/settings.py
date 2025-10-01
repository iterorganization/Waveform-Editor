import logging
import os
from pathlib import Path

import panel as pn
import param
import yaml

from waveform_editor.gui.util import WarningIndicator

logger = logging.getLogger(__name__)

_xdg = os.environ.get("XDG_CONFIG_HOME")
_config_home = Path(_xdg) if _xdg else Path.home() / ".config"
CONFIG_FILE = _config_home / "waveform_editor.yaml"


class NiceSettings(param.Parameterized):
    INVERSE_MODE = "NICE Inverse"
    DIRECT_MODE = "NICE Direct"

    BASE_REQUIRED = (
        "md_pf_active",
        "md_pf_passive",
        "md_wall",
        "md_iron_core",
    )
    inv_executable = param.String(
        label="NICE inverse executable path",
        doc="Path to NICE inverse IMAS MUSCLE3 executable",
    )
    dir_executable = param.String(
        label="NICE direct executable path",
        doc="Path to NICE direct IMAS MUSCLE3 executable",
    )
    environment = param.Dict(
        default={},
        label="NICE environment variables",
        doc="Environment variables for NICE",
    )
    md_pf_active = param.String(label="'pf_active' machine description URI")
    md_pf_passive = param.String(label="'pf_passive' machine description URI")
    md_wall = param.String(label="'wall' machine description URI")
    md_iron_core = param.String(label="'iron_core' machine description URI")
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

    def to_dict(self):
        """Returns a dictionary representation of current parameter values, excluding
        params with a precendence of -1."""
        result = {}
        for p in self.param:
            param_obj = self.param[p]
            if p != "name" and param_obj.precedence != -1:
                result[p] = getattr(self, p)
        return result

    def panel(self):
        items = []

        for p in self.param:
            if p == "name":
                continue

            # Add warning indicator if required parameter is not filled
            is_inv_required = p == "inv_executable" and self.is_inverse_mode
            is_dir_required = p == "dir_executable" and self.is_direct_mode
            is_base_required = p in self.BASE_REQUIRED

            row_content = [pn.Param(self.param[p], show_name=False)]
            if is_inv_required or is_dir_required or is_base_required:
                warning = WarningIndicator(visible=self.param[p].rx.not_())
                row_content.append(warning)

            items.append(pn.Row(*row_content))

        return pn.Column(*items)


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

    @param.depends("gs_solver")
    def panel(self):
        params_to_show = [p for p in self.param if p != "nice" and p != "name"]
        base_ui = pn.Param(self.param, parameters=params_to_show)
        if self.gs_solver == "NICE":
            nice_ui = pn.panel(self.nice.param, expand_button=False, expand=True)
            return pn.Column(base_ui, pn.Spacer(height=10), nice_ui)
        else:
            return base_ui


settings = UserSettings()  # Global config object
