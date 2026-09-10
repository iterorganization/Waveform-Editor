import logging
from pathlib import Path

import imas
import numpy as np

# N.B. libmuscle is an optional dependency
from libmuscle import Instance, InstanceFlags, Message
from ymmsl import Operator

from waveform_editor.cli import load_config
from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.export.exporter import ConfigurationExporter

logger = logging.getLogger(__name__)


def _export_times(msg, input_port, dd_version):
    """The time base to evaluate the waveforms on, from the message on ``input_port``.

    The actor takes one input and takes one thing from it: the root ``/time`` of a
    homogeneous IDS. That may be a single time step or a whole trace; the rest of the
    message is ignored. The port is named ``<ids>_in`` so the IDS can be deserialized --
    its content plays no part beyond ``/time``.
    """
    name = input_port.removesuffix("_in")
    factory = imas.IDSFactory(dd_version)
    if not factory.exists(name):
        raise RuntimeError(
            f"input port '{input_port}' must be named '<ids>_in' so its time base can "
            f"be read; '{name}' is not an IDS in DD {dd_version}"
        )
    if msg.data is None:
        raise RuntimeError(
            f"no data on '{input_port}': nothing to take a time base from"
        )

    ids = factory.new(name)
    ids.deserialize(msg.data)

    times = np.asarray(ids.time, dtype=float)
    if times.size == 0:
        raise RuntimeError(f"the '{name}' received on '{input_port}' has no root /time")
    if int(ids.ids_properties.homogeneous_time) != (
        imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
    ):
        logger.warning(
            "the '%s' received on '%s' is in heterogeneous time mode; evaluating "
            "on its root /time anyway",
            name,
            input_port,
        )
    logger.info("exporting on %d time step(s) from '%s'", times.size, input_port)
    return times


def waveform_actor():
    logger.info("Starting waveform actor")

    # Ports are created by libmuscle from the yMMSL conduits, not named here.
    # - Exactly one input port, named '<ids>_in'. Only the root /time of that message is
    #   used: it is the time base the waveforms are evaluated on. Everything else the
    #   design needs it reads itself, from the URIs in its `imports:`.
    # - Output port names must be '<ids>_out' or '<ids>'.
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
        input_ports = ports.get(Operator.F_INIT, [])
        if len(input_ports) != 1:
            raise RuntimeError(
                "Exactly one F_INIT port must be connected, to supply the time base; "
                f"got {len(input_ports)}: {', '.join(input_ports) or '<none>'}"
            )
        input_port = input_ports[0]
        msg = instance.receive(input_port)
        times = _export_times(msg, input_port, config.globals.dd_version)

        exporter = ConfigurationExporter(config, times)
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
