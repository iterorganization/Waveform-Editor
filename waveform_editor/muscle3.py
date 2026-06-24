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


def _time_base_and_received_idss(msg, input_port, dd_version):
    """Resolve the export time base and the IDS received on the input port.

    The input port name selects the mode. A port named ``<ids>_in`` (a valid IDS name)
    carrying that IDS exposes it as a *port-import*: the IDS is keyed by the port name
    so a config import ``{port: <input_port>}`` can read it, and the waveforms are
    evaluated on its ``time`` array. Combined with an ``<ids>/*`` import this overlays
    the waveforms onto the received IDS (e.g. adding Ip to an equilibrium). Any other
    port name selects *fresh export*: the waveforms are evaluated at ``msg.timestamp``
    into a single slice.
    """
    name = input_port.removesuffix("_in")
    factory = imas.IDSFactory(dd_version)
    if not factory.exists(name) or msg.data is None:
        logger.info("fresh-export mode on '%s'", input_port)
        return np.array([msg.timestamp]), {}

    logger.info("received '%s' on '%s' (available as a port-import)", name, input_port)
    received = factory.new(name)
    received.deserialize(msg.data)

    # The waveforms are evaluated on '/time' and written back homogeneous, so '/time' is
    # not authoritative for a non-homogeneous IDS: warn rather than fail.
    if int(received.ids_properties.homogeneous_time) != (
        imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
    ):
        logger.warning("received '%s' IDS is not in homogeneous time mode", name)

    times = np.asarray(received.time, dtype=float)
    if times.size == 0:
        raise RuntimeError(f"received '{name}' IDS has no root '/time'")
    return times, {input_port: received}


def waveform_actor():
    logger.info("Starting waveform actor")

    # Ports are created by libmuscle from the yMMSL conduits, not named here.
    # - Exactly one input port. If named '<ids>_in' and the message carries that IDS,
    #   the waveforms are exported on its /time and overlaid onto it; otherwise a single
    #   slice at the message timestamp is exported.
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
        if len(ports.get(Operator.F_INIT, [])) != 1:
            raise RuntimeError("Exactly one F_INIT port must be connected.")
        input_port = ports[Operator.F_INIT][0]
        msg = instance.receive(input_port)

        times, received_idss = _time_base_and_received_idss(
            msg, input_port, config.globals.dd_version
        )
        exporter = ConfigurationExporter(config, times, received_idss=received_idss)
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
