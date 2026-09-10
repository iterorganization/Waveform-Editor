import logging

import param

from waveform_editor.util import AVAILABLE_DD_VERSIONS, LATEST_DD_VERSION

logger = logging.getLogger(__name__)


class YamlGlobals(param.Parameterized):
    dd_version = param.Selector(
        label="DD Version",
        default=LATEST_DD_VERSION,
        objects=AVAILABLE_DD_VERSIONS,
        doc="IMAS Data Dictionary version",
    )
    imports = param.Dict(
        label="Imports",
        default={},
        doc=(
            "External data entries this configuration copies from, as "
            "``{name: IMAS URI}``. A waveform reads one with ``{copy: <name>}``."
        ),
    )
    version = param.String(
        label="Format version",
        default="",
        doc="Version of the waveform file format this configuration is written in.",
    )

    def __init__(self, **params):
        super().__init__(**params)

    def set_globals(self, params):
        """Update globals from a dictionary."""
        self.param.update(**params)

    def reset(self):
        """Reset all parameters to their default values."""
        for p in self.param:
            if p != "name":
                setattr(self, p, self.param[p].default)

    def get(self):
        """Return all parameters wrapped under 'globals' key."""
        return {"globals": {p: getattr(self, p) for p in self.param if p != "name"}}
