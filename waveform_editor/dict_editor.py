import pandas as pd
import panel as pn
import param


class DictEditor(pn.viewable.Viewer):
    """A Panel widget for editing Python dictionaries in a tabular interface."""

    value = param.Dict(default={}, allow_refs=True)

    def __init__(self, key_options=None, names=("key", "value"), **params):
        """Initialize the DictEditor widget.

        Args:
            key_options: List of allowed keys shown in the dropdown editor.
            names: Tuple of column names to display for keys and values.
        """
        if key_options is None:
            key_options = []
        self.tabulator = pn.widgets.Tabulator(
            editors={"key": {"type": "list", "values": key_options}},
            titles={"index": "#", "key": names[0], "value": names[1]},
            layout="fit_data_stretch",
            sizing_mode="stretch_width",
        )
        self.tabulator.on_edit(self.on_cell_update)
        super().__init__(**params)

    @param.depends("value", watch=True, on_init=True)
    def update_value(self):
        """Update the Tabulator widget to reflect the current dictionary."""
        # Create pd Dataframe from input dict
        df = pd.DataFrame([*self.value.items(), ("", "")], columns=("key", "value"))
        self.tabulator.value = df

    def on_cell_update(self, event):
        """Callback for when a cell in the Tabulator is edited."""
        # Copy current dict and overwrite later to ensure watchers are triggered
        new_value = self.value.copy()

        # Callback when user edits a cell
        if event.column == "value":
            key = self.tabulator.value["key"][event.row]
            new_value[key] = event.value
        elif event.column == "key":
            if event.value in new_value:
                self.tabulator.value.loc[event.row, "key"] = event.old
                self.tabulator.param.trigger("value")
                return
            if event.old in new_value:
                new_value[event.value] = new_value.pop(event.old)
            else:
                new_value[event.value] = ""
            if event.old == "":
                self.tabulator.value.loc[len(self.tabulator.value)] = ("", "")
            self.tabulator.param.trigger("value")

        self.value = new_value

    def __iter__(self):
        yield self.tabulator

    def __panel__(self):
        return self.tabulator
