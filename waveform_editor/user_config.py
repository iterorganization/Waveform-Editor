import param

# CONFIG_FILE = ($XDG_CONFIG_HOME or $HOME/.config)/waveform_editor.yaml


class ShapeConfig(param.Parametrized):
    gs_solver = param.Option("NICE")

    nice_executable = param.String(
        default="nice_imas_inv_muscle3",
        documentation="Path to NICE inverse IMAS MUSCLE3 executable",
    )
    nice_environment = "..."
    nice_modules = (
        "MUSCLE3 IMAS/4.0.0-2024.12-intel-2023b SuiteSparse/7.7.0-intel-2023b"
    )


class UserConfig(param.Parameterized):
    """
    Automatic UI: https://panel.holoviz.org/how_to/param/uis.html
    Nested UI? https://panel.holoviz.org/how_to/param/subobjects.html
    """

    ...

    shapeconfig = param.Select(ShapeConfig())

    def __init__(self):
        settings = read(CONFIG_FILE)
        super().__init__(**settings)
        for param in self.param.xyz:
            param.watch(self.save_settings)

    @param.depends("*")
    def save_settings(self):
        store(CONFIG_FILE, self.param)


config = UserConfig()
