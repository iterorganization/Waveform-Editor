from pathlib import Path

import holoviews as hv
import imas
import panel as pn
import param
import scipy.constants
from panel.viewable import Viewer

from waveform_editor.gui.util import FormattedEditableFloatSlider
from waveform_editor.shape_editor.plasma_properties_calc import (
    compute_profiles_from_params,
)

_CARD_CSS = (Path(__file__).parent.parent / "styles" / "property_card.css").read_text()


def _make_badges(input_state_param, on_reset):
    """Create badge components wired to input_state_param and return them."""
    from_ids = pn.pane.HTML(
        '<span class="ids-badge from-ids">from IDS</span>',
        stylesheets=[_CARD_CSS],
        margin=(0, 0, 0, 4),
    )
    edited = pn.pane.HTML(
        '<span class="ids-badge edited">edited</span>',
        stylesheets=[_CARD_CSS],
        margin=(5, 0, 0, 4),
    )
    reset_btn = pn.widgets.Button(
        name="↺ Reset to IDS",
        button_type="light",
        width=120,
        margin=(0, 0, 0, 4),
    )
    reset_btn.on_click(lambda _: on_reset())
    is_from_ids = pn.bind(lambda s: s == "from_ids", input_state_param)
    is_edited = pn.bind(lambda s: s == "edited", input_state_param)
    from_ids.visible = is_from_ids
    edited.visible = is_edited
    reset_btn.visible = is_edited
    return from_ids, edited, reset_btn


class PropertyInput(Viewer):
    """A single scalar plasma property with an editable float input.

    Starts in plain manual mode. After a global IDS load via ``load_value``, the
    field shows a blue "from IDS" badge. Editing the value switches to an amber
    "edited" badge and surfaces a reset button to revert that field individually.
    """

    value = param.Number(default=0.0)
    ids_value = param.Number(default=None, allow_None=True, precedence=-1)
    resolved_value = param.Parameter(default=None, precedence=-1)
    changed = param.Event()
    input_state = param.String(default="manual", precedence=-1)

    def __init__(self, label, default_value, step=0.01, **params):
        super().__init__(**params)
        self._label = label
        self.value = default_value
        self.resolved_value = default_value

        self._value_input = pn.widgets.FloatInput.from_param(
            self.param.value,
            step=step,
            sizing_mode="stretch_width",
            margin=(4, 0, 0, 0),
        )
        self._from_ids_badge, self._edited_badge, self._reset_btn = _make_badges(
            self.param.input_state, self.reset_to_ids
        )

    def load_value(self, v):
        """Set value from a global IDS load and mark the field as 'from IDS'."""
        self.ids_value = v
        if self.value == v:
            # Param watcher only fires on actual changes; handle state manually.
            self.resolved_value = v
            self.input_state = "from_ids"
            self.param.trigger("changed")
        else:
            self.value = v  # triggers _on_value_change

    def reset_to_ids(self):
        if self.ids_value is not None:
            self.value = self.ids_value  # triggers _on_value_change

    @param.depends("value", watch=True)
    def _on_value_change(self):
        self.resolved_value = self.value
        if self.ids_value is not None:
            self.input_state = "from_ids" if self.value == self.ids_value else "edited"
        self.param.trigger("changed")

    def __panel__(self):
        badge_area = pn.Row(
            self._from_ids_badge,
            self._edited_badge,
            self._reset_btn,
            margin=0,
            align="center",
        )
        header = pn.Row(
            pn.pane.HTML(self._label, sizing_mode="stretch_width", margin=(5, 0)),
            badge_area,
            sizing_mode="stretch_width",
            margin=0,
        )
        return pn.Column(
            header,
            self._value_input,
            css_classes=["property-card"],
            stylesheets=[_CARD_CSS],
            max_width=600,
            margin=(0, 0, 8, 0),
        )


class PlasmaProfiles(Viewer):
    """Widget for plasma profile source: starts parametric, populates from IDS on load.

    After a global Load the profiles come from IDS ("from IDS" badge). Adjusting
    any slider recomputes profiles parametrically from alpha/beta/gamma and switches
    to an "edited" badge. Clicking Reset restores the IDS profiles.
    """

    alpha = param.Number(default=0.5, softbounds=[0.5, 2], step=0.01)
    beta = param.Number(default=0.5, softbounds=[0.5, 2], step=0.01)
    gamma = param.Number(default=1.0, softbounds=[0.5, 2], step=0.01)
    changed = param.Event()
    input_state = param.String(default="manual", precedence=-1)

    psi_norm = param.Parameter(default=None, precedence=-1)
    dpressure_dpsi = param.Parameter(default=None, precedence=-1)
    f_df_dpsi = param.Parameter(default=None, precedence=-1)
    r0 = param.Parameter(default=None, precedence=-1)
    has_properties = param.Boolean(default=False, precedence=-1)

    def __init__(self, **params):
        super().__init__(**params)
        self._ids_psi_norm = None
        self._ids_dpressure_dpsi = None
        self._ids_f_df_dpsi = None
        self._ids_load_alpha = self.alpha
        self._ids_load_beta = self.beta
        self._ids_load_gamma = self.gamma
        self._resetting = False

        self._alpha_input = FormattedEditableFloatSlider.from_param(
            self.param.alpha, name="Alpha", margin=0
        )
        self._beta_input = FormattedEditableFloatSlider.from_param(
            self.param.beta, name="Beta", margin=0
        )
        self._gamma_input = FormattedEditableFloatSlider.from_param(
            self.param.gamma, name="Gamma", margin=0
        )
        self._profiles_pane = pn.pane.HoloViews(
            hv.DynamicMap(self._plot_profiles), width=350, height=350
        )

        self._from_ids_badge, self._edited_badge, self._reset_btn = _make_badges(
            self.param.input_state, self.reset_to_ids
        )
        self._from_ids_badge.margin = (5, 0, 0, 4)
        self._use_parametric_btn = pn.widgets.Button(
            name="Use parametric",
            button_type="light",
            width=130,
            margin=(0, 0, 0, 4),
        )
        self._use_parametric_btn.on_click(lambda _: self._switch_to_parametric())
        self._use_parametric_btn.visible = pn.bind(
            lambda s: s == "from_ids", self.param.input_state
        )

    def _switch_to_parametric(self):
        self._reload_parametric()
        self.input_state = "edited"
        self.param.trigger("changed")

    def load_from_ids(self, uri, time):
        """Load profiles from IDS and mark as 'from IDS'."""
        if not uri:
            return
        try:
            with imas.DBEntry(uri, "r") as entry:
                eq = entry.get_slice(
                    "equilibrium",
                    time,
                    imas.ids_defs.CLOSEST_INTERP,
                    lazy=True,
                )
                self._ids_dpressure_dpsi = eq.time_slice[0].profiles_1d.dpressure_dpsi
                self._ids_f_df_dpsi = eq.time_slice[0].profiles_1d.f_df_dpsi
                psi = eq.time_slice[0].profiles_1d.psi
                self._ids_psi_norm = (psi - psi[0]) / (psi[-1] - psi[0])
        except Exception as e:
            pn.state.notifications.error(f"Could not load profiles from {uri}: {e}")
            return

        self._ids_load_alpha = self.alpha
        self._ids_load_beta = self.beta
        self._ids_load_gamma = self.gamma

        self.dpressure_dpsi = self._ids_dpressure_dpsi
        self.f_df_dpsi = self._ids_f_df_dpsi
        self.psi_norm = self._ids_psi_norm
        self.input_state = "from_ids"
        self.param.trigger("changed")

    def reset_to_ids(self):
        if self._ids_dpressure_dpsi is not None:
            self._resetting = True
            try:
                self.param.update(
                    alpha=self._ids_load_alpha,
                    beta=self._ids_load_beta,
                    gamma=self._ids_load_gamma,
                )
            finally:
                self._resetting = False
            self.dpressure_dpsi = self._ids_dpressure_dpsi
            self.f_df_dpsi = self._ids_f_df_dpsi
            self.psi_norm = self._ids_psi_norm
            self.input_state = "from_ids"
            self.param.trigger("changed")

    def _reload_parametric(self):
        if self.r0 is not None:
            try:
                self.psi_norm, self.dpressure_dpsi, self.f_df_dpsi = (
                    compute_profiles_from_params(
                        r0=self.r0,
                        alpha=self.alpha,
                        beta=self.beta,
                        gamma=self.gamma,
                    )
                )
            except Exception as e:
                pn.state.notifications.error(f"Could not compute profiles: {e}")
                self.psi_norm = self.dpressure_dpsi = self.f_df_dpsi = None
        else:
            self.psi_norm = self.dpressure_dpsi = self.f_df_dpsi = None

    @param.depends("alpha", "beta", "gamma", watch=True)
    def _on_slider_change(self):
        if self._resetting:
            return
        self._reload_parametric()
        if self._ids_dpressure_dpsi is not None:
            self.input_state = "edited"
        self.param.trigger("changed")

    @param.depends("r0", watch=True)
    def _on_r0_change(self):
        if self.input_state != "from_ids":
            self._reload_parametric()

    @pn.depends("psi_norm", "r0", "has_properties")
    def _plot_profiles(self):
        kdims = "Normalized Poloidal Flux"
        vdims = "Profile Value [A.U.]"
        if not self.has_properties:
            return hv.Overlay([hv.Curve([], kdims=kdims, vdims=vdims)])
        r0 = self.r0
        dpressure_dpsi_curve = hv.Curve(
            (self.psi_norm, self.dpressure_dpsi * r0),
            kdims=kdims,
            vdims=vdims,
            label="dpressure_dpsi * r₀",
        )
        f_df_dpsi_curve = hv.Curve(
            (self.psi_norm, self.f_df_dpsi / (scipy.constants.mu_0 * r0)),
            kdims=kdims,
            vdims=vdims,
            label="f_df_dpsi / (μ₀ * r₀)",
        )
        return (dpressure_dpsi_curve * f_df_dpsi_curve).opts(
            hv.opts.Overlay(title="Plasma Profiles"), hv.opts.Curve(framewise=True)
        )

    def __panel__(self):
        is_not_from_ids = pn.bind(lambda s: s != "from_ids", self.param.input_state)
        badge_area = pn.Row(
            self._from_ids_badge,
            self._edited_badge,
            self._reset_btn,
            self._use_parametric_btn,
            margin=0,
            align="center",
        )
        header = pn.Row(
            pn.pane.HTML("Profile source", sizing_mode="stretch_width", margin=(5, 0)),
            badge_area,
            sizing_mode="stretch_width",
            margin=0,
        )
        return pn.Column(
            header,
            pn.Column(
                self._alpha_input,
                self._beta_input,
                self._gamma_input,
                align="end",
                margin=(4, 0, 0, 0),
                visible=is_not_from_ids,
            ),
            self._profiles_pane,
            css_classes=["property-card"],
            stylesheets=[_CARD_CSS],
            max_width=600,
            margin=(0, 0, 8, 0),
        )


class PlasmaProperties(Viewer):
    """Assembles a shared IDS source, per-property inputs, and plasma profiles.

    One URI and time input at the top feeds all properties. Clicking Load populates
    every scalar field and the profile plot. Individual fields remain editable after
    loading and show state badges.
    """

    profile_updated = param.Event(
        doc="Triggered whenever the dpressure_dpsi and f_df_dpsi are updated."
    )
    has_properties = param.Boolean(doc="Whether the plasma properties are loaded.")
    ids_uri = param.String(default="")
    ids_time = param.Number(default=0.0)

    def __init__(self):
        super().__init__()
        self._ip = PropertyInput(
            "Plasma current [A]",
            default_value=-1.5e7,
            step=1e6,
        )
        self._r0 = PropertyInput(
            "Reference major radius [m]",
            default_value=6.2,
        )
        self._b0 = PropertyInput(
            "Toroidal magnetic field [T]",
            default_value=-5.3,
        )
        self._profiles = PlasmaProfiles()

        self._uri_input = pn.widgets.TextInput.from_param(
            self.param.ids_uri,
            name="IDS URI",
            placeholder="imas:?path=...",
            sizing_mode="stretch_width",
        )
        self._time_input = pn.widgets.FloatInput.from_param(
            self.param.ids_time, name="Time [s]", width=100
        )
        self._load_btn = pn.widgets.Button(
            name="Load", button_type="primary", width=80, margin=(28, 0, 0, 0)
        )
        self._load_btn.on_click(self._do_load)

        self.dpressure_dpsi = None
        self.f_df_dpsi = None
        self.psi_norm = None
        self.ip = None
        self.r0 = None
        self.b0 = None

        for widget in [self._ip, self._r0, self._b0, self._profiles]:
            widget.param.watch(self._load_plasma_properties, "changed")

        self._load_plasma_properties()

    _IDS_SCALAR_PATHS = [
        ("_ip", "time_slice(0)/global_quantities/ip"),
        ("_r0", "vacuum_toroidal_field/r0"),
        ("_b0", "vacuum_toroidal_field/b0(0)"),
    ]

    def _do_load(self, _event=None):
        """Load all scalar properties from the global IDS URI, then load profiles."""
        uri = self.ids_uri
        time = self.ids_time
        if not uri:
            pn.state.notifications.warning("Please enter an IDS URI first.")
            return
        try:
            with imas.DBEntry(uri, "r") as entry:
                eq = entry.get_slice(
                    "equilibrium",
                    time,
                    imas.ids_defs.CLOSEST_INTERP,
                    lazy=True,
                )
                for attr, path in self._IDS_SCALAR_PATHS:
                    try:
                        getattr(self, attr).load_value(float(eq[path]))
                    except Exception as e:
                        pn.state.notifications.error(f"Could not load {path}: {e}")
        except Exception as e:
            pn.state.notifications.error(f"Could not open IDS {uri}: {e}")
            return
        self._profiles.load_from_ids(uri, time)

    def _load_plasma_properties(self, _event=None):
        self.ip = self._ip.resolved_value
        self.r0 = self._r0.resolved_value
        self.b0 = self._b0.resolved_value

        self._profiles.r0 = self.r0
        self.psi_norm = self._profiles.psi_norm
        self.dpressure_dpsi = self._profiles.dpressure_dpsi
        self.f_df_dpsi = self._profiles.f_df_dpsi

        self.has_properties = all(
            v is not None for v in [self.ip, self.r0, self.b0, self.dpressure_dpsi]
        )
        self._profiles.has_properties = self.has_properties
        self.param.trigger("profile_updated")

    def __panel__(self):
        ids_source = pn.Column(
            pn.pane.HTML(
                "<b>Equilibrium IDS source</b>",
                margin=(0, 0, 6, 0),
            ),
            pn.Row(
                self._uri_input,
                self._time_input,
                self._load_btn,
                margin=0,
                align="end",
            ),
            css_classes=["property-card", "ids-source-card"],
            stylesheets=[_CARD_CSS],
            max_width=600,
            margin=(0, 0, 8, 0),
        )
        return pn.Column(
            ids_source,
            self._ip,
            self._r0,
            self._b0,
            self._profiles,
            sizing_mode="stretch_width",
            margin=(20, 20),
        )
