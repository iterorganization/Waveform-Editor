import param


class ShapeParams(param.Parameterized):
    """Parameters related to plasma shape"""

    equilibrium_input = param.String(label="Input 'equilibrium' IDS")
    time_input = param.Number(label="Time for input equilibrium")
