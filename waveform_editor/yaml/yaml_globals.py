import logging

import param

from waveform_editor.util import AVAILABLE_DD_VERSIONS, LATEST_DD_VERSION

logger = logging.getLogger(__name__)

# Configuration schema version. Bumped to 2 when bare-string values became literal
# string constants instead of derived-waveform expressions.
CURRENT_SCHEMA_VERSION = 2


class YamlGlobals(param.Parameterized):
    version = param.Integer(
        default=CURRENT_SCHEMA_VERSION,
        label="Schema Version",
        doc="Waveform Editor configuration schema version.",
    )
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
            "Named external data entries to import values from. Each value is either "
            "an IMAS URI string, or a mapping ``{port: <name>}`` referring to an IDS "
            "received on a MUSCLE3 port at run time. Consumed by ``{ref: <name>}`` "
            "import entries in waveforms."
        ),
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
