import panel as pn
import param
from panel.viewable import Viewer


class YamlGlobalsDialog(Viewer):
    visible = param.Boolean(allow_refs=True)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.modal = pn.Modal(pn.Param(self.config.globals, name="YAML Globals"))

        self.button = pn.widgets.ButtonIcon(
            icon="settings",
            size="20px",
            active_icon="settings-filled",
            description="Change YAML global parameters",
            on_click=lambda event: self.modal.show(),
            visible=self.param.visible,
        )

        for param_name in self.config.globals.param:
            if param_name != "name":
                self.config.globals.param.watch(self._on_param_change, param_name)

    def _on_param_change(self, event):
        self.config.has_changed = True

    def __panel__(self):
        return pn.Column(self.button, self.modal)
