"""Module that enables running the NICE equilibrium solver through MUSCLE3."""

import asyncio
import multiprocessing
import os
import signal
import subprocess
import tempfile

import panel as pn
import param
from imas.ids_toplevel import IDSToplevel

from waveform_editor.shape_editor.muscle3_runner import (
    run_muscle3_communicator,
    run_muscle_manager,
)
from waveform_editor.settings import settings


class NiceIntegration(param.Parameterized):
    """Main API for running NICE, submitting problems and getting the resulting
    equilibrium back.
    """

    muscle_manager_running = param.Boolean(doc="muscle_manager process is running")
    nice_running = param.Boolean(doc="NICE process is running")
    communicator_running = param.Boolean(
        doc="The process for communicating with NICE is running"
    )
    equilibrium = param.ClassSelector(class_=IDSToplevel)
    pf_active = param.ClassSelector(class_=IDSToplevel)

    processing = param.Boolean(doc="NICE is processing an equilibrium")

    def __init__(self, imas_factory):
        super().__init__()
        self.imas_factory = imas_factory
        self.terminal = pn.widgets.Terminal(
            # write_to_console=True,
            sizing_mode="stretch_width",
            options={"scrollback": 10000, "wrap": True},
            height=200,
            max_width=750,
        )
        self.running = False
        self.closing = False
        self.pf_active = None

    async def close(self):
        """Shutdown all running subprocesses and close any open files."""
        if not self.running or self.closing:
            return
        self.closing = True
        self.xml_config_file.close()

        # Stop communicator
        if self.communicator.is_alive():
            self.communicator_pipe.send(None)
        for _ in range(10):  # Wait at most 1 second before killing
            if not self.communicator.is_alive():
                break
            await asyncio.sleep(0.1)
        else:  # Kill the communicator if it didn't stop after 1 second
            self.communicator.kill()

        # Stop NICE
        if self.nice_transport is not None:
            if self.nice_transport.get_returncode() is None:
                self.nice_transport.send_signal(signal.SIGINT)  # Send Ctrl+C signal
            for _ in range(10):
                if self.nice_transport.get_returncode() is not None:
                    break
                await asyncio.sleep(0.1)
            else:  # Kill the communicator if it didn't stop after 1 second
                self.nice_transport.kill()

        # Stop MUSCLE Manager
        self.manager_pipe.send(None)
        for _ in range(10):
            if not self.manager.is_alive():
                break
            await asyncio.sleep(0.1)
        else:  # Kill the muscle_manager if it didn't stop after 1 second
            self.manager.kill()

        # Cleanup
        self.processing = False
        self.communicator_pipe.close()
        self.manager_pipe.close()
        if self.pn_callback is not None:
            self.pn_callback.stop()
        self.closing = self.running = False
        self._update_state()

    async def run(self, is_direct_mode=False):
        """Start NICE and the controlling processes."""
        if self.running:
            raise RuntimeError("Already running!")
        self.running = True

        self.xml_config_file = tempfile.NamedTemporaryFile()  # noqa: SIM115

        # MUSCLE manager
        self.manager_pipe, pipe = multiprocessing.Pipe()
        self.manager = multiprocessing.Process(
            target=run_muscle_manager,
            args=[pipe, self.xml_config_file.name, is_direct_mode],
            name="MUSCLE Manager",
        )
        self.manager.start()
        manager_location = self.manager_pipe.recv()

        # MUSCLE3 communicator
        self.communicator_pipe, pipe = multiprocessing.Pipe()
        self.communicator = multiprocessing.Process(
            target=run_muscle3_communicator,
            args=[manager_location, pipe, is_direct_mode],
            name="NICE Communicator",
        )
        self.communicator.start()

        # NICE
        nice_env = os.environ.copy()
        nice_env.update(settings.nice.environment)
        nice_env["MUSCLE_MANAGER"] = manager_location

        if is_direct_mode:
            executable = settings.nice.dir_executable
            nice_env["MUSCLE_INSTANCE"] = "nice_dir"
        else:
            executable = settings.nice.inv_executable
            nice_env["MUSCLE_INSTANCE"] = "nice_inv"

        self.terminal.write(f"{os.getcwd()}$ {executable}\n")

        loop = asyncio.get_running_loop()
        try:
            self.nice_transport, self.nice_protocol = await loop.subprocess_exec(
                self.create_communicator_protocol,
                executable,
                env=nice_env,
                stdin=subprocess.DEVNULL,
            )
        except Exception as exc:
            self.terminal.write(str(exc) + "\n")
            self.pn_callback = self.nice_transport = self.nice_protocol = None
            self._update_state()
            await self.close()
            raise

        # Update state every 500ms
        self.pn_callback = pn.state.add_periodic_callback(self._update_state, 500)
        self._update_state()

    def create_communicator_protocol(self):
        """Instantiate helper class to display NICE output in self.nice_terminal"""
        return TerminalCommunicatorProtocol(self.terminal)

    def _update_state(self):
        """Check if subprocesses are still running."""
        self.muscle_manager_running = self.manager.is_alive()
        self.communicator_running = self.communicator.is_alive()
        self.nice_running = (
            self.nice_transport is not None
            and self.nice_transport.get_returncode() is None
        )

    @param.depends("nice_running", watch=True)
    async def _nice_running_changed(self):
        if not self.nice_running:  # figure out why:
            retcode = self.nice_transport.get_returncode()
            # Bold green on success, bold red on failure:
            color = "\033[32;1m" if retcode == 0 else "\033[31;1m"
            # Add signal description (if relevant), e.g. 'Segmentation fault'
            reason = f" ({signal.strsignal(-retcode)})" if retcode < 0 else ""
            self.terminal.write(
                f"{color}NICE exited with status={retcode}{reason}\033[0m\n"
            )
            # Cleanup after a crash
            await self.close()

    async def submit(
        self,
        xml_params: str,
        equilibrium: bytes,
        pf_active: bytes,
        pf_passive: bytes,
        wall: bytes,
        iron_core: bytes,
    ):
        """Submit a new equilibrium reconstruction job to NICE.

        Args:
            xml_params: NICE XML parameters
            equilibrium: Serialized equilibrium IDS
            pf_active: Serialized pf_active IDS
            pf_passive: Serialized pf_passive IDS
            wall: Serialized wall IDS
            iron_core: Serialized iron_core IDS
        """
        if self.processing:
            raise RuntimeError(
                "NICE is already processing an equilibrium reconstruction"
            )

        # Overwrite config file with new parameters
        self.xml_config_file.seek(0)
        self.xml_config_file.truncate()
        self.xml_config_file.write(xml_params.encode())
        self.xml_config_file.flush()

        # Push IDSs to NICE
        self.communicator_pipe.send(
            (equilibrium, pf_active, pf_passive, wall, iron_core)
        )
        self.processing = True

        # Wait until we have a result
        while not self.communicator_pipe.poll():
            await asyncio.sleep(0.1)
        try:
            eq, pfa = self.communicator_pipe.recv()
        except EOFError:  # NICE and/or communicator has crashed
            self.processing = False
            return

        # Set output
        equilibrium = self.imas_factory.new("equilibrium")
        equilibrium.deserialize(eq)
        self.equilibrium = equilibrium
        pf_active = self.imas_factory.new("pf_active")
        pf_active.deserialize(pfa)
        self.pf_active = pf_active
        self.processing = False


class TerminalCommunicatorProtocol(asyncio.SubprocessProtocol):
    """Helper class to display subprocess output in a panel Terminal widget"""

    def __init__(self, terminal):
        self.terminal = terminal
        self._closed = False

    def pipe_data_received(self, fd, data):
        self.terminal.write(data)
