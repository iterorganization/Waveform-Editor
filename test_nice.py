"""Tests for the NICE integration.

N.B. these will not run in pytest.
"""

from pathlib import Path

import holoviews as hv
import imas
import matplotlib
import matplotlib.pyplot
import numpy as np
import panel as pn
import param
from scipy.spatial import Delaunay

from waveform_editor.settings import settings
from waveform_editor.shape_editor.nice_integration import NiceIntegration

# Testing

# hv.extension("matplotlib")
# matplotlib.use("agg")

xml_params = Path(
    "/home/sebbe/projects/iter_python/nice/run/iwrap/param/inv/iter/param.xml"
).read_text()

print("loading data:")
with imas.DBEntry(
    "imas:hdf5?path=/home/sebbe/projects/iter_python/Waveform-Editor/data/nice-input-dd4",
    "r",
) as entry:
    time = 249.5
    print("equilibrium")
    eq = entry.get_slice("equilibrium", time, imas.ids_defs.CLOSEST_INTERP)
    print("pf_active")
    pfa = entry.get_slice("pf_active", time, imas.ids_defs.CLOSEST_INTERP)
    print("pf_passive")
    pfp = entry.get_slice("pf_passive", time, imas.ids_defs.CLOSEST_INTERP)
    print("wall")
    wall = entry.get_slice("wall", time, imas.ids_defs.CLOSEST_INTERP)
    print("iron_core")
    iron_core = entry.get_slice("iron_core", time, imas.ids_defs.CLOSEST_INTERP)

communicator = NiceIntegration(imas.IDSFactory())


async def submit(event=None):
    if not communicator.running:
        await communicator.run()
    print("Submit to comm")
    await communicator.submit(
        xml_params,
        eq.serialize(),
        pfa.serialize(),
        pfp.serialize(),
        wall.serialize(),
        iron_core.serialize(),
    )


def extract_contour_segments(tricontour):
    segments = []
    for i, level in enumerate(tricontour.levels):
        for seg in tricontour.allsegs[i]:
            if len(seg) > 1:
                segments.append({"x": seg[:, 0], "y": seg[:, 1], "psi": level})
    return segments


def create_coil_rectangles(pf_active):
    rectangles = []
    paths = []
    for coil in pf_active.coil:
        for element in coil.element:
            rect = element.geometry.rectangle
            outline = element.geometry.outline
            if rect.has_value:
                r0 = rect.r - rect.width / 2
                r1 = rect.r + rect.width / 2
                z0 = rect.z - rect.height / 2
                z1 = rect.z + rect.height / 2
                rectangles.append((r0, z0, r1, z1))
            elif outline.has_value:
                path = hv.Path([list(zip(outline.r, outline.z))]).opts(
                    color="black", line_width=1, show_legend=False
                )
                paths.append(path)
            else:
                continue
    rects = hv.Rectangles(rectangles).opts(
        line_color="black", fill_alpha=0, line_width=2, show_legend=False
    )

    return rects * hv.Overlay(paths)


def create_contours(equilibrium, levels=20):
    eqggd = equilibrium.time_slice[0].ggd[0]
    r = eqggd.r[0].values
    z = eqggd.z[0].values
    psi = eqggd.psi[0].values
    time = communicator.equilibrium.time[0]  # time may not be filled for homogeneous
    time_meta = communicator.equilibrium.time.metadata
    r_meta = eqggd.r.metadata
    z_meta = eqggd.z.metadata
    psi_meta = eqggd.psi.metadata

    trics = matplotlib.pyplot.tricontour(r, z, psi, levels=levels)
    contours = hv.Contours(extract_contour_segments(trics), vdims="psi").opts(
        hv.opts.Contours(
            cmap="viridis",
            colorbar=True,
            tools=["hover"],
            title=f"equilibrium poloidal flux at time: {time:.2f} {time_meta.units}",
            width=900,
            height=900,
            xlabel=f"{r_meta.name} [{r_meta.units}]",
            ylabel=f"{z_meta.name} [{z_meta.units}]",
            colorbar_opts={"title": f"{psi_meta.name} [{psi_meta.units}]"},
            show_legend=False,
        )
    )
    return contours


def create_separatrix(equilibrium):
    r = equilibrium.time_slice[0].boundary.outline.r
    z = equilibrium.time_slice[0].boundary.outline.z

    separatrix = hv.Curve((r, z)).opts(color="red", line_width=2, show_legend=False)

    return separatrix


def create_xo_points(equilibrium):
    o_points = [
        (node.r, node.z)
        for node in equilibrium.time_slice[0].contour_tree.node
        if node.critical_type == 0 or node.critical_type == 2
    ]
    x_points = [
        (node.r, node.z)
        for node in equilibrium.time_slice[0].contour_tree.node
        if node.critical_type == 1
    ]

    o_scatter = hv.Scatter(o_points).opts(
        marker="o", size=10, color="black", show_legend=False
    )
    x_scatter = hv.Scatter(x_points).opts(
        marker="x", size=10, color="black", show_legend=False
    )

    return o_scatter * x_scatter


def plot_nice(processing, levels):
    if not processing and communicator.equilibrium:
        contours = create_contours(communicator.equilibrium, levels=levels)
        coils = create_coil_rectangles(communicator.pf_active)
        separatrix = create_separatrix(communicator.equilibrium)
        points = create_xo_points(communicator.equilibrium)
        overlay = contours * coils * separatrix * points
        overlay = overlay.opts(ylim=(-10, 10))
        return pn.pane.HoloViews(overlay, width=1000, height=1000)

        # Apply Delaunay triangulation
        delaunay = Delaunay(np.column_stack([r, z]))
        nodes = hv.Points(np.column_stack([r, z, psi]), vdims=["z"])
        trimesh = hv.TriMesh((delaunay.simplices, nodes))
        trimesh.opts(
            hv.opts.TriMesh(
                cmap="viridis",
                # node_color="PSI",
                edge_color="z",
                filled=True,
                height=400,
                # inspection_policy="edges",
                tools=["hover"],
                width=400,
            )
        )
        print(trimesh, r.shape, z.shape, psi.shape, nodes.shape)
        return pn.pane.HoloViews(trimesh, sizing_mode="stretch_both")
    else:
        r = np.array([0, 0, 1, 1, 2, 2])
        z = np.array([0, 1, 0, 1, 0, 1])
        psi = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])

        delaunay = Delaunay(np.column_stack([r, z]))
        trics = matplotlib.pyplot.tricontour(r, z, psi, levels=levels)
        contours = hv.Contours([p.vertices for p in trics.get_paths()])
        return pn.pane.HoloViews(contours, sizing_mode="stretch_both")
        nodes = hv.Points(np.column_stack([r, z, psi]), vdims=["z"])
        trimesh = hv.TriMesh((delaunay.simplices, nodes))
        trimesh.opts(
            hv.opts.TriMesh(
                cmap="viridis",
                edge_color="z",
                filled=True,
                # height=400,
                # tools=["hover"],
                # width=400,
            )
        )
        # contours = hv.operation.contours(trimesh)
        print(trimesh, r.shape, z.shape, psi.shape, nodes.shape)
        return pn.pane.HoloViews(trimesh, sizing_mode="stretch_both")

    return pn.indicators.LoadingSpinner(value=True, size=40, name="Loading...")


# class PlotParams(param.Parameterized):
#     levels = param.Integer(default=50, bounds=(1, 200))
#
#
# plot_params = PlotParams()
# pn.Column(
#     pn.Param(communicator.param),
#     pn.Param(plot_params),
#     pn.widgets.Button(name="Click", on_click=submit),
#     pn.Tabs(
#         ("NICE output", communicator.terminal),
#         (
#             "NICE plot",
#             pn.bind(plot_nice, communicator.param.processing, plot_params.param.levels),
#         ),
#     ),
# ).servable()


async def start_nice(event):
    await communicator.run()


async def stop_nice(event):
    await communicator.close()


class PlotParams(param.Parameterized):
    levels = param.Integer(default=50, bounds=(1, 200))


plot_params = PlotParams()
pn.Column(
    pn.Param(communicator.param),
    pn.Param(plot_params),
    pn.widgets.Button(name="Click", on_click=submit),
    pn.widgets.Button(name="Start NICE", on_click=start_nice),
    pn.widgets.Button(name="Stop NICE", on_click=stop_nice),
    pn.Tabs(
        ("NICE output", communicator.terminal),
        (
            "NICE plot",
            pn.bind(plot_nice, communicator.param.processing, plot_params.param.levels),
        ),
        ("NICE settings", settings.panel),
    ),
).servable()
