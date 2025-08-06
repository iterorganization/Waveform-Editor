import xml.etree.ElementTree as ET
from pathlib import Path

import imas
import numpy as np
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.settings import NiceSettings, settings
from waveform_editor.shape_editor.nice_integration import NiceIntegration
from waveform_editor.shape_editor.nice_plotter import NicePlotter
from waveform_editor.shape_editor.plasma_properties import PlasmaProperties
from waveform_editor.shape_editor.shape_params import ShapeParams


class ShapeEditor(Viewer):
    nice_settings = param.ClassSelector(class_=NiceSettings)
    shape_params = param.ClassSelector(class_=ShapeParams)

    def __init__(self):
        super().__init__()
        factory = imas.IDSFactory()
        self.communicator = NiceIntegration(factory)
        self.shape_params = ShapeParams()
        self.plasma_properties = PlasmaProperties()
        self.equilibrium = self.create_empty_equilibrium()
        self.nice_plotter = NicePlotter(
            self.communicator, self.shape_params, self.equilibrium
        )
        self.nice_settings = settings.nice

        # UI Configuration
        button_start = pn.widgets.Button(name="Run", on_click=self.submit)
        button_stop = pn.widgets.Button(name="Stop", on_click=self.stop_nice)
        buttons = pn.Row(button_start, button_stop)
        options = pn.Accordion(
            ("NICE Configuration", pn.Param(settings.nice, show_name=False)),
            ("Plotting Parameters", pn.Param(self.nice_plotter, show_name=False)),
            ("Plasma Shape", self.shape_params),
            ("Plasma Parameters", self.plasma_properties),
            ("Coil Currents", None),
            sizing_mode="stretch_width",
        )
        menu = pn.Column(
            buttons, self.communicator.terminal, sizing_mode="stretch_width"
        )
        self.panel = pn.Row(
            self.nice_plotter,
            pn.Column(
                menu,
                options,
                sizing_mode="stretch_both",
            ),
        )

    def _load_slice(self, uri, ids_name, time=0):
        """Load an IDS slice and return it.

        Args:
            uri: the URI to load the slice of.
            ids_name: The name of the IDS to load.
            time: the time step to load slice of.
        """
        if uri:
            try:
                with imas.DBEntry(uri, "r") as entry:
                    return entry.get_slice(ids_name, time, imas.ids_defs.CLOSEST_INTERP)
            except Exception as e:
                pn.state.notifications.error(str(e))

    @param.depends("nice_settings.md_pf_active", watch=True)
    def _load_pf_active(self):
        self.pf_active = self._load_slice(self.nice_settings.md_pf_active, "pf_active")
        self.nice_plotter.pf_active = self.pf_active
        if not self.pf_active:
            self.nice_settings.md_pf_active = ""

    @param.depends("nice_settings.md_pf_passive", watch=True)
    def _load_pf_passive(self):
        self.pf_passive = self._load_slice(
            self.nice_settings.md_pf_passive, "pf_passive"
        )
        if not self.pf_passive:
            self.nice_settings.md_pf_passive = ""

    @param.depends("nice_settings.md_wall", watch=True)
    def _load_wall(self):
        self.wall = self._load_slice(self.nice_settings.md_wall, "wall")
        self.nice_plotter.wall = self.wall
        if not self.wall:
            self.nice_settings.md_wall = ""

    @param.depends("nice_settings.md_iron_core", watch=True)
    def _load_iron_core(self):
        self.iron_core = self._load_slice(self.nice_settings.md_iron_core, "iron_core")
        if not self.iron_core:
            self.nice_settings.md_iron_core = ""

    @param.depends(
        "shape_params.equilibrium_input", "shape_params.time_input", watch=True
    )
    def _load_shape(self):
        equilibrium = self._load_slice(
            self.shape_params.equilibrium_input,
            "equilibrium",
            self.shape_params.time_input,
        )

        outline = equilibrium.time_slice[0].boundary.outline
        self.equilibrium.time_slice[0].boundary.outline.r = outline.r
        self.equilibrium.time_slice[0].boundary.outline.z = outline.z

    @param.depends("nice_settings.xml_params", watch=True)
    def _load_xml_params(self):
        if self.nice_settings.xml_params:
            try:
                self.xml_params = Path(self.nice_settings.xml_params).read_text()
            except Exception:
                self.xml_params = None
                self.nice_settings.xml_params = ""

    def _update_xml_params(self, xml_string, params):
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

    async def submit(self, event=None):
        """Submit a new equilibrium reconstruction job to NICE, passing the machine
        description IDSs and an input equilibrium IDS."""

        if not self.xml_params:
            pn.state.notifications.error("Please provide a path to NICE XML params")
            return

        input_ids_names = ["pf_active", "pf_passive", "wall", "iron_core"]
        for name in input_ids_names:
            ids = getattr(self, name)
            if not ids:
                pn.state.notifications.error(f"Please provide a valid {name} IDS")
                return

        # TODO:NICE requires an input equilibrium IDS with the following parameters
        # filled:
        # - time_slice[0].global_quantities.ip
        # - vacuum_toroidal_field.r0
        # - vacuum_toroidal_field.b0
        # - time_slice[0].profiles_1d.dpressure_dpsi
        # - time_slice[0].profiles_1d.f_df_dpsi
        # - time_slice[0].profiles_1d.psi
        if self.shape_params.input_mode == self.shape_params.PARAMETERIZED_INPUT:
            self.equilibrium = self.create_empty_equilibrium()
        elif (
            self.shape_params.input_mode == self.shape_params.EQUILIBRIUM_INPUT
            and not self.equilibrium
        ):
            pn.state.notifications.error("Please provide a valid equilibrium IDS")
            return

        updated_xml = self._update_xml_params(self.xml_params, self.shape_params)
        if not self.communicator.running:
            await self.communicator.run()
        await self.communicator.submit(
            updated_xml,
            self.equilibrium.serialize(),
            self.pf_active.serialize(),
            self.pf_passive.serialize(),
            self.wall.serialize(),
            self.iron_core.serialize(),
        )

    def create_empty_equilibrium(self):
        equilibrium = imas.IDSFactory().new("equilibrium")
        equilibrium.time = [0]
        equilibrium.time_slice.resize(1)
        equilibrium.ids_properties.homogeneous_time = (
            imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        )
        equilibrium.time_slice[0].global_quantities.ip = -1.5e7
        equilibrium.vacuum_toroidal_field.r0 = 6.2
        equilibrium.vacuum_toroidal_field.b0.resize(1)
        equilibrium.vacuum_toroidal_field.b0[0] = -5.3
        # TODO: NICE does not read from p'/ff' from parametrisation (alpha, beta, gamma)
        # yet, so these are taken from the equilibrium IDS for now
        equilibrium.time_slice[0].profiles_1d.dpressure_dpsi = np.array(
            [
                -390.34138988,
                -2912.67072464,
                -6165.21622226,
                -6908.1180053,
                -7422.15736387,
                -7745.09724664,
                -7975.14145374,
                -8137.83898627,
                -8247.58658396,
                -8308.01864827,
                -8321.61973232,
                -8295.27269954,
                -8237.77432626,
                -8150.78348088,
                -8037.2198474,
                -7899.0043066,
                -7737.2657881,
                -7553.88451492,
                -7354.15116111,
                -7141.79517789,
                -6921.46702604,
                -6703.97929578,
                -6509.90501645,
                -6372.60005051,
                -6312.59187912,
                -6297.65684416,
                -6285.36618649,
                -6255.64991897,
                -6214.19656503,
                -6176.63307724,
                -6144.88291435,
                -6115.41487426,
                -6086.02871425,
                -6057.78418939,
                -6032.56122792,
                -6025.48551586,
                -6033.24104422,
                -6047.6832907,
                -6070.09160039,
                -6106.41587008,
                -7942.33174394,
                -10064.23355528,
                -12187.39735735,
                -14311.88957072,
                -16437.78011178,
                -13493.25130769,
                -10123.94791099,
                -6752.0633207,
                -3377.4616845,
                -0.0,
            ]
        )
        equilibrium.time_slice[0].profiles_1d.f_df_dpsi = np.array(
            [
                -1.99255004,
                -1.8584636,
                -1.68214296,
                -1.63733705,
                -1.60888662,
                -1.59202963,
                -1.57903411,
                -1.5678743,
                -1.56089994,
                -1.56026971,
                -1.56279336,
                -1.56593499,
                -1.56905217,
                -1.57439985,
                -1.58129249,
                -1.59077246,
                -1.60261902,
                -1.61445146,
                -1.62349026,
                -1.62589783,
                -1.6060002,
                -1.53342162,
                -1.36776053,
                -1.09556959,
                -0.84058881,
                -0.67455513,
                -0.5837479,
                -0.51128605,
                -0.44276129,
                -0.38129521,
                -0.32745261,
                -0.28081709,
                -0.24058079,
                -0.20603021,
                -0.17649139,
                -0.150883,
                -0.1288626,
                -0.11024486,
                -0.09464058,
                -0.08178965,
                -0.03433791,
                0.01868792,
                0.07174528,
                0.12483583,
                0.17796134,
                0.14796525,
                0.1110179,
                0.07404225,
                0.03703681,
                0.0,
            ]
        )

        equilibrium.time_slice[0].profiles_1d.psi = np.array(
            [
                -96.41120419,
                -96.35249564,
                -96.17636999,
                -95.88282724,
                -95.47186739,
                -94.94349044,
                -94.29769639,
                -93.53448524,
                -92.65385699,
                -91.65581164,
                -90.54034918,
                -89.30746963,
                -87.95717298,
                -86.48945923,
                -84.90432837,
                -83.20178042,
                -81.38181537,
                -79.44443321,
                -77.38963396,
                -75.21741761,
                -72.92778415,
                -70.5207336,
                -67.99626594,
                -65.35438119,
                -62.59507933,
                -59.86498498,
                -57.17324163,
                -54.5275017,
                -51.93410195,
                -49.39822018,
                -46.92401531,
                -44.51475242,
                -42.17291433,
                -39.90030102,
                -37.69811831,
                -35.56705667,
                -33.50736138,
                -31.51889484,
                -29.60119181,
                -27.75350845,
                -25.97486567,
                -24.26408743,
                -22.6198346,
                -21.04063473,
                -19.52490823,
                -18.07099138,
                -16.67715643,
                -15.34162914,
                -14.06260408,
                -12.83825786,
            ]
        )
        return equilibrium

    async def stop_nice(self, event):
        await self.communicator.close()

    def __panel__(self):
        return self.panel
