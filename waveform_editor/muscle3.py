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
    """Resolve one F_INIT port's candidate export time base and received IDS.

    Called once per connected F_INIT port; the caller picks which result (if any)
    becomes the actor's actual time base. The port name selects the mode. A port named
    ``<ids>_in`` (a valid IDS name) carrying that IDS exposes it as a *port-import*: the
    IDS is keyed by the port name so a config import ``{port: <input_port>}`` can read
    it, and its ``time`` array is offered as a candidate export time base. Combined
    with an ``<ids>/*`` import this overlays the waveforms onto the received IDS (e.g.
    adding Ip to an equilibrium). Any other port name yields no candidate time base
    (the caller falls back to *fresh export*, evaluating at ``msg.timestamp``).
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
    # - One or more input ports, received in their yMMSL declaration order. The first
    #   one named '<ids>_in' whose message carries that IDS selects overlay mode: the
    #   waveforms are exported on its /time and the result overlaid onto it. Every
    #   other '<ids>_in' port carrying an IDS is a port-import only -- available as
    #   {ref: <name>} via a `{port: <that port>}` globals.imports entry, resampled onto
    #   the primary time base -- without affecting which port drives the time base. If
    #   no port selects overlay mode, a single slice is exported at the first message's
    #   timestamp.
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
        if not input_ports:
            raise RuntimeError("At least one F_INIT port must be connected.")

        times = None
        received_idss = {}
        primary_msg = None
        for input_port in input_ports:
            msg = instance.receive(input_port)
            primary_msg = primary_msg or msg
            port_times, port_received = _time_base_and_received_idss(
                msg, input_port, config.globals.dd_version
            )
            received_idss.update(port_received)
            if times is None and port_received:
                times, primary_msg = port_times, msg
        if times is None:
            # No F_INIT port selected overlay mode: fresh export at the first
            # message's timestamp.
            times = np.array([primary_msg.timestamp])

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
            instance.send(
                portname,
                Message(primary_msg.timestamp, primary_msg.next_timestamp, data),
            )


if __name__ == "__main__":
    waveform_actor()
