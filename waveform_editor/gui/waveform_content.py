import panel as pn
import param

from waveform_editor.gui.sidebar import WaveformSidebar

WAVEFORM_EDITOR_PAGE = "Waveform Editor"
PLASMA_EDITOR_PAGE = "Plasma Shape Editor"


class WaveformContent(param.Parameterized):
    def __init__(
        self, nav, io_manager, selector, confirm_modal, rename_modal, tabs, shape_editor
    ):
        super().__init__()

        sidebar = WaveformSidebar(io_manager, selector, confirm_modal, rename_modal)

        is_waveform_page = pn.bind(lambda page: page == WAVEFORM_EDITOR_PAGE, nav)
        is_plasma_page = pn.bind(lambda page: page == PLASMA_EDITOR_PAGE, nav)

        _no_shadow = {"box-shadow": "none", "overflow": "hidden"}
        sidebar_card = pn.Card(
            sidebar,
            hide_header=True,
            width=pn.bind(lambda v: 400 if v else 50, sidebar.param.open),
            sizing_mode="stretch_height",
            styles=_no_shadow,
        )
        tabs_card = pn.Card(
            tabs,
            hide_header=True,
            sizing_mode="stretch_both",
            styles=_no_shadow,
        )

        # Both pages stay in the DOM so Bokeh plots keep their layout context.
        # Switching pages toggles visibility rather than swapping elements.
        waveform_page = pn.Row(
            sidebar_card,
            tabs_card,
            sizing_mode="stretch_both",
            visible=is_waveform_page,
        )
        plasma_page = pn.Column(
            shape_editor, sizing_mode="stretch_both", visible=is_plasma_page
        )
        self._layout = pn.Column(waveform_page, plasma_page, sizing_mode="stretch_both")

    def __panel__(self):
        return self._layout
