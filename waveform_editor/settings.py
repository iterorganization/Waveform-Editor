import logging
import os
from pathlib import Path

import panel as pn
import param
import yaml

logger = logging.getLogger(__name__)

_xdg = os.environ.get("XDG_CONFIG_HOME")
_config_home = Path(_xdg) if _xdg else Path.home() / ".config"
CONFIG_FILE = _config_home / "waveform_editor.yaml"


class NiceSettings(param.Parameterized):
    executable = param.String(
        default="nice_imas_inv_muscle3",
        label="NICE executable path",
        doc="Path to NICE inverse IMAS MUSCLE3 executable",
    )
    environment = param.Dict(
        default={},
        label="NICE environment variables",
        doc="Environment variables for NICE",
    )
    md_pf_active = param.String(
        label="'pf_active' machine description URI",
    )
    md_pf_passive = param.String(
        label="'pf_passive' machine description URI",
    )
    md_wall = param.String(
        label="'wall' machine description URI",
    )
    md_iron_core = param.String(
        label="'iron_core' machine description URI",
    )

    def apply_settings(self, params):
        """Update parameters from a dictionary."""
        self.param.update(**params)

    def to_dict(self):
        """Returns a dictionary representation of current parameter values."""
        return {p: getattr(self, p) for p in self.param if p != "name"}


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
