#!/usr/bin/env python3
"""
Aloha Water Treatment Plant PLC Simulation
Generic PLC interface which new protocols must adhere to
"""

import importlib
import logging
import os

from typing import Protocol, runtime_checkable

from aloha.plc.plc_simulation import SimulationContext
from aloha.constants import AlohaEnvVar, configure_logging

logger: logging.Logger = logging.getLogger(__name__)


@runtime_checkable
class PLCProtocolInterface(Protocol):
    """
    Protocol interface for PLC implementations used by the water treatment simulation.

    This interface defines the contract that any OT protocol implementation must
    satisfy so the simulation logic remains independent of protocol-specific code.

    To implement a PLC interface, you must implement a class with the following:
    - setup_plc: Establish any variables needed to run the plant logic
    - run_server: Establish a server that runs the simulation and that the HMI can use
    - handle_signal: Handle graceful shutdown of the server
    - update_simulation_from_plc: Update the context object with PLC values
    - update_plc_from_simulation: Update the PLC with values from the context object

    In general, for any protocol, you should, in your run_server method loop should
    - call update_simulation_from_plc
    - call simulation_step (in plc_simulation.py)
    - call update_plc_from_simulation
    - sleep for 1 second
    """

    # Implementations are expected to maintain an active/inactive server state
    # flag and a shared simulation context object.
    is_active: bool
    context: SimulationContext

    def setup_plc(self) -> None:
        """
        Initialize protocol-specific PLC state, data structures, and resources.
        """
        ...

    def run_server(self) -> None:
        """
        Start the protocol server and execute the main simulation loop.
        """
        ...

    def handle_signal(self, sig: int, frame: object | None) -> None:
        """
        Handle process termination signals by stopping the main loop.

        Args:
            sig: The received signal number.
            frame: The current stack frame, if provided by the signal handler.
        """
        ...

    def update_simulation_from_plc(self) -> None:
        """
        Read values from the PLC layer and copy them into the simulation context.
        """
        ...

    def update_plc_from_simulation(self) -> None:
        """
        Write values from the simulation context back into the PLC layer.
        """
        ...



def load_plc() -> PLCProtocolInterface:
    """
    Load and instantiate the PLC implementation selected by configuration.

    The module name is derived from the configured protocol value and is expected
    to expose a create_plc() factory function that returns a PLC-compatible object.

    Returns:
        A PLC implementation matching the configured protocol.

    Raises:
        RuntimeError: If the protocol is not configured, the module cannot be
            imported, or the required create_plc() factory is missing.
    """
    protocol_name = os.getenv(AlohaEnvVar.protocol.value)
    if not protocol_name: raise RuntimeError(f"{AlohaEnvVar.protocol.value} is not set")

    # PLC modules match the naming convention 'aloha.<protocol>.<protocol._plc'
    # e.g., "aloha.modbus.modbus_plc".
    module_name = f"aloha.{protocol_name.lower()}.{protocol_name.lower()}_plc"
    try:
        # Import the selected PLC implementation dynamically so the application
        # can support multiple protocol backends without hard-coding one here.
        module = importlib.import_module(f"{module_name}")
    except ImportError as e:
        msg = f"Could not load PLC module '{module_name}'"
        logger.error(msg)
        raise RuntimeError(msg) from e

    try:
        # Each PLC module must provide a create_plc() factory function.
        create_plc = getattr(module, "create_plc")
    except AttributeError as e:
        msg = f"Module '{module_name}' does not define a create_plc() function"
        logger.error(msg)
        raise RuntimeError(f"Module '{module_name}' does not define a create_plc() function") from e

    plc = create_plc()

    # Runtime protocol validation is intentionally left disabled.
    # The returned object is assumed to satisfy PLCProtocolInterface.
    #if not isinstance(plc, PLCProtocolInterface):
    #    raise TypeError(f"{module_name}.create_plc() does not return a PLCProtocolInterface")
    return plc

def main() -> None:
    """
    General startup
    Configure logging, load the PLC implementation, and start the server.
    """
    configure_logging()
    try:
        plc = load_plc()
    except RuntimeError as e:
        # Startup cannot continue without a valid PLC implementation.
        logger.critical(f"Unable to load PLC module, exiting")
        exit(1)

    # Initialize the PLC before entering the server loop.
    plc.setup_plc()
    plc.run_server()

if __name__ == "__main__":
    main()
