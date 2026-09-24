import imas
from imas.ids_path import IDSPath
from ruamel.yaml.comments import CommentedMap

from waveform_editor.derived_waveform import DerivedWaveform
from waveform_editor.tendencies.points.piecewise import PiecewiseLinearTendency


class WaveformStore:
    """Stores the quantities of a NICE run in the waveforms named after their IDS
    paths."""

    QUANTITIES = {
        "Plasma Boundary": [
            "equilibrium/time_slice(1)/boundary/elongation",
            "equilibrium/time_slice(1)/boundary/triangularity",
            "equilibrium/time_slice(1)/boundary/triangularity_upper",
            "equilibrium/time_slice(1)/boundary/triangularity_lower",
            "equilibrium/time_slice(1)/boundary/minor_radius",
            "equilibrium/time_slice(1)/boundary/geometric_axis/r",
            "equilibrium/time_slice(1)/boundary/geometric_axis/z",
            "equilibrium/time_slice(1)/boundary/psi",
        ],
        "Plasma Global Quantities": [
            "equilibrium/time_slice(1)/global_quantities/ip",
            "equilibrium/time_slice(1)/global_quantities/q_95",
            "equilibrium/time_slice(1)/global_quantities/q_axis",
            "equilibrium/time_slice(1)/global_quantities/q_min/value",
            "equilibrium/time_slice(1)/global_quantities/q_min/rho_tor_norm",
            "equilibrium/time_slice(1)/global_quantities/beta_pol",
            "equilibrium/time_slice(1)/global_quantities/beta_tor",
            "equilibrium/time_slice(1)/global_quantities/beta_tor_norm",
            "equilibrium/time_slice(1)/global_quantities/li_3",
            "equilibrium/time_slice(1)/global_quantities/volume",
            "equilibrium/time_slice(1)/global_quantities/area",
            "equilibrium/time_slice(1)/global_quantities/surface",
            "equilibrium/time_slice(1)/global_quantities/length_pol",
            "equilibrium/time_slice(1)/global_quantities/psi_axis",
            "equilibrium/time_slice(1)/global_quantities/psi_boundary",
            "equilibrium/time_slice(1)/global_quantities/energy_mhd",
            "equilibrium/time_slice(1)/global_quantities/magnetic_axis/r",
            "equilibrium/time_slice(1)/global_quantities/magnetic_axis/z",
            "equilibrium/time_slice(1)/global_quantities/magnetic_axis/b_field_phi",
            "equilibrium/vacuum_toroidal_field/b0(1)",
        ],
        # NICE fills a node for the o-point and one for the x-point
        "Plasma Critical Points": [
            "equilibrium/time_slice(1)/contour_tree/node(:)/r",
            "equilibrium/time_slice(1)/contour_tree/node(:)/z",
            "equilibrium/time_slice(1)/contour_tree/node(:)/psi",
        ],
        "Coil Currents": [
            "pf_active/coil(:)/current/data(1)",
            "pf_active/coil(:)/b_field_max_timed/data(1)",
            "pf_active/coil(:)/force_radial/data(1)",
            "pf_active/coil(:)/force_vertical/data(1)",
        ],
    }

    def __init__(self, config):
        self.config = config

    def get_quantities(self, equilibrium, pf_active):
        """The quantities of a NICE run that can be stored in waveforms.

        Args:
            equilibrium: The equilibrium IDS NICE returned, or None.
            pf_active: The pf_active IDS NICE returned, or None.

        Returns:
            List of (group, waveform name, value, units), empty when NICE has not run
            yet.
        """
        idss = {"equilibrium": equilibrium, "pf_active": pf_active}
        factory = imas.IDSFactory(self.config.globals.dd_version)
        dd_idss = {name: factory.new(name) for name in idss}
        rows = []
        for group, paths in self.QUANTITIES.items():
            for path in paths:
                ids_name, _, path_in_ids = path.partition("/")
                ids = idss[ids_name]
                if ids is None:  # NICE did not return this IDS
                    continue
                dd_ids = dd_idss[ids_name]
                # An (:) index stands for every element of that array
                prefix, wildcard, rest = path_in_ids.partition("(:)")
                elements = [path_in_ids]
                if wildcard:
                    elements = [
                        f"{prefix}({i + 1}){rest}" for i in range(len(ids[prefix]))
                    ]
                for element in elements:
                    name, units = self._describe(dd_ids, element)
                    if name is None:
                        # The data dictionary version in use has no such quantity
                        continue
                    try:
                        value = float(ids[element])
                    except IndexError:
                        # NICE did not fill this quantity, for instance because it
                        # does not apply to the mode that was run
                        continue
                    rows.append((group, f"{ids_name}/{name}", value, units))
        return rows

    def _describe(self, dd_ids, path):
        """The name of the waveform a quantity is stored in, and its units.

        Args:
            dd_ids: An IDS of the data dictionary version of the configuration.
            path: Path of the quantity inside that IDS.

        Returns:
            Tuple of (name, units)
        """
        without_index, parts = [], []
        for part, index in IDSPath(path).items():
            without_index.append(part)
            try:
                metadata = dd_ids.metadata["/".join(without_index)]
            except KeyError:
                return None, None
            keep = index is not None and not metadata.type.is_dynamic
            parts.append(f"{part}({index + 1})" if keep else part)
        return "/".join(parts), metadata.units

    def store(self, quantities, time):
        """Store each quantity in a waveform, creating the ones that do not exist yet.

        Args:
            quantities: The quantities to store.
            time: The time to store the values at.


        Returns:
            The names of the waveforms created.
        """
        created = []
        for group, name, value, _ in quantities:
            if name in self.config.waveform_map:
                self._store_in_waveform(name, value, time)
            else:
                self._create_waveform(group, name, value, time)
                created.append(name)
        return created

    def _create_waveform(self, group, name, value, time):
        """Create a waveform holding a single point, in its group.

        Args:
            group: Name of the group to create the waveform in, added if it is new.
            name: Name of the waveform.
            value: Value to store.
            time: The time to store the value at.
        """
        if group not in self.config.groups:
            self.config.add_group(group, [])
        yaml_str = f"{name}:\n- {{type: piecewise, time: [{time}], value: [{value}]}}"
        self.config.add_waveform(self.config.parser.parse_waveform(yaml_str), [group])

    def _store_in_waveform(self, name, value, time):
        """Store the value at the end of an existing waveform, either by extending its
        last piecewise tendency, or by adding a new one.

        TODO: only storing after the last point keeps this simple. Storing at an
        arbitrary time needs a waveform splitter, which can place a point inside any
        tendency by splitting it.

        Args:
            name: Name of the waveform.
            value: Value to store.
            time: The time to store the value at.
        """
        waveform = self.config[name]
        if isinstance(waveform, DerivedWaveform):
            raise ValueError(
                f"Could not store a value in waveform {name!r}, because it is a "
                "derived waveform"
            )

        last = waveform.tendencies[-1]
        if time <= last.end:
            raise ValueError(
                f"Could not store a value in waveform {name!r} at t={time}, because it "
                f"already runs until t={last.end}. Store at a later time."
            )

        if isinstance(last, PiecewiseLinearTendency):
            waveform.yaml[-1]["time"].append(float(time))
            waveform.yaml[-1]["value"].append(float(value))
        else:
            entry = CommentedMap(
                type="piecewise",
                time=[float(last.end), float(time)],
                value=[float(value), float(value)],
            )
            # The flow style the other tendencies are written in
            entry.fa.set_flow_style()
            waveform.yaml.append(entry)

        self.config.replace_waveform(
            self.config.parse_waveform(f"{name}:\n{waveform.get_yaml_string()}")
        )
