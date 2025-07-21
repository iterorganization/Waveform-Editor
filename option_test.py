import os

import panel as pn
import param
import yaml

CONFIG_FILE = (
    "/home/sebbe/projects/iter_python/Waveform-Editor/waveform_editor_options.yaml"
)


class NiceOptions(param.Parameterized):
    executable = param.String(
        label="NICE executable path",
        default="nice_imas_inv_muscle3",
    )
    environment = param.Dict(
        label="NICE environment variables",
        default={"ENV1": 0, "ENV2": "a"},
    )
    modules = param.List(
        label="NICE modules",
        default=["MUSCLE3"],
    )
    md_pf_active = param.String(
        label="pf_active machine description URI",
        default="imas:hdf?path=/path/to/pf_active",
    )
    md_pf_passive = param.String(
        label="pf_passive machine description URI",
        default="imas:hdf?path=/path/to/pf_passive",
    )
    md_wall = param.String(
        label="wall machine description URI",
        default="imas:hdf?path=/path/to/wall",
    )
    md_iron_core = param.String(
        label="iron_core machine description URI",
        default="imas:hdf?path=/path/to/iron_core",
    )
    test_float = param.Number(
        label="Test float",
        default=1.234,
    )
    test_int = param.Integer(label="Test Integer", bounds=[0, 5], default=1)

    def update(self, params):
        self.param.update(**params)

    def to_dict(self):
        return {p: getattr(self, p) for p in self.param if p != "name"}


class UserConfig(param.Parameterized):
    gs_solver = param.Selector(objects=["NICE", "CHEASE"], default="NICE")

    nice = param.ClassSelector(class_=NiceOptions, default=NiceOptions())

    default_export = param.String(
        label="Default Export URI",
        default="imas:hdf5?path=./test",
    )

    def __init__(self, **params):
        super().__init__(**params)
        self._load_settings()
        self._save_settings()
        self.param.watch(self._save_settings, list(self.param))
        self.nice.param.watch(self._save_settings, list(self.nice.param))

    def _load_settings(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                settings = yaml.safe_load(f) or {}
        else:
            settings = {}

        if "nice" in settings:
            self.nice.update(settings["nice"])

        base_settings = {k: v for k, v in settings.items() if k != "nice"}
        self.param.update(**base_settings)

    def _save_settings(self, event=None):
        config = {
            p: getattr(self, p) for p in self.param if p != "name" and p != "nice"
        }

        if self.gs_solver == "NICE":
            config["nice"] = self.nice.to_dict()

        with open(CONFIG_FILE, "w") as f:
            yaml.safe_dump(config, f)

    @param.depends("gs_solver")
    def panel(self):
        params_to_show = [p for p in self.param if p != "nice" and p != "name"]
        base_ui = pn.Param(self.param, parameters=params_to_show)
        if self.gs_solver == "NICE":
            nice_ui = pn.panel(self.nice.param, expand_button=False, expand=True)
            return pn.Column(base_ui, pn.Spacer(height=10), nice_ui)
        else:
            return base_ui


config = UserConfig()
pn.panel(config.panel).servable()
