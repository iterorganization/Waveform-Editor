import imas
import numpy as np
from libmuscle import Instance, Message
from ymmsl import Operator


def solver():
    """Dummy solver demonstrating the waveform actor on a whole-trace equilibrium.

    It sends a whole-trace equilibrium and receives back a fresh equilibrium with the
    configured waveforms (the plasma current) evaluated on that same time base.
    """
    instance = Instance(
        ports={
            Operator.O_I: ["equilibrium_out"],
            Operator.S: ["equilibrium_in"],
        }
    )

    factory = imas.IDSFactory("4.1.1")

    while instance.reuse_instance():
        equilibrium = factory.new("equilibrium")
        equilibrium.ids_properties.homogeneous_time = (
            imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        )
        times = np.linspace(0, 100, 11)
        equilibrium.time = times
        equilibrium.time_slice.resize(len(times))
        instance.send(
            "equilibrium_out", Message(times[0], data=equilibrium.serialize())
        )

        # Receive a fresh equilibrium with ip evaluated on the sent /time:
        msg = instance.receive("equilibrium_in")
        result = factory.new("equilibrium")
        result.deserialize(msg.data)
        assert len(result.time_slice) == len(times)
        assert result.time_slice[-1].global_quantities.ip == -15e6


if __name__ == "__main__":
    solver()
