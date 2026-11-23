import numpy as np
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.shape_editor.gap_editor import GapEditor
from waveform_editor.gui.shape_editor.points_table import WeightedPointsTable
from waveform_editor.gui.shape_editor.reference_shape import ReferenceShape
from waveform_editor.gui.shape_editor.shape_params import PlasmaShapeParams
from waveform_editor.gui.shape_editor.shape_refinement import ShapeRefinement
from waveform_editor.gui.util import CARD_CSS, card
from waveform_editor.settings import NiceSettings, settings
from waveform_editor.shape_editor.gaps import MACHINE_GAPS
from waveform_editor.shape_editor.plasma_shape_calc import (
    compute_outline_from_params,
    fit_params_to_outline,
    x_points_from_params,
)

# Pixels high of the view switch and the button beside it, so that they line up
BUTTON_HEIGHT = 32


class PlasmaShape(Viewer):
    """The target shape of the plasma that NICE is given. It starts from a reference
    shape, and is changed with the parameterisation, with gaps, or as free points."""

    EDIT_REFERENCE = "Reference shape"
    EDIT_SLIDERS = "Shape parameterisation"
    EDIT_GAPS = "Target gaps"
    EDIT_POINTS = "Free points"
    edit_by = param.Selector(
        default=EDIT_REFERENCE,
        objects=[EDIT_REFERENCE, EDIT_SLIDERS, EDIT_GAPS, EDIT_POINTS],
    )
    points_table = param.ClassSelector(
        class_=WeightedPointsTable, default=WeightedPointsTable()
    )
    shape_params = param.ClassSelector(
        class_=PlasmaShapeParams, default=PlasmaShapeParams()
    )
    refinement = param.ClassSelector(class_=ShapeRefinement)
    has_shape = param.Boolean(doc="Whether a plasma shape is loaded.")
    shape_updated = param.Event(doc="Triggered whenever the plasma shape changes.")
    redraw = param.Event(doc="Triggered whenever what is drawn of the shape changes.")
    nice_settings = param.ClassSelector(class_=NiceSettings)

    @property
    def is_reference(self):
        """Whether the target shape is the reference shape itself."""
        return self.edit_by == self.EDIT_REFERENCE

    @property
    def is_points(self):
        """Whether the target shape is edited as free points."""
        return self.edit_by == self.EDIT_POINTS

    def __init__(self):
        super().__init__(nice_settings=settings.nice, refinement=ShapeRefinement())
        self.outline_r = None
        self.outline_z = None
        # Unduplicated parameterized boundary points and their per-point weight,
        # kept alongside the (possibly duplicated) outline_r/outline_z so the
        # plot can colour the boundary by weight. None when weighting is off.
        self.param_r = None
        self.param_z = None
        self.param_weights = None
        self.reference = ReferenceShape(
            on_set=self._take_reference, shape_params=self.shape_params
        )
        # Whether the parameterisation is still to be fitted to the reference shape
        self._fit_pending = False
        self.gaps = GapEditor(self.shape_params)
        # A double null has other gaps to fit to
        self.shape_params.param.watch(self._on_second_x_point, "second_x_point")
        edit_by = self.param.edit_by.rx()
        # The inputs of every view, of which only those of the view are shown, as
        # building them again for each view is slow
        edit_views = pn.Column(
            pn.Column(
                self.shape_params, visible=edit_by == self.EDIT_SLIDERS, margin=0
            ),
            pn.Column(self.gaps, visible=edit_by == self.EDIT_GAPS, margin=0),
            pn.Column(
                pn.Row(
                    pn.widgets.Button(
                        name="Fit parameterisation to points",
                        on_click=self._fit_to_points,
                        margin=(0, 10, 0, 0),
                    ),
                    pn.widgets.Button(
                        name="Clear points",
                        icon="trash",
                        on_click=lambda event: self.points_table.set_points([], [], []),
                        margin=0,
                    ),
                    margin=(0, 0, 8, 0),
                ),
                self.points_table,
                visible=edit_by == self.EDIT_POINTS,
                margin=0,
            ),
            pn.Column(
                # Only a parameterized boundary has a number of points
                self.shape_params.boundary_points_input(
                    visible=edit_by != self.EDIT_REFERENCE
                ),
                self.refinement,
                visible=edit_by != self.EDIT_POINTS,
                margin=0,
            ),
            margin=0,
        )
        self.panel = pn.Column(
            self.reference,
            card(
                "Target shape",
                pn.FlexBox(
                    pn.widgets.RadioButtonGroup.from_param(
                        self.param.edit_by,
                        name="",
                        # Free points are reached from these, and none is shown active
                        options=[
                            self.EDIT_REFERENCE,
                            self.EDIT_SLIDERS,
                            self.EDIT_GAPS,
                        ],
                        button_type="primary",
                        button_style="outline",
                        stylesheets=[CARD_CSS],
                        width=480,
                        height=BUTTON_HEIGHT,
                        margin=(0, 10, 8, 0),
                    ),
                    pn.widgets.Button(
                        name="Edit as free points",
                        icon="pencil",
                        button_type="primary",
                        button_style=(edit_by == self.EDIT_POINTS).rx.where(
                            "solid", "outline"
                        ),
                        stylesheets=[CARD_CSS],
                        height=BUTTON_HEIGHT,
                        on_click=self._edit_as_points,
                        disabled=edit_by == self.EDIT_POINTS,
                        margin=(0, 0, 8, 0),
                    ),
                    margin=0,
                ),
                edit_views,
                # Once a reference shape is set, and out of the way while another one
                # is chosen
                visible=pn.bind(
                    lambda origin, source: (
                        bool(origin) and source == ReferenceShape.SOURCE_NONE
                    ),
                    self.reference.param.origin,
                    self.reference.param.source,
                ),
            ),
            margin=(15, 20, 12, 20),
        )
        self.param.watch(self._on_edit_by, "edit_by")
        # One event for the plot, so that it can be drawn once for several changes
        self._hold_redraw = False

        def redraw(*events):
            if not self._hold_redraw:
                self.param.trigger("redraw")

        self.param.watch(redraw, ["shape_updated", "edit_by"])
        self.reference.param.watch(redraw, ["show", "preview", "source", "last_result"])
        # Last, because clearing the shape fires the watchers above
        self.nice_settings.param.watch(self._clear_reference, "machine_preset")
        self._clear_reference()

    @pn.depends(
        "shape_params.param",
        "points_table.param",
        "refinement.param",
        "refinement.extra_points_table.param",
        "edit_by",
        watch=True,
    )
    def _set_plasma_shape(self):
        """Update plasma boundary shape, triggering shape_updated only if it
        changed."""
        previous = (self.outline_r, self.outline_z, self.param_weights)
        self.param_r = self.param_z = self.param_weights = None
        if self.is_points:
            self.outline_r, self.outline_z = self.points_table.get_outline_coordinates()
        elif self.reference.r is None:  # no reference shape is set yet
            self.outline_r = self.outline_z = None
        elif self.is_reference:
            self._refine_shape(self.reference.r, self.reference.z)
        else:
            self._refine_shape(
                *compute_outline_from_params(**self.shape_params.outline_arguments())
            )
        self.has_shape = bool(self.outline_r and self.outline_z)
        current = (self.outline_r, self.outline_z, self.param_weights)
        if not all(map(np.array_equal, previous, current)):
            self.param.trigger("shape_updated")

    @property
    def target_x_points(self):
        """The x-points of the target shape, which only a parameterized shape has."""
        if self.is_reference or self.is_points:
            return []
        return x_points_from_params(self.shape_params.outline_arguments())

    @property
    def active_points_table(self):
        """The point table the plot edits, None when no points are in use."""
        if self.is_points:
            return self.points_table
        if self.refinement.extra_points_enabled:
            return self.refinement.extra_points_table
        return None

    def _take_reference(self):
        """Give NICE the reference shape just set, as it is. The parameterisation is
        fitted to that of an equilibrium once it is used."""
        # The plot is drawn once, for all that changes
        self._hold_redraw = True
        try:
            if not self.reference.of_equilibrium:  # the machine default
                self.shape_params.apply_machine_shape()
            self._fit_pending = self.reference.of_equilibrium
            # Out of the way until the reference is changed again
            self.reference.source = ReferenceShape.SOURCE_NONE
            self._start_editing()
        finally:
            self._hold_redraw = False
            self.param.trigger("redraw")

    def _clear_reference(self, event=None):
        """Start without a reference shape, for one to be chosen first."""
        self.shape_params.apply_machine_shape(values=False)
        self.reference.clear()
        self._fit_pending = False
        self._start_editing()

    def _start_editing(self):
        """Give NICE the new reference as it is."""
        self.edit_by = self.EDIT_REFERENCE
        self.param.trigger("edit_by")  # also when it was, to take the new reference

    def _refine_shape(self, r, z):
        """The outline NICE is given from a boundary: with its emphasized region and
        extra points."""
        self.param_r, self.param_z = r, z
        self.outline_r, self.outline_z, self.param_weights = self.refinement.refine(
            r, z
        )

    def _edit_as_points(self, event=None):
        """Edit the target shape as it is, with its weights and extra points, as free
        points."""
        if self.is_points:  # a second click, before it was disabled
            return
        r, z = list(self.param_r), list(self.param_z)
        weights = (
            [1] * len(r) if self.param_weights is None else list(self.param_weights)
        )
        if self.refinement.extra_points_enabled:
            extra_r, extra_z, extra_weights = (
                self.refinement.extra_points_table.get_points()
            )
            r, z, weights = r + extra_r, z + extra_z, weights + extra_weights
        self.points_table.set_points(r, z, weights)
        self.edit_by = self.EDIT_POINTS

    def _fit_to_points(self, event=None):
        """Fit the parameterisation to the free points, and show it."""
        x_points = (
            x_points_from_params(self.shape_params.outline_arguments())
            if self.shape_params.second_x_point
            else ()
        )
        r, z = self.points_table.get_points()[:2]
        if self._fit_to(r, z, "the free points", x_points):
            self._fit_pending = False  # the free points are newer than the reference
            self.edit_by = self.EDIT_SLIDERS

    def _fit_to(self, r, z, fitted_to, x_points=()):
        """Fit the parameterisation to an outline, warning when it misses it.

        Args:
            r: Radial coordinates of the outline.
            z: Height coordinates of the outline.
            fitted_to: What the outline is, for the warning.
            x_points: The (r, z) of its x-points, if known.

        Returns:
            Whether it could be fitted.
        """
        if len(r) < 3:
            pn.state.notifications.error("At least 3 points are needed to fit to")
            return False
        p = self.shape_params
        x_points = sorted(x_points, key=lambda point: point[1])  # the lower one first
        fitted, distances = fit_params_to_outline(
            r, z, p.n_desired_bnd_points, x_points
        )
        if distances.max() > p.FIT_TOLERANCE:
            pn.state.notifications.warning(
                f"The shape parameterisation misses {fitted_to} by up to "
                f"{distances.max() * 100:.1f} cm"
            )
        top = np.argmax(z)
        # A single null is ready for a double null: the second x-point at the top
        rx_upper, zx_upper = x_points[1] if len(x_points) > 1 else (r[top], z[top])
        p.param.update(
            **{name: fitted[name] for name in p.FIT_PARAMS},
            second_x_point=len(x_points) > 1,
            rx_upper=float(rx_upper),
            zx_upper=float(zx_upper),
        )
        return True

    def _on_edit_by(self, event):
        """The parameterisation is fitted to the reference shape of an equilibrium
        when it is first used."""
        self.reference.is_target = event.new == self.EDIT_REFERENCE
        if event.new in (self.EDIT_SLIDERS, self.EDIT_GAPS) and self._fit_pending:
            self._fit_pending = False
            ref = self.reference
            self._fit_to(ref.r, ref.z, "the reference shape", ref.x_points)
        if event.new == self.EDIT_GAPS:
            if self.nice_settings.machine_preset not in MACHINE_GAPS:
                pn.state.notifications.warning(
                    "Gaps are only defined for the ITER and WEST presets"
                )
                self.edit_by = self.EDIT_SLIDERS
                return
            self.gaps.create_sliders()

    def _on_second_x_point(self, event):
        """Make the gap sliders those of a single or double null."""
        if self.edit_by == self.EDIT_GAPS:
            self.gaps.create_sliders()

    def __panel__(self):
        return self.panel
