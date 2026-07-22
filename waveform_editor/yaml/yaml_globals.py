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
    machine_description = param.Dict(
        label="Machine Description URIs",
        default={},
        doc="Machine description URIs for each IDS.",
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
