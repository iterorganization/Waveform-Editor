"""MUSCLE3 subprocess runner functions for NICE integration, with no Panel dependency."""

import multiprocessing
import multiprocessing.connection
import os

import ymmsl
from libmuscle import Instance, Message
from libmuscle.manager.manager import Manager
from ymmsl import Operator

# YMMSL configuration for NICE inverse mode
_muscle3_inv_configuration = """
ymmsl_version: v0.1
model:
    name: shape_editor
    components:
        shape_editor:
            implementation: shape_editor
        nice_inv:
            implementation: nice_inv

    conduits:
        shape_editor.equilibrium_out: nice_inv.equilibrium_in
        shape_editor.pf_passive_out: nice_inv.pf_passive_in
        shape_editor.pf_active_out: nice_inv.pf_active_in
        shape_editor.iron_core_out: nice_inv.iron_core_in
        shape_editor.wall_out: nice_inv.wall_in
        nice_inv.equilibrium_out: shape_editor.equilibrium_in
        nice_inv.pf_active_out: shape_editor.pf_active_in

settings:
    muscle_profile_level: none  # Disable profiling
    nice_inv.xml_path: {xml_path}
"""

# YMMSL configuration for NICE direct mode
_muscle3_dir_configuration = """
ymmsl_version: v0.1
model:
    name: shape_editor
    components:
        shape_editor:
            implementation: shape_editor
        nice_dir:
            implementation: nice_dir

    conduits:
        shape_editor.equilibrium_out: nice_dir.equilibrium_in
        shape_editor.pf_passive_out: nice_dir.pf_passive_in
        shape_editor.pf_active_out: nice_dir.pf_active_in
        shape_editor.iron_core_out: nice_dir.iron_core_in
        shape_editor.wall_out: nice_dir.wall_in
        nice_dir.equilibrium_out: shape_editor.equilibrium_in

settings:
    muscle_profile_level: none  # Disable profiling
    nice_dir.xml_path: {xml_path}
"""


def run_muscle3_communicator(
    server_location: str,
    pipe: multiprocessing.connection.Connection,
    is_direct_mode: bool,
):
    """Run MUSCLE3 actor for communicating with NICE."""
    os.environ["MUSCLE_INSTANCE"] = "shape_editor"
    os.environ["MUSCLE_MANAGER"] = server_location

    ports = {
        Operator.O_I: [
            "equilibrium_out",
            "pf_active_out",
            "pf_passive_out",
            "wall_out",
            "iron_core_out",
        ],
        Operator.S: ["equilibrium_in"],
    }
    if not is_direct_mode:
        ports[Operator.S].append("pf_active_in")

    instance = Instance(ports)

    while instance.reuse_instance():
        while True:
            data = pipe.recv()
            if data is None:  # data = None signals that we should stop
                break

            eq, pfa, pfp, wall, ic = data
            instance.send("equilibrium_out", Message(0.0, 0.0, data=eq))
            instance.send("pf_active_out", Message(0.0, 0.0, data=pfa))
            instance.send("pf_passive_out", Message(0.0, 0.0, data=pfp))
            instance.send("wall_out", Message(0.0, 0.0, data=wall))
            instance.send("iron_core_out", Message(0.0, 0.0, data=ic))

            # Wait for nice to process
            eq = instance.receive("equilibrium_in").data
            if not is_direct_mode:
                pfa = instance.receive("pf_active_in").data
            pipe.send((eq, pfa))


def run_muscle_manager(
    pipe: multiprocessing.connection.Connection, xml_path: str, is_direct_mode: bool
):
    """Run the muscle_manager with a given configuration."""
    config_str = (
        _muscle3_dir_configuration if is_direct_mode else _muscle3_inv_configuration
    )
    config = ymmsl.load(config_str.format(xml_path=xml_path))
    manager = Manager(config)
    server_location = manager.get_server_location()
    pipe.send(server_location)
    pipe.recv()  # Blocks until we're instructed to stop
    pipe.close()
    manager.stop()
