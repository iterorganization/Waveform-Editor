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

MANUAL = "Manual"
EQ_IDS = "Equilibrium IDS"
PARAMETRIC = "Parametric"

_CARD_CSS = (Path(__file__).parent.parent / "styles" / "property_card.css").read_text()


class PropertyInput(Viewer):
    """A single scalar plasma property with its own Manual / Eq IDS mode toggle."""

    mode = param.Selector(default=MANUAL, objects=[MANUAL, EQ_IDS])
    value = param.Number(default=0.0)
    ids_uri = param.String(default="")
    ids_time = param.Number(default=0.0)
    loaded_value = param.Number(default=None, allow_None=True, precedence=-1)
    resolved_value = param.Parameter(default=None, precedence=-1)
    changed = param.Event()

    def __init__(self, label, default_value, ids_path, step=0.01, **params):
        """
        Parameters
        ----------
        label:
            Display label shown in the card header.
        default_value:
            Initial value used in Manual mode.
        ids_path:
            Dot-path into the equilibrium IDS used in Eq IDS mode, e.g.
            ``"vacuum_toroidal_field.r0"``.
        step:
            Step size for the numeric input widget.
        """
        super().__init__(**params)
        self._ids_path = ids_path
        self.value = default_value
        self._label = label

        self._mode_toggle = pn.widgets.RadioButtonGroup.from_param(
            self.param.mode,
            button_style="outline",
            button_type="primary",
            stylesheets=[_CARD_CSS],
        )
        self._value_input = pn.widgets.FloatInput.from_param(
            self.param.value,
            step=step,
            sizing_mode="stretch_width",
            margin=(4, 0, 0, 0),
        )
        self._uri_input = pn.widgets.TextInput.from_param(
            self.param.ids_uri,
            name="IDS URI",
            sizing_mode="stretch_width",
        )
        self._time_input = pn.widgets.FloatInput.from_param(
            self.param.ids_time, name="Time [s]", width=100
        )
        self._reload()

    def _reload(self):
        if self.mode == MANUAL:
            self.resolved_value = self.value
            return
        if not self.ids_uri:
            self.resolved_value = None
            return
        try:
            with imas.DBEntry(self.ids_uri, "r") as entry:
                eq = entry.get_slice(
                    "equilibrium",
                    self.ids_time,
                    imas.ids_defs.CLOSEST_INTERP,
                    lazy=True,
                )
                self.loaded_value = self.resolved_value = float(eq[self._ids_path])
        except Exception as e:
            pn.state.notifications.error(f"Could not load from {self.ids_uri}: {e}")
            self.loaded_value = None
            self.resolved_value = None

    @param.depends("mode", "value", "ids_uri", "ids_time", watch=True)
    def _on_change(self):
        self._reload()
        self.param.trigger("changed")

    @param.depends("loaded_value")
    def _loaded_display(self):
        """Render a small label showing the last value loaded from IDS."""
        if self.loaded_value is None:
            return ""
        html = (
            f'<span style="color:#666;font-size:0.85em;">'
            f"Loaded: {self.loaded_value:.4g}</span>"
        )
        return pn.pane.HTML(html, margin=(2, 0, 0, 0))

    def __panel__(self):
        is_manual = pn.bind(lambda m: m == MANUAL, self.param.mode)
        is_ids = pn.bind(lambda m: m == EQ_IDS, self.param.mode)
        self._value_input.visible = is_manual
        header = pn.Row(
            pn.pane.HTML(self._label, sizing_mode="stretch_width", margin=(5, 0)),
            self._mode_toggle,
            sizing_mode="stretch_width",
            margin=0,
        )
        return pn.Column(
            header,
            self._value_input,
            pn.Column(
                pn.Row(self._uri_input, self._time_input, margin=(4, 0, 0, 0)),
                self._loaded_display,
                visible=is_ids,
                margin=0,
            ),
            css_classes=["property-card"],
            stylesheets=[_CARD_CSS],
            max_width=600,
            margin=(0, 0, 8, 0),
        )


class PlasmaProfiles(Viewer):
    """Widget for selecting the plasma profile source: parametric or from IDS.

    In Parametric mode, dpressure_dpsi and f_df_dpsi are computed analytically
    from alpha/beta/gamma shape parameters. In Eq IDS mode, they are read
    directly from an equilibrium IDS file.
    """

    mode = param.Selector(default=PARAMETRIC, objects=[PARAMETRIC, EQ_IDS])
    alpha = param.Number(default=0.5, softbounds=[0.5, 2], step=0.01)
    beta = param.Number(default=0.5, softbounds=[0.5, 2], step=0.01)
    gamma = param.Number(default=1.0, softbounds=[0.5, 2], step=0.01)
    ids_uri = param.String(default="")
    ids_time = param.Number(default=0.0)
    changed = param.Event()

    # Resolved profile data, updated by _reload()
    psi_norm = param.Parameter(default=None, precedence=-1)
    dpressure_dpsi = param.Parameter(default=None, precedence=-1)
    f_df_dpsi = param.Parameter(default=None, precedence=-1)
    r0 = param.Parameter(default=None, precedence=-1)
    has_properties = param.Boolean(default=False, precedence=-1)

    def __init__(self, **params):
        super().__init__(**params)

        self._mode_toggle = pn.widgets.RadioButtonGroup.from_param(
            self.param.mode,
            button_style="outline",
            button_type="primary",
            stylesheets=[_CARD_CSS],
        )
        self._alpha_input = FormattedEditableFloatSlider.from_param(
            self.param.alpha, name="Alpha", margin=0
        )
        self._beta_input = FormattedEditableFloatSlider.from_param(
            self.param.beta, name="Beta", margin=0
        )
        self._gamma_input = FormattedEditableFloatSlider.from_param(
            self.param.gamma, name="Gamma", margin=0
        )
        self._uri_input = pn.widgets.TextInput.from_param(
            self.param.ids_uri,
            name="IDS URI",
            sizing_mode="stretch_width",
        )
        self._time_input = pn.widgets.FloatInput.from_param(
            self.param.ids_time, name="Time [s]", width=100
        )
        self._profiles_pane = pn.pane.HoloViews(
            hv.DynamicMap(self._plot_profiles), width=350, height=350
        )

    def _reload(self, r0):
        """Resolve profile functions from parametric params or an equilibrium IDS.

        Called by PlasmaProperties after it resolves r0. Results are stored in
        `psi_norm`, `dpressure_dpsi`, and `f_df_dpsi`.
        """
        self.r0 = r0
        if self.mode == EQ_IDS:
            self._load_from_ids()
        elif r0 is not None:
            try:
                self.psi_norm, self.dpressure_dpsi, self.f_df_dpsi = (
                    compute_profiles_from_params(
                        r0=r0,
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

    def _load_from_ids(self):
        """Load dpressure_dpsi, f_df_dpsi, and psi_norm from an equilibrium IDS."""
        if not self.ids_uri:
            self.psi_norm = self.dpressure_dpsi = self.f_df_dpsi = None
            return
        try:
            with imas.DBEntry(self.ids_uri, "r") as entry:
                eq = entry.get_slice(
                    "equilibrium",
                    self.ids_time,
                    imas.ids_defs.CLOSEST_INTERP,
                    lazy=True,
                )
                self.dpressure_dpsi = eq.time_slice[0].profiles_1d.dpressure_dpsi
                self.f_df_dpsi = eq.time_slice[0].profiles_1d.f_df_dpsi
                psi = eq.time_slice[0].profiles_1d.psi
                self.psi_norm = (psi - psi[0]) / (psi[-1] - psi[0])
        except Exception as e:
            pn.state.notifications.error(
                f"Could not load profiles from {self.ids_uri}: {e}"
            )
            self.psi_norm = self.dpressure_dpsi = self.f_df_dpsi = None

    @param.depends("mode", "alpha", "beta", "gamma", "ids_uri", "ids_time", watch=True)
    def _on_change(self):
        self.param.trigger("changed")

    @pn.depends("psi_norm", "has_properties")
    def _plot_profiles(self):
        """Plot dpressure_dpsi and f_df_dpsi vs normalised poloidal flux."""
        # Define kdims/vdims explicitly
        # to prevent HoloViews linking axes with the flux map
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
        is_parametric = pn.bind(lambda m: m == PARAMETRIC, self.param.mode)
        is_ids = pn.bind(lambda m: m == EQ_IDS, self.param.mode)
        header = pn.Row(
            pn.pane.HTML("Profile source", sizing_mode="stretch_width", margin=(5, 0)),
            self._mode_toggle,
            sizing_mode="stretch_width",
            margin=0,
        )
        return pn.Column(
            header,
            pn.Column(
                self._alpha_input,
                self._beta_input,
                self._gamma_input,
                visible=is_parametric,
                align="end",
                margin=(4, 0, 0, 0),
            ),
            pn.Column(
                self._uri_input,
                self._time_input,
                visible=is_ids,
                margin=(4, 0, 0, 0),
            ),
            self._profiles_pane,
            css_classes=["property-card"],
            stylesheets=[_CARD_CSS],
            max_width=600,
            margin=(0, 0, 8, 0),
        )


class PlasmaProperties(Viewer):
    """Assembles per-property inputs; exposes resolved plasma scalars and profiles.

    Each scalar (ip, r0, b0) can independently source its value from manual input or
    an equilibrium IDS. Profile functions (dpressure_dpsi, f_df_dpsi) can be computed
    parametrically or read from an IDS via the PlasmaProfiles widget.
    """

    profile_updated = param.Event(
        doc="Triggered whenever the dpressure_dpsi and f_df_dpsi are updated."
    )
    has_properties = param.Boolean(doc="Whether the plasma properties are loaded.")

    def __init__(self):
        super().__init__()
        self._ip = PropertyInput(
            "Plasma current [A]",
            default_value=-1.5e7,
            ids_path="time_slice[0].global_quantities.ip",
            step=1e6,
        )
        self._r0 = PropertyInput(
            "Reference major radius [m]",
            default_value=6.2,
            ids_path="vacuum_toroidal_field.r0",
        )
        self._b0 = PropertyInput(
            "Toroidal magnetic field [T]",
            default_value=-5.3,
            ids_path="vacuum_toroidal_field.b0[0]",
        )
        self._profiles = PlasmaProfiles()

        self.dpressure_dpsi = None
        self.f_df_dpsi = None
        self.psi_norm = None
        self.ip = None
        self.r0 = None
        self.b0 = None

        for widget in [self._ip, self._r0, self._b0, self._profiles]:
            widget.param.watch(self._load_plasma_properties, "changed")

        self._load_plasma_properties()

    def _load_plasma_properties(self, _event=None):
        """Reload all plasma properties from the current mode and inputs.

        Reads already-resolved scalar values from each PropertyInput, delegates
        profile loading/computation to PlasmaProfiles, then triggers `profile_updated`.
        """
        self.ip = self._ip.resolved_value
        self.r0 = self._r0.resolved_value
        self.b0 = self._b0.resolved_value

        self._profiles._reload(self.r0)
        self.psi_norm = self._profiles.psi_norm
        self.dpressure_dpsi = self._profiles.dpressure_dpsi
        self.f_df_dpsi = self._profiles.f_df_dpsi

        self.has_properties = all(
            v is not None for v in [self.ip, self.r0, self.b0, self.dpressure_dpsi]
        )
        self._profiles.has_properties = self.has_properties
        self.param.trigger("profile_updated")

    def __panel__(self):
        return pn.Column(
            self._ip,
            self._r0,
            self._b0,
            self._profiles,
            sizing_mode="stretch_width",
            margin=(20, 20),
        )
