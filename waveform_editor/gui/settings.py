"""Panel rendering functions for settings objects."""

import panel as pn
import param

from waveform_editor.gui.util import WarningIndicator
from waveform_editor.settings import NiceSettings, UserSettings


def nice_settings_panel(nice_settings: NiceSettings) -> pn.Column:
    """Render a NiceSettings instance as a Panel column.

    Adds a warning indicator next to required fields that are not yet filled.

    Args:
        nice_settings: The NiceSettings instance to render.

    Returns:
        A Panel Column containing all settings fields.
    """
    items = []

    for p in nice_settings.param:
        if p == "name":
            continue

        is_inv_required = p == "inv_executable" and nice_settings.is_inverse_mode
        is_dir_required = p == "dir_executable" and nice_settings.is_direct_mode
        is_base_required = p in nice_settings.BASE_REQUIRED

        row_content = [pn.Param(nice_settings.param[p], show_name=False)]
        if is_inv_required or is_dir_required or is_base_required:
            warning = WarningIndicator(visible=nice_settings.param[p].rx.not_())
            row_content.append(warning)

        items.append(pn.Row(*row_content))

    return pn.Column(*items)


@param.depends("settings.gs_solver")
def user_settings_panel(settings: UserSettings) -> pn.viewable.Viewable:
    """Render a UserSettings instance as a Panel layout.

    Args:
        settings: The UserSettings instance to render.

    Returns:
        A Panel layout containing all user settings.
    """
    params_to_show = [p for p in settings.param if p != "nice" and p != "name"]
    base_ui = pn.Param(settings.param, parameters=params_to_show)
    if settings.gs_solver == "NICE":
        nice_ui = pn.panel(settings.nice.param, expand_button=False, expand=True)
        return pn.Column(base_ui, pn.Spacer(height=10), nice_ui)
    return base_ui
