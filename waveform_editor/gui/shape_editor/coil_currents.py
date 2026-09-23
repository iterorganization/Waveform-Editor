import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import panel as pn
import param
from bokeh.models.widgets.tables import NumberFormatter
from panel.viewable import Viewer

from waveform_editor.settings import settings


class CoilCurrentEntry(param.Parameterized):
    coil_name = param.String()
    fix_current = param.Boolean(default=False)
    current = param.Number(default=None)
    previous_current = param.Number(default=None)
    current_limit = param.Number(
        default=None,
        doc="Largest current this coil tolerates, None if the machine description "
        "does not say.",
    )
    penalize_to_zero = param.Boolean(
        default=False,
        doc="Penalize this coil's current towards 0 instead of towards the current "
        "it was loaded with.",
    )
    penalty_weight = param.Number(
        default=1.0,
        doc="NICE's group_special_weight. Below 1 weighs this coil's current more "
        "heavily, holding it closer to what it is penalized towards.",
    )

    @property
    def exceeds_limit(self):
        """Whether the current is beyond what the coil tolerates, in either
        direction. A coil current is signed, so the limit applies to its magnitude."""
        if self.current is None or self.current_limit is None:
            return False
        return abs(self.current) > self.current_limit


class CoilCurrents(Viewer):
    coils = param.List(doc="List of CoilCurrentEntry for each coil")

    # Table column names
    COIL_NAME = "coil_name"
    FIX_CURRENT = "fix_current"
    CURRENT = "current"
    PREV_CURRENT = "previous_current"
    CURRENT_LIMIT = "current_limit"
    PENALIZE_ZERO = "penalize_to_zero"
    PENALTY_WEIGHT = "penalty_weight"

    def __init__(self, **params):
        super().__init__(**params)
        self.nice_settings = settings.nice

        titles = {
            self.COIL_NAME: "Name",
            self.FIX_CURRENT: "Fix",
            self.CURRENT: "Coil current [A]",
            self.PREV_CURRENT: "Previous current [A]",
            self.CURRENT_LIMIT: "Current limit [A]",
            self.PENALIZE_ZERO: "Penalize to 0",
            self.PENALTY_WEIGHT: "Penalty weight",
        }
        header_tooltips = {
            self.COIL_NAME: "The name of the coil",
            self.FIX_CURRENT: "Fix coil current to a specific value.",
            self.CURRENT: "Coil current",
            self.PREV_CURRENT: "Coil current input to previous run of the solver.",
            self.CURRENT_LIMIT: (
                "Largest current this coil tolerates, from the machine description. "
                "A current beyond it is allowed, but the row is highlighted."
            ),
            self.PENALIZE_ZERO: (
                "Penalize this coil's current towards 0. When unchecked, it is "
                "penalized towards the current it was loaded with."
            ),
            self.PENALTY_WEIGHT: (
                "Scales how far this coil's current may stray from what it is "
                "penalized towards. Below 1 holds it closer, above 1 lets it drift "
                "further."
            ),
        }
        editors = {
            self.COIL_NAME: None,
            self.FIX_CURRENT: None,
            self.CURRENT: {"type": "number"},
            self.PREV_CURRENT: None,
            self.CURRENT_LIMIT: None,
            self.PENALIZE_ZERO: None,
            self.PENALTY_WEIGHT: {"type": "number", "step": 0.01},
        }
        formatters = {
            self.FIX_CURRENT: {"type": "tickCross"},
            self.CURRENT: NumberFormatter(),
            self.PREV_CURRENT: NumberFormatter(),
            self.CURRENT_LIMIT: NumberFormatter(),
            self.PENALIZE_ZERO: {"type": "tickCross"},
            self.PENALTY_WEIGHT: NumberFormatter(),
        }
        self.table = pn.widgets.Tabulator(
            layout="fit_data_stretch",
            sizing_mode="stretch_width",
            show_index=False,
            titles=titles,
            editors=editors,
            formatters=formatters,
            header_tooltips=header_tooltips,
            header_align="center",
            text_align="center",
            sortable=False,
            selectable=False,
            visible=self.param.coils.rx.bool(),
            on_edit=self._on_cell_edit,
            on_click=self._on_cell_click,
        )
        self._update_column_visibility()
        self.nice_settings.param.watch(self._update_column_visibility, "is_direct_mode")

        self.panel = self.table

    def create_ui(self, pf_active):
        """Create the UI for each coil in the provided pf_active IDS.

        Args:
            pf_active: pf_active IDS containing coils with current values.
        """
        if not pf_active:
            self.coils = []
            return

        new_coils = []
        for coil in pf_active.coil:
            coil_current = coil.current
            entry = CoilCurrentEntry(
                coil_name=str(coil.name),
                current=coil_current.data[0] if coil_current.data.has_value else None,
                current_limit=self._current_limit(coil),
            )
            new_coils.append(entry)

        self.coils = new_coils
        self._warn_exceeded()

    def _warn_exceeded(self, coils=None):
        """Warn about coils beyond their current limit"""

        if coils is None:
            coils = self.coils
        exceeded = [coil for coil in coils if coil.exceeds_limit]
        if not exceeded:
            return
        if len(exceeded) == 1:
            coil = exceeded[0]
            message = (
                f"{coil.coil_name} is at {coil.current:.0f} A, beyond its limit of "
                f"{coil.current_limit:.0f} A."
            )
        else:
            names = ", ".join(coil.coil_name for coil in exceeded)
            message = f"{len(exceeded)} coils are beyond their limit: {names}."
        pn.state.notifications.warning(message)

    def _current_limit(self, coil):
        """The largest current ``coil`` tolerates, or None if it isn't in the machine
        description."""
        limits = np.abs(np.asarray(coil.current_limit_max))
        if limits.size == 0:
            return None
        return float(limits.max())

    def _update_column_visibility(self, *events):
        """Show or hide the inverse-mode-only columns based on whether NICE is in
        direct mode."""
        inverse_only = [self.FIX_CURRENT, self.PENALIZE_ZERO, self.PENALTY_WEIGHT]
        self.table.hidden_columns = (
            inverse_only if self.nice_settings.is_direct_mode else []
        )

    @param.depends("coils", watch=True)
    def _update_table(self):
        data = [
            {
                self.COIL_NAME: coil.coil_name,
                self.FIX_CURRENT: coil.fix_current,
                self.CURRENT: coil.current,
                self.PREV_CURRENT: coil.previous_current,
                self.CURRENT_LIMIT: coil.current_limit,
                self.PENALIZE_ZERO: coil.penalize_to_zero,
                self.PENALTY_WEIGHT: coil.penalty_weight,
            }
            for coil in self.coils
        ]
        self.table.value = pd.DataFrame(data)
        self._highlight_exceeded()

    def _highlight_exceeded(self):
        """Colour the row of every coil whose current is beyond its limit."""

        exceeded = [coil.exceeds_limit for coil in self.coils]
        exceeded_style = "background-color: #f8d7da"
        self.table.style.clear()
        self.table.style.apply(
            lambda row: [exceeded_style if exceeded[row.name] else ""] * len(row),
            axis=1,
        )

    def _on_cell_edit(self, event):
        coil = self.coils[event.row]
        if event.column == self.FIX_CURRENT:
            coil.fix_current = bool(event.value)
        elif event.column == self.CURRENT:
            coil.current = float(event.value)
            self._highlight_exceeded()
            self._warn_exceeded([coil])
        elif event.column == self.PENALTY_WEIGHT:
            if float(event.value) <= 0:
                pn.state.notifications.error(
                    "The penalty weight must be positive. Fix the coil instead to "
                    "hold its current exactly."
                )
                self._update_table()
                return
            coil.penalty_weight = float(event.value)
        else:
            raise RuntimeError(f"Cannot edit column {event.column}")

    def _on_cell_click(self, event):
        coil = self.coils[event.row]
        if event.column == self.FIX_CURRENT:
            coil.fix_current = not coil.fix_current
            self._update_table()
        elif event.column == self.PENALIZE_ZERO:
            coil.penalize_to_zero = not coil.penalize_to_zero
            self._update_table()

    def fill_pf_active(self, pf_active):
        """Update the coil currents of the provided pf_active IDS. Also stores current
        values as previous_current before the NICE run.

        Args:
            pf_active: pf_active IDS to update the coil currents for.
        """
        for i, coil in enumerate(self.coils):
            coil.previous_current = pf_active.coil[i].current.data[0]
            if coil.current is not None:
                pf_active.coil[i].current.data = np.array([coil.current])

    def sync_ui_with_pf_active(self, pf_active):
        """Synchronize UI with the current values from the pf_active IDS.

        Args:
            pf_active: pf_active IDS for which the coil currents are used.
        """
        for i, coil in enumerate(pf_active.coil):
            self.coils[i].current = coil.current.data[0]
        self._update_table()

    def update_xml(self, xml_params: ET.Element):
        """Update XML parameters based on coil current table configuration.

        Args:
            xml_params: XML representing configuration parameters, which are updated
                in-place.
        """
        self._update_fixed_coils_in_xml(xml_params)
        self._update_penalization_in_xml(xml_params)

    def _update_fixed_coils_in_xml(self, xml_params: ET.Element):
        """Update XML parameters indicating which coils are fixed based on
        UI checkboxes.

        Args:
            xml_params: XML representing configuration parameters, which are updated
                in-place.
        """
        coil_groups = xml_params.find("coil_group_index").text.split()
        fixed_coils = [i for i, coil in enumerate(self.coils) if coil.fix_current]
        target_groups = {coil_groups[coil_idx] for coil_idx in fixed_coils}
        fixed_groups = sorted(list(target_groups), key=int)

        xml_params.find("n_group_fixed_index").text = str(len(fixed_groups))
        # NICE requires group_fixed_index to be filled even when there are no fixed
        # coils
        xml_params.find("group_fixed_index").text = " ".join(fixed_groups) or "-1"

    def _update_penalization_in_xml(self, xml_params: ET.Element):
        """Update the XML parameters describing how NICE penalizes the coil currents
        based on the UI.

        Args:
            xml_params: XML representing configuration parameters
        """
        coil_groups = xml_params.find("coil_group_index").text.split()
        zero_groups = set()
        weights = {}
        for group, coil in zip(coil_groups, self.coils, strict=True):
            penalization = (coil.penalize_to_zero, coil.penalty_weight)
            if weights.setdefault(group, penalization) != penalization:
                group_names = ", ".join(
                    coil.coil_name
                    for coil_group, coil in zip(coil_groups, self.coils, strict=True)
                    if coil_group == group
                )
                raise ValueError(
                    f"Coils {group_names} share a NICE coil group, "
                    "so they must be penalized the same way."
                )
            if coil.penalize_to_zero:
                zero_groups.add(group)

        zero_groups = sorted(zero_groups, key=int)
        xml_params.find("n_group_penalized_to_zero_index").text = str(len(zero_groups))
        # NICE requires group_penalized_to_zero_index to be filled even when no coil
        # is penalized to zero
        xml_params.find("group_penalized_to_zero_index").text = (
            " ".join(zero_groups) or "-1"
        )

        groups = sorted(weights, key=int)
        xml_params.find("n_group_special_weight").text = str(len(groups))
        xml_params.find("group_special_weight_index").text = " ".join(groups)
        xml_params.find("group_special_weight").text = " ".join(
            str(weights[group][1]) for group in groups
        )

    def __panel__(self):
        return self.panel
