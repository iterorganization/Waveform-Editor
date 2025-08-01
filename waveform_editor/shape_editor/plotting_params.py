import param


class PlottingParams(param.Parameterized):
    """Parameters related to plotting"""

    show_contour = param.Boolean(default=True, label="Show contour lines")
    levels = param.Integer(
        default=20, bounds=(1, 200), label="Number of contour levels"
    )
    show_coils = param.Boolean(default=True, label="Show coils")
    show_wall = param.Boolean(default=True, label="Show limiter and divertor")
    show_vacuum_vessel = param.Boolean(
        default=True, label="Show inner and outer vacuum vessel"
    )
    show_xo = param.Boolean(default=True, label="Show x-point and o-point")
    show_separatrix = param.Boolean(default=True, label="Show separatrix")
