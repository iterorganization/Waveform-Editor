import param


class DisplaySettings(param.Parameterized):
    """Display setting that determine what is visualized in the plotting window."""

    show_contour = param.Boolean(default=True, label="Show contour lines")
    levels = param.Integer(
        default=20, bounds=(1, 200), label="Number of contour levels"
    )
    show_heatmap = param.Boolean(default=False, label="Show heatmap")
    heatmap_alpha = param.Number(
        default=0.7, bounds=(0.0, 1.0), step=0.05, label="Heatmap opacity"
    )
    show_coils = param.Boolean(default=True, label="Show coils")
    show_wall = param.Boolean(default=True, label="Show limiter and divertor")
    show_vacuum_vessel = param.Boolean(
        default=True, label="Show inner and outer vacuum vessel"
    )
    show_passive_structures = param.Boolean(
        default=True, label="Show passive structures"
    )
    show_iron_core = param.Boolean(default=True, label="Show iron core")
    show_plasma_facing_components = param.Boolean(
        default=True, label="Show plasma facing components"
    )
    show_xo = param.Boolean(default=True, label="Show x-point and o-point")
    show_strike_points = param.Boolean(default=True, label="Show strike points")
    show_separatrix = param.Boolean(default=True, label="Show separatrix")
    show_target_shape = param.Boolean(default=True, label="Show target shape")
    show_target_gaps = param.Boolean(default=True, label="Show target shape gaps")
    show_result_gaps = param.Boolean(default=False, label="Show resulting shape gaps")
    show_reference_shape = param.Boolean(default=True, label="Show reference shape")
