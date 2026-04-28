import panel as pn
import param


class WaveformSidebar(param.Parameterized):
    _open = param.Boolean(default=True)

    def __init__(self, io_manager, selector, confirm_modal, rename_modal):
        super().__init__()

        toggle_btn = pn.widgets.Button(
            name="◀",
            button_type="light",
            width=40,
            align=pn.bind(lambda v: "start" if v else "center", self.param._open),
        )
        toggle_btn.on_click(lambda _: setattr(self, "_open", not self._open))
        self.param.watch(
            lambda e: toggle_btn.param.update(name="◀" if e.new else "▶"),
            "_open",
        )

        content = pn.Column(
            io_manager,
            selector,
            confirm_modal,
            rename_modal,
            sizing_mode="stretch_width",
            scroll=True,
            visible=pn.bind(lambda v: v, self.param._open),
        )

        self._layout = pn.Column(toggle_btn, content, sizing_mode="stretch_width")

    def __panel__(self):
        return self._layout
