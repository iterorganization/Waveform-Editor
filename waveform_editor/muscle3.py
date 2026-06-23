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


def _time_base_and_base_ids(msg, input_port, dd_version):
    """Resolve the export time base and the optional base IDS to overlay onto.

    The input port name selects the mode. A port named ``<ids>_in`` (a valid IDS name)
    selects *overlay*: the message must carry that IDS, and the waveforms are evaluated
    on its ``time`` array and overlaid onto it in place, preserving its other data so it
    can be passed on (e.g. adding Ip to an equilibrium). Any other name selects *fresh
    export*: the waveforms are evaluated at ``msg.timestamp`` into a single slice.
    """
    name = input_port.removesuffix("_in")
    factory = imas.IDSFactory(dd_version)
    if not factory.exists(name):
        logger.info("fresh-export mode on '%s' (not an IDS name)", input_port)
        return np.array([msg.timestamp]), {}

    logger.info("overlay mode on '%s': overlaying onto '%s'", input_port, name)
    if msg.data is None:
        raise RuntimeError(
            f"input port '{input_port}' selects overlay mode, but the message carried "
            f"no '{name}' IDS"
        )
    base = factory.new(name)
    base.deserialize(msg.data)

    # Overlay evaluates the waveforms on '/time' and writes the result back homogeneous,
    # so '/time' is not authoritative for a non-homogeneous base: warn rather than fail.
    if int(base.ids_properties.homogeneous_time) != (
        imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
    ):
        logger.warning("received '%s' IDS is not in homogeneous time mode", name)

    times = np.asarray(base.time, dtype=float)
    if times.size == 0:
        raise RuntimeError(f"received '{name}' IDS has no root '/time' to overlay onto")
    return times, {name: base}


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

        times, base_idss = _time_base_and_base_ids(
            msg, input_port, config.globals.dd_version
        )
        exporter = ConfigurationExporter(config, times, base_idss=base_idss)
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
