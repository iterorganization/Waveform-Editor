import pandas as pd
import panel as pn
import param

from waveform_editor.shape_editor.plasma_shape_calc import apply_point_weights


class WeightedPointsTable(param.Parameterized):
    """Widget for managing weighted points table for defining plasma shape."""

    COL_R = "R [m]"
    COL_Z = "Z [m]"
    COL_WEIGHT = "weight"
    MAX_WEIGHT = 5000
    COL_DELETE = "🗑️"

    points = param.DataFrame(default=pd.DataFrame(columns=[COL_R, COL_Z, COL_WEIGHT]))

    def __init__(self):
        super().__init__()
        initial_df = pd.DataFrame(
            columns=(self.COL_DELETE, self.COL_R, self.COL_Z, self.COL_WEIGHT)
        )
        self._tabulator = pn.widgets.Tabulator(
            value=initial_df,
            editors={
                self.COL_DELETE: None,
                self.COL_R: {"type": "number"},
                self.COL_Z: {"type": "number"},
                self.COL_WEIGHT: {"type": "number", "step": 1},
            },
            layout="fit_data_fill",
            sizing_mode="stretch_width",
            # Scrolled within, rather than the panel, when there are many points
            max_height=400,
            show_index=False,
            margin=0,
            on_click=self._on_delete_click,
            on_edit=self._on_edit,
        )
        self._update_tabulator()

    def set_points(self, r, z, weights):
        """Replace the table contents, keeping the points in the order given.

        Args:
            r: Radial coordinates of the points.
            z: Height coordinates of the points.
            weights: How many times each point is repeated in the boundary.
        """
        rows = [
            {
                self.COL_R: round(float(rv), 3),
                self.COL_Z: round(float(zv), 3),
                self.COL_WEIGHT: self.as_weight(w),
            }
            for rv, zv, w in zip(r, z, weights, strict=True)
        ]
        self.points = pd.DataFrame(
            rows, columns=[self.COL_R, self.COL_Z, self.COL_WEIGHT]
        )
        self._update_tabulator()

    def _valid_rows(self):
        """The rows that have both coordinates filled in."""
        df = self.points.dropna(subset=[self.COL_R, self.COL_Z])
        return df[(df[self.COL_R] != "") & (df[self.COL_Z] != "")]

    def as_weight(self, value):
        """A weight as a whole number of repeats, within bounds. Points drawn on
        the plot arrive without a weight, and a weight below 1 would drop them."""
        try:
            return min(max(int(value), 1), self.MAX_WEIGHT)
        except (TypeError, ValueError):
            return 1

    def get_points(self):
        """The points entered, without weight duplication.

        Returns:
            tuple: (r, z, weights) lists, empty when no valid points are entered.
        """
        rows = self._valid_rows()
        return (
            list(rows[self.COL_R]),
            list(rows[self.COL_Z]),
            [int(w) for w in rows[self.COL_WEIGHT]],
        )

    def _update_tabulator(self, event=None):
        """Update the Tabulator to reflect the current DataFrame."""
        df = self.points
        data = []
        for _, row in df.iterrows():
            data.append(
                (
                    self.COL_DELETE,
                    row[self.COL_R],
                    row[self.COL_Z],
                    row[self.COL_WEIGHT],
                )
            )

        # Add empty row if last data row has R and Z values filled
        if len(df) == 0 or (
            df.iloc[-1][self.COL_R] != "" and df.iloc[-1][self.COL_Z] != ""
        ):
            data.append((self.COL_DELETE, "", "", 1))

        new_df = pd.DataFrame(
            data, columns=(self.COL_DELETE, self.COL_R, self.COL_Z, self.COL_WEIGHT)
        )
        # Convert columns to allow mixed types
        new_df[self.COL_R] = new_df[self.COL_R].astype(object)
        new_df[self.COL_Z] = new_df[self.COL_Z].astype(object)
        new_df[self.COL_WEIGHT] = new_df[self.COL_WEIGHT].astype(object)
        self._tabulator.value = new_df

    def _on_delete_click(self, event):
        if event.column == self.COL_DELETE:
            n_data_rows = len(self.points)
            if event.row < n_data_rows:
                df = self.points.copy()
                df = df.drop(index=event.row).reset_index(drop=True)
                self.param.update(points=df)
                self._update_tabulator()

    def _on_edit(self, event):
        """Handle edits in the weighted points tabulator."""
        df = self.points.copy()
        is_empty_row = event.row >= len(df)

        # Convert columns to object dtype to allow mixed types
        for col in [self.COL_R, self.COL_Z, self.COL_WEIGHT]:
            if col in df.columns:
                df[col] = df[col].astype(object)

        value = event.value
        if event.column == self.COL_WEIGHT:
            rounded = round(value) if value is not None else None
            if rounded is None or rounded < 1 or rounded > self.MAX_WEIGHT:
                pn.state.notifications.error(
                    f"Weight must be a whole number between 1 and {self.MAX_WEIGHT}"
                )
                prev = (
                    self.points.iloc[event.row][self.COL_WEIGHT]
                    if not is_empty_row
                    else 1
                )
                self._tabulator.value.at[event.row, self.COL_WEIGHT] = prev
                self._tabulator.param.trigger("value")
                return
            if rounded != value:
                self._tabulator.value.at[event.row, self.COL_WEIGHT] = rounded
                self._tabulator.param.trigger("value")
            value = rounded

        if is_empty_row:
            new_row = {self.COL_R: "", self.COL_Z: "", self.COL_WEIGHT: 1}
            new_row[event.column] = value
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            df.at[event.row, event.column] = value

        self.points = df

        edited_row = df.iloc[event.row]
        is_last_row = event.row == len(df) - 1
        row_now_complete = edited_row[self.COL_R] != "" and edited_row[self.COL_Z] != ""
        if is_last_row and row_now_complete:
            self._update_tabulator()

    def get_outline_coordinates(self):
        """Generate outline coordinates from weighted points.

        Returns:
            tuple: (outline_r, outline_z) lists of coordinates, or (None, None) if
                no valid points have been entered yet
        """
        r, z, weights = self.get_points()
        if not r:
            return None, None
        return apply_point_weights(r, z, weights)

    def __panel__(self):
        return self._tabulator
