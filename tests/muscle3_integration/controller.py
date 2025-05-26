import imas
import numpy as np
from libmuscle import Instance, Message
from ymmsl import Operator


def controller():
    """Dummy controller actor for demonstrating the waveform actor."""
    instance = Instance(
        ports={
            Operator.O_I: ["time_out"],
            Operator.S: ["ec_launchers_in", "nbi_in"],
        }
    )

    factory = imas.IDSFactory("4.0.0")

    while instance.reuse_instance():
        for time in np.linspace(0, 50, 20):
            # The data of this message is ignored by the waveform-actor, only the
            # timestamp is relevant:
            instance.send("time_out", Message(time))

            # Receive waveform input
            msg = instance.receive("ec_launchers_in")
            ec_launchers = factory.new("ec_launchers")
            ec_launchers.deserialize(msg.data)

            msg = instance.receive("nbi_in")
            nbi = factory.new("nbi")
            nbi.deserialize(msg.data)

            # An actual actor would do something with the received data now:
            ...


if __name__ == "__main__":
    controller()
