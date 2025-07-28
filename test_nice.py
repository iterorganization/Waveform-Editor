"""Tests for the NICE integration.

N.B. these will not run in pytest.
"""

import asyncio
import xml.etree.ElementTree as ET
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

xml_params = Path(
    "/home/sebbe/projects/iter_actors/nice/run/iwrap/param/inv/iter/param.xml"
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


def update_xml_params(xml_string, params):
    root = ET.fromstring(xml_string)
    for key in params.param:
        elem = root.find(key)
        if elem is not None:
            val = getattr(params, key)
            if isinstance(val, bool):
                val = int(val)
            print(f"Changed {key} from {elem.text} to {str(val)}")
            elem.text = str(val)
    return ET.tostring(root, encoding="unicode")


async def submit(plot_params, event=None):
    updated_xml = update_xml_params(xml_params, plot_params)
    if not communicator.running:
        await communicator.run()
    print("Submit to comm")
    await communicator.submit(
        updated_xml,
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


def create_wall(wall):
    centreline = wall.description_2d[0].vessel.unit[0].annular.centreline
    r = centreline.r
    z = centreline.z
    path = hv.Path([(r, z)]).opts(color="black", line_width=2)
    return path


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
    if processing:
        return pn.indicators.LoadingSpinner(value=True, size=40, name="Loading...")
    elif not processing and communicator.equilibrium:
        contours = create_contours(communicator.equilibrium, levels=levels)
        coils = create_coil_rectangles(communicator.pf_active)
        wall_plot = create_wall(wall)
        separatrix = create_separatrix(communicator.equilibrium)
        points = create_xo_points(communicator.equilibrium)
        overlay = contours * coils * separatrix * points * wall_plot
        overlay = overlay.opts(ylim=(-10, 10))
        return pn.pane.HoloViews(overlay, width=1000, height=1000)
    else:
        return None


async def start_nice(event):
    await communicator.run()


async def stop_nice(event):
    await communicator.close()


class PlotParams(param.Parameterized):
    levels = param.Integer(default=50, bounds=(1, 200))

    # global parameters
    algoMode = param.Selector(default="31", objects=["31", "41"])
    iterMaxInv = param.Integer(default=40, bounds=(1, 50))
    epsStopInv = param.Number(default=1.0e-10, bounds=(1e-20, 1e-5))

    # Shape parameters
    parametric_bnd = param.Boolean(default=True)
    a = param.Number(default=1.9, bounds=(0, 5))
    center_r = param.Number(default=6.2, bounds=(5, 7.5))
    center_z = param.Number(default=0.545, bounds=(0, 2))
    kappa = param.Number(default=1.8, bounds=(0, 5))
    delta = param.Number(default=0.43, bounds=(0, 5))
    rx = param.Number(default=5.089, bounds=(0, 10))
    zx = param.Number(default=-3.346, bounds=(-10, 0))
    n_desired_bnd_points = param.Integer(default=96, bounds=(1, 200))

    # p' and ff'
    useInputAB = param.Boolean(default=True)
    Aabg = param.String(default="2, 0.6, 1.4")
    Babg = param.String(default="2, 0.4, 1.4")

    def reset(self):
        for p in self.param:
            if p != "name":
                setattr(self, p, self.param[p].default)


plot_params = PlotParams()
reset_button = pn.widgets.ButtonIcon(icon="restore", size="25px")
reset_button.on_click(lambda event: plot_params.reset())
pn.Column(
    pn.Param(communicator.param),
    pn.widgets.Button(
        name="Run",
        on_click=lambda event: asyncio.create_task(submit(plot_params, event)),
    ),
    pn.widgets.Button(name="Start NICE", on_click=start_nice),
    pn.widgets.Button(name="Stop NICE", on_click=stop_nice),
    pn.Tabs(
        ("NICE output", communicator.terminal),
        (
            "NICE plot",
            pn.Row(
                pn.Column(
                    reset_button,
                    pn.Param(plot_params),
                ),
                pn.bind(
                    plot_nice, communicator.param.processing, plot_params.param.levels
                ),
            ),
        ),
        ("NICE settings", settings.panel),
    ),
).servable()
