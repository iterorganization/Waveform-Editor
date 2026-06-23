import imas
import numpy as np
from libmuscle import Instance, Message
from ymmsl import Operator


def solver():
    """Dummy solver demonstrating the waveform actor in overlay mode.

    It sends a whole-trace equilibrium and receives it back with the configured
    waveforms (the plasma current) overlaid onto its time slices, its other data kept.
    """
    instance = Instance(
        ports={
            Operator.O_I: ["equilibrium_out"],
            Operator.S: ["equilibrium_in"],
        }
    )

    factory = imas.IDSFactory("4.0.0")

    while instance.reuse_instance():
        # Build an equilibrium carrying pre-existing data (a boundary outline):
        equilibrium = factory.new("equilibrium")
        equilibrium.ids_properties.homogeneous_time = (
            imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        )
        times = np.linspace(0, 100, 11)
        equilibrium.time = times
        equilibrium.time_slice.resize(len(times))
        for time_slice in equilibrium.time_slice:
            time_slice.boundary.outline.r = [4.0, 6.0, 8.0]
        instance.send(
            "equilibrium_out", Message(times[0], data=equilibrium.serialize())
        )

        # Receive the equilibrium with ip overlaid on its /time and the rest preserved:
        msg = instance.receive("equilibrium_in")
        result = factory.new("equilibrium")
        result.deserialize(msg.data)
        assert len(result.time_slice) == len(times)
        assert result.time_slice[-1].global_quantities.ip == -15e6
        assert np.array_equal(result.time_slice[0].boundary.outline.r, [4.0, 6.0, 8.0])


if __name__ == "__main__":
    solver()
