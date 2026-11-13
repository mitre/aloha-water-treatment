#!/usr/bin/env python3
"""
Aloha Water Treatment Plant PLC Simulation
Generic PLC interface which new protocols must adhere to
"""

import importlib
import logging
import sys

from typing import Protocol, runtime_checkable

from simulator import SIM
from simulator.sim import SimulationContext
from simulator.config import configure_logging, parse_args

logger: logging.Logger = logging.getLogger(__name__)


@runtime_checkable
class PLCProtocolInterface(Protocol):
    """
    Protocol interface for PLC implementations used by the water treatment simulation.

    This interface defines the contract that any OT protocol implementation must
    satisfy so the simulation logic remains independent of protocol-specific code.

    To implement a PLC interface, you must implement a class with the following:
    - setup_plc: Establish any variables needed to run the plant logic
    - run_server: Establish a server that runs the simulation and that the HMI can use,
      and return the exit status
    - handle_signal: Handle graceful shutdown of the server
    - update_simulation_from_plc: Update the context object with PLC values
    - update_plc_from_simulation: Update the PLC with values from the context object

    In general, for any protocol, you should, in your run_server method loop should
    - call update_simulation_from_plc
    - call simulation_step (in sim.py)
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

    def run_server(self) -> int:
        """
        Start the protocol server and execute the main simulation loop.

        Returns:
            0 after a clean shutdown, 1 if the server could not start.
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



def load_plc(protocol: str, host: str, port: int) -> PLCProtocolInterface:
    """
    Load and instantiate the PLC implementation for a protocol.

    The module name is derived from the protocol and is expected to expose a
    create_plc(host, port) factory function that returns a PLC-compatible object.

    Args:
        protocol: The protocol name, e.g. "modbus".
        host: The address the PLC binds to.
        port: The port the PLC listens on.

    Returns:
        A PLC implementation matching the protocol.

    Raises:
        RuntimeError: If the module cannot be imported, or the required
            create_plc() factory is missing.
    """
    # PLC modules match the naming convention 'simulator.<protocol>.<protocol>_plc'
    # e.g., "simulator.modbus.modbus_plc".
    module_name = f"simulator.{protocol.lower()}.{protocol.lower()}_plc"
    try:
        # Import the selected PLC implementation dynamically so the application
        # can support multiple protocol backends without hard-coding one here.
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise RuntimeError(f"Could not load PLC module '{module_name}': {e}") from e

    try:
        # Each PLC module must provide a create_plc() factory function.
        create_plc = getattr(module, "create_plc")
    except AttributeError as e:
        raise RuntimeError(f"Module '{module_name}' does not define a create_plc() function") from e

    return create_plc(host, port)

def main(argv: list[str] | None = None) -> int:
    """
    General startup
    Parse the command line, configure logging, load the PLC implementation,
    and start the server.

    Returns:
        The process exit status.
    """
    args = parse_args(
        prog="python -m simulator.plc",
        description=f"{SIM['name']} PLC: a Modbus or BACnet device.",
        host_help="address to bind (default: ALOHA_IP in the config, 0.0.0.0 for Modbus, auto for BACnet)",
        port_help="Modbus or BACnet port (default: ALOHA_PORT in the config, 5020 for Modbus, 47808 for BACnet)",
        argv=argv)
    configure_logging(args.debug)
    try:
        plc = load_plc(args.protocol, args.host, args.port)
    except RuntimeError as e:
        # Startup cannot continue without a valid PLC implementation.
        logger.error(e)
        return 1

    # Initialize the PLC before entering the server loop.
    plc.setup_plc()
    return plc.run_server()

if __name__ == "__main__":
    sys.exit(main())
