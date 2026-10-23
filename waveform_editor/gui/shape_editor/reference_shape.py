import imas
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.shape_editor.shape_params import (
    MACHINE_SHAPES,
    PlasmaShapeParams,
)
from waveform_editor.gui.util import EquilibriumInput, card
from waveform_editor.settings import NiceSettings, settings
from waveform_editor.shape_editor.plasma_shape_calc import compute_outline_from_params


class ReferenceShape(Viewer):
    """The shape the target shape starts from, chosen from a source and previewed on
    the plot before it is set."""

    SOURCE_NONE = "Choose a reference…"
    SOURCE_DEFAULT = "Machine default"
    SOURCE_IDS = "Equilibrium IDS"
    SOURCE_RESULT = "NICE result"
    source = param.Selector(
        default=SOURCE_NONE,
        objects=[SOURCE_NONE, SOURCE_DEFAULT, SOURCE_IDS, SOURCE_RESULT],
    )
    input_outline = param.ClassSelector(
        class_=EquilibriumInput, default=EquilibriumInput()
    )
    last_result = param.Parameter(
        default=None, precedence=-1, doc="The converged equilibrium of the last run."
    )
    preview = param.Parameter(
        default=None, precedence=-1, doc="The equilibrium IDS loaded, before it is set."
    )
    show = param.Boolean(default=True, label="Show reference shape")
    is_target = param.Boolean(
        precedence=-1, doc="Whether the target shape is the reference itself."
    )
    origin = param.String(precedence=-1, doc="Where the reference is from.")
    shape_params = param.ClassSelector(class_=PlasmaShapeParams)
    nice_settings = param.ClassSelector(class_=NiceSettings)

    def __init__(self, on_set, **params):
        """
        Args:
            on_set: Called when the reference shape of the chosen source is set.
        """
        super().__init__(nice_settings=settings.nice, **params)
        self._on_set = on_set
        # The outline set, its x-point if known, and whether it is of an equilibrium
        self.r = self.z = self.x_point = None
        self.of_equilibrium = False
        self.input_outline.param.watch(self._load_preview, "load")
        self._source_select = pn.widgets.Select.from_param(
            self.param.source,
            name="",
            # SOURCE_NONE is only shown while no source is chosen
            stylesheets=["option:first-child { display: none; }"],
            margin=(0, 10, 8, 0),
        )
        self.nice_settings.param.watch(self._update_sources, "machine_preset")
        self.param.watch(self._update_sources, "last_result")
        self._update_sources()

    @property
    def candidate_outline(self):
        """The (r, z) of the reference shape of the chosen source, None if no source
        is chosen or it has no shape yet, such as an equilibrium IDS not loaded."""
        if self.source == self.SOURCE_DEFAULT:
            shape = MACHINE_SHAPES[self.nice_settings.machine_preset]
            return compute_outline_from_params(
                **{
                    **{name: value for name, (value, _) in shape.items()},
                    # A single null, as the parameterisation starts from
                    "rx_upper": None,
                    "zx_upper": None,
                    "n_desired_bnd_points": self.shape_params.n_desired_bnd_points,
                }
            )
        if (equilibrium := self._source_equilibrium) is None:
            return None
        outline = equilibrium.time_slice[0].boundary.outline
        return outline.r, outline.z

    @property
    def _source_equilibrium(self):
        """The equilibrium IDS of the chosen source, None if it has none (yet)."""
        sources = {self.SOURCE_RESULT: self.last_result, self.SOURCE_IDS: self.preview}
        return sources.get(self.source)

    def _update_sources(self, event=None):
        """Disable the sources there is nothing to take the reference from."""
        unavailable = []
        if self.nice_settings.machine_preset not in MACHINE_SHAPES:
            unavailable.append(self.SOURCE_DEFAULT)
        if self.last_result is None:
            unavailable.append(self.SOURCE_RESULT)
        if self.source in unavailable:
            self.source = self.SOURCE_NONE
        self._source_select.disabled_options = unavailable

    def _set(self, event=None):
        """Set the reference shape of the chosen source."""
        r, z = self.candidate_outline
        if len(r) < 3:
            pn.state.notifications.error("The equilibrium has no boundary outline")
            return
        equilibrium = self._source_equilibrium
        self.x_point = None
        if equilibrium is not None:
            nodes = equilibrium.time_slice[0].contour_tree.node
            # The primary x-point is node 1, see the Data Dictionary
            if len(nodes) > 1 and nodes[1].critical_type == 1:
                self.x_point = (float(nodes[1].r), float(nodes[1].z))
        self.r, self.z = list(r), list(z)
        self.of_equilibrium = equilibrium is not None
        self.origin = {
            self.SOURCE_DEFAULT: f"{self.nice_settings.machine_preset} default",
            self.SOURCE_RESULT: "NICE result",
            self.SOURCE_IDS: (
                f"{self.input_outline.uri} at t = {self.input_outline.time:g} s"
            ),
        }[self.source]
        self._on_set()

    def clear(self):
        """Have no reference shape, for one to be chosen first."""
        self.r = self.z = None
        self.param.update(origin="", source=self.SOURCE_NONE)

    @param.depends("source", watch=True)
    def _on_source(self):
        """The loaded equilibrium IDS is only drawn, as the reference, while it can be
        set."""
        if self.source == self.SOURCE_IDS:
            self.show = True
            if self.input_outline.times:  # an IDS entered before, loaded again
                self._load_preview()
        else:
            self.preview = None

    def _load_preview(self, event=None):
        """Load the entered equilibrium IDS, to see it on the plot before it is set."""
        try:
            with imas.DBEntry(self.input_outline.uri, "r") as entry:
                self.preview = entry.get_slice(
                    "equilibrium", self.input_outline.time, imas.ids_defs.CLOSEST_INTERP
                )
        except Exception as e:
            self.preview = None
            pn.state.notifications.error(
                f"Could not load the equilibrium from {self.input_outline.uri}: {e}"
            )

    def __panel__(self):
        return card(
            self.param.origin.rx().rx.pipe(
                lambda origin: (
                    f"Reference shape: {origin}" if origin else "Reference shape"
                )
            ),
            pn.Row(
                self._source_select,
                pn.widgets.Checkbox.from_param(
                    self.param.show,
                    # When the reference is the target shape itself, or the
                    # equilibrium IDS being chosen, which is always shown
                    disabled=pn.bind(
                        lambda is_target, source: (
                            is_target or source == self.SOURCE_IDS
                        ),
                        self.param.is_target,
                        self.param.source,
                    ),
                    align="center",
                    margin=(0, 0, 8, 0),
                ),
                margin=0,
            ),
            pn.Column(
                self.input_outline,
                visible=self.param.source.rx() == self.SOURCE_IDS,
                sizing_mode="stretch_width",
                margin=0,
            ),
            pn.widgets.Button(
                name="Set reference shape",
                button_type="primary",
                # Until there is a reference shape to set
                disabled=pn.bind(
                    lambda source, preview: (
                        source == self.SOURCE_NONE
                        or (source == self.SOURCE_IDS and preview is None)
                    ),
                    self.param.source,
                    self.param.preview,
                ),
                margin=0,
                on_click=self._set,
            ),
        )
