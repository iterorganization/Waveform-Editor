import logging
from pathlib import Path

import numpy as np

# N.B. libmuscle is an optional dependency
from libmuscle import Instance, InstanceFlags, Message
from ymmsl import Operator

from waveform_editor.cli import load_config
from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.exporter import ConfigurationExporter

logger = logging.getLogger(__name__)


def waveform_actor():
    logger.info("Starting waveform actor")

    # N.B. we don't specify our port names, ports are created by libmuscle based on the
    # conduits specified in the yMMSL file.
    # - We require exactly one input port for which we only use the timestamp
    # - Output port names must be '<ids_name>_out' or '<ids_name>'
    instance = Instance(flags=InstanceFlags.KEEPS_NO_STATE_FOR_NEXT_USE)

    # Settings
    fname = None
    config = WaveformConfiguration()

    while instance.reuse_instance():
        # Apply settings
        new_fname = Path(instance.get_setting("waveforms"))

        # Load (new) waveform configuration
        if new_fname != fname:
            fname = new_fname
            logger.info("Loading waveform configuration from %s", fname)
            load_config(config, fname)

        ports = instance.list_ports()
        if len(ports.get(Operator.F_INIT, [])) != 1:
            raise RuntimeError("Exactly one F_INIT port must be connected.")
        input_port = ports[Operator.F_INIT][0]
        msg = instance.receive(input_port)

        exporter = ConfigurationExporter(config, np.array([msg.timestamp]))
        idss = exporter.to_ids_dict()

        for portname in ports[Operator.O_F]:
            # Strip any _out from the portname
            idsname = portname.removesuffix("_out")

            if idsname not in idss:
                raise RuntimeError(
                    f"Output port '{portname}' does not match any IDS in the "
                    f"waveform configuration (from '{fname}'). Available IDSs are: "
                    f"{', '.join(idss) or '<none>'}"
                )

            data = idss[idsname].serialize()
            instance.send(portname, Message(msg.timestamp, msg.next_timestamp, data))


if __name__ == "__main__":
    waveform_actor()
