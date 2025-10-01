from io import StringIO

import holoviews as hv
import numpy as np
import panel as pn
import param
from holoviews import opts, streams
from panel.viewable import Viewer
from ruamel.yaml import YAML

from waveform_editor.derived_waveform import DerivedWaveform
from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency
from waveform_editor.util import State
from waveform_editor.waveform import Waveform


class PlotterEdit(Viewer):
    """Class to plot a single waveform in edit mode."""

    plotted_waveform: Waveform = param.ClassSelector(
        class_=(Waveform, DerivedWaveform), allow_refs=True
    )

    def __init__(self, editor, **params):
        super().__init__(**params)
        self.editor = editor

        self.plotted_waveform = self.editor.param.waveform

        self._update_plot_from_drag = State()
        self.pipe = streams.Pipe()

        self.pane = pn.pane.HoloViews(sizing_mode="stretch_both")
        # TODO: The y axis should show the units of the plotted waveform
        self.xlabel = "Time (s)"
        self.ylabel = "Value"
        self.update_plot()

    @param.depends("plotted_waveform", watch=True)
    def update_plot(self):
        """Update the plot"""
        if self._update_plot_from_drag:
            return  # Skip update triggered from a drag-and-drop

        if isinstance(self.plotted_waveform, DerivedWaveform):
            try:
                self.pane.object = self.main_curve()
            except Exception as e:
                self.editor.error_message = str(e)
                self.editor.alert_type = "danger"
            return

        if self.plotted_waveform is None or not self.plotted_waveform.tendencies:
            self.pane.object = hv.Curve(([], []), self.xlabel, self.ylabel)
            return

        # Find all piecewise linear tendencies
        pwl_tendencies = [
            tendency
            for tendency in self.plotted_waveform.tendencies
            if isinstance(tendency, PiecewiseLinearTendency)
        ]
        if not pwl_tendencies:
            # No need for a CurveEdit stream, just show the whole waveform:
            self.pane.object = self.main_curve()

        else:
            # Create a single Curve, which is a stitched together version of all
            # piecewise tendencies, and add a CurveEdit stream to it:
            pwl_values = [tendency.get_value() for tendency in pwl_tendencies]
            # Stitch tendencies into a single curve, separated by nan values:
            stitched_time = [[np.nan]] * (2 * len(pwl_values))
            stitched_values = [[np.nan]] * (2 * len(pwl_values))
            stitched_time[::2] = [val[0] for val in pwl_values]
            stitched_values[::2] = [val[1] for val in pwl_values]
            stitched_time = np.concatenate(stitched_time)
            stitched_values = np.concatenate(stitched_values)

            self.point_stream = streams.PointDraw(
                data={self.xlabel: stitched_time, self.ylabel: stitched_values},
            )
            self.point_stream.add_subscriber(self.piecewise_click_and_drag)

            edit_points = hv.DynamicMap(
                lambda data: hv.Points(data, [self.xlabel, self.ylabel]),
                streams=[self.point_stream],
            )

            overlay = hv.DynamicMap(self.main_curve, streams=[self.pipe]) * edit_points
            self.pane.object = overlay.opts(
                opts.Curve(line_width=2, color=hv.Cycle().values[0]),
                opts.Points(color="black", size=10, tools=["box_select"]),
            ).opts(
                framewise=True,
                show_legend=False,
                responsive=True,
            )

    def main_curve(self, **kwargs):
        """Return a curve representing the whole waveform"""
        return hv.Curve(self.plotted_waveform.get_value(), self.xlabel, self.ylabel)

    def piecewise_click_and_drag(self, data):
        """Updates a piecewise linear tendency in the code editor YAML time/value data.

        Args:
            data: Dictionary containing the new piecewise values.
        """
        yaml = YAML()
        content = self.editor.code_editor.value
        stream = StringIO(content)
        try:
            items = yaml.load(stream)
        except Exception:
            pn.state.notifications.error("Please fix the waveform errors first")
            return

        times = np.array(data[self.xlabel])
        values = np.array(data[self.ylabel])

        # Check if a new point is inserted:
        if not np.isnan(times[-1]):
            # Find out in which curve we need to insert the new point
            # NaN handling is tricky:
            # - Time array could end with many nans: [t1, t2, nan, ..., nan, newtime]
            newtime = times[-1]
            end_of_last_curve = len(times) - 1
            while np.isnan(times[end_of_last_curve - 1]):
                end_of_last_curve -= 1
            for itime in range(end_of_last_curve + 1):
                if times[itime] > newtime:
                    break

            if itime == 0 or np.isnan(times[itime - 1]):
                # Inserted in between two curves, this is not allowed
                times[-1] = values[-1] = np.nan  # Clear the point
                pn.state.notifications.warning(
                    "Cannot insert points outside of piecewise tendencies"
                )
            else:
                # Move new point to the right spot in times/values
                times[itime + 1 :] = times[itime:-1]
                times[itime] = newtime
                newvalue = values[-1]
                values[itime + 1 :] = values[itime:-1]
                values[itime] = newvalue
            self.point_stream.data = {self.xlabel: times, self.ylabel: values}

        # Ensure times are monotonically increasing
        if np.any(np.diff(times) <= 0):
            for i in range(1, len(times)):
                if times[i] <= times[i - 1]:
                    times[i] = times[i - 1] * (1 + 1e-15)
            self.point_stream.data = {self.xlabel: times, self.ylabel: values}
            pn.state.notifications.warning(
                "Times must be increasing: clipping to previous time point."
            )

        data_idx = 0
        nan_indices = [-1, *np.argwhere(np.isnan(times)).flatten()]

        # Update data of the piecewise linear tendencies
        for item in items:
            if item.get("type") == "piecewise":
                data_slice = slice(nan_indices[data_idx] + 1, nan_indices[data_idx + 1])
                time = times[data_slice]
                item["time"] = [float(x) for x in time]
                item["value"] = [float(x) for x in values[data_slice]]
                data_idx += 1

        output = StringIO()
        yaml.dump(items, output)
        with self._update_plot_from_drag:
            # Overwrite editor with updated data
            self.editor.code_editor.value = output.getvalue()
            # Trigger an update of self.main_curve
            self.pipe.event()

    def __panel__(self):
        return self.pane
