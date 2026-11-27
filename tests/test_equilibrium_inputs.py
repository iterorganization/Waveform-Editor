import imas

from waveform_editor.gui.shape_editor.plasma_properties import PlasmaProperties
from waveform_editor.gui.shape_editor.reference_shape import ReferenceShape
from waveform_editor.gui.shape_editor.shape_params import PlasmaShapeParams

# The equilibrium data that the plasma properties read
PLASMA_PROPERTIES_PATHS = [
    *(path for _, path in PlasmaProperties._IDS_SCALAR_PATHS),
    "time_slice(0)/profiles_1d/psi",
    "time_slice(0)/profiles_1d/dpressure_dpsi",
    "time_slice(0)/profiles_1d/f_df_dpsi",
]


def test_dd3_equilibrium():
    eq = imas.IDSFactory("3.39.0").equilibrium()
    eq.vacuum_toroidal_field.b0 = [5.3]
    eq.time_slice.resize(1)
    x_points = eq.time_slice[0].boundary_separatrix.x_point
    x_points.resize(2)
    x_points[0].r, x_points[0].z = 6.0, -3.0
    x_points[1].r, x_points[1].z = 0.0, 0.0

    for path in PLASMA_PROPERTIES_PATHS:
        eq[path]
    reference = ReferenceShape(on_set=lambda: None, shape_params=PlasmaShapeParams())
    assert reference._equilibrium_shape(eq)[2] == [(6.0, -3.0)]


def test_dd4_equilibrium():
    eq = imas.IDSFactory("4.1.1").equilibrium()
    eq.vacuum_toroidal_field.b0 = [5.3]
    eq.time_slice.resize(1)
    nodes = eq.time_slice[0].contour_tree.node
    nodes.resize(3)  # the axis, the primary x-point, and another x-point
    nodes[1].critical_type = nodes[2].critical_type = 1
    nodes[1].r, nodes[1].z = 6.0, -3.0
    nodes[2].r, nodes[2].z = 5.0, 4.5

    for path in PLASMA_PROPERTIES_PATHS:
        eq[path]
    reference = ReferenceShape(on_set=lambda: None, shape_params=PlasmaShapeParams())
    assert reference._equilibrium_shape(eq)[2] == [(6.0, -3.0)]
