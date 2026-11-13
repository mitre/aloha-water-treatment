"""
Aloha Water Treatment Plant HMI
Flask web application for monitoring and controlling the treatment plant
"""


import importlib
import logging
import signal
import sys

from enum import StrEnum
from flask import Flask, render_template, request, jsonify, Response
from typing import Protocol, runtime_checkable
from werkzeug.serving import make_server

from simulator import SIM
from simulator.config import configure_logging, parse_args
from simulator.sim import SimulationContext, TANK_MAX

logger: logging.Logger = logging.getLogger(__name__)

# Controls exposed by the HMI to the user interface.
class HMIControl(StrEnum):
    estop    = "emergencyStop"
    inflow   = "inflowRate"
    outflow  = "outflowRate"
    pswitch  = "pumpSwitch"
    manualop = "inflowMode"


@runtime_checkable
class HMIClientInterface(Protocol):
    """
    Protocol contract for HMI client implementations.

    An HMI client is responsible for communicating with the selected OT
    protocol backend and keeping a local SimulationContext synchronized so the
    web UI can display current process state.
    """

    # Implementations are expected to maintain a local copy of the shared
    # simulation state for display and command handling.
    simulation: SimulationContext = SimulationContext()


    def initialize_client(self, host: str, port: int, client_cidr: int | None = None):
        """
        Initialize the HMI client and any protocol-specific resources.

        Args:
            host: The PLC's address.
            port: The PLC's port.
            client_cidr: Prefix length for the client's own address, for
                protocols that bind one (BACnet), or None to read it from the
                interface.
        """
        ...

    def send_command_to_server(self, command: HMIControl, value) -> tuple[Response, int]:
        """
        Validate and route an HMI command to the appropriate protocol handler.

        With manual mode off, inflow and outflow adjustments are rejected because
        those values are controlled by the simulation logic rather than the
        operator.

        Args:
            command: The HMI control being updated.
            value: The requested value for the control.

        Returns:
            A Flask-style JSON response object and HTTP status code.
        """

        logger.info(f"Command: {command.value}={value}")
        try:
            if not self.simulation.manual_op:  # Flow rates are only ajusted in manual mode
                if command in [HMIControl.outflow, HMIControl.inflow]:
                    logger.error("Flow rates are currently auto-controlled, cannot adjust")
                    return jsonify({"error": "Flow rates are auto-controlled in auto mode"}), 400

            # Dispatch the command to the matching protocol-specific setter.
            if   command == HMIControl.estop:    written = self.set_estop(value)
            elif command == HMIControl.inflow:   written = self.set_inflow(value)
            elif command == HMIControl.outflow:  written = self.set_outflow(value)
            elif command == HMIControl.pswitch:  written = self.set_pumpSwitch(value)
            elif command == HMIControl.manualop: written = self.set_manualMode(value)
            else:
                logger.error(f"Unknown control {command}")
                return jsonify({"error": "Unknown control"}), 400

            # A client that reports the write failed must not be reported as sent.
            if written is False:
                logger.error(f"Device did not accept {command.value}={value}")
                return jsonify({"error": "The device did not accept the write"}), 502

            logger.info("Command sent")
            return jsonify({"success": "Command sent"}), 200

        except Exception as e:
            logger.error(f"Error: {e}")
            return jsonify({"error": str(e)}), 500

    def hmi_update_loop(self):
        """
        Run the client update loop that refreshes local HMI state.
        """
        ...

    def read_simulation_from_server(self):
        """
        Read simulation state from the protocol server into the local context.
        """
        ...

    def set_estop(self, value: bool) -> bool:
        """
        Update the emergency stop control to the provided value
        """
        ...

    def set_inflow(self, value: float) -> bool:
        """
        Update the inflow rate control to the provided value
        """
        ...

    def set_outflow(self, value: float) -> bool:
        """
        Update the outflow rate control to the provided value
        """
        ...

    def set_pumpSwitch(self, value: bool) -> bool:
        """
        Update the pump switch control to the provided value
        """
        ...

    def set_manualMode(self, value: bool) -> bool:
        """
        Set or unset manual operating mode to the provided value
        """
        ...


interface: HMIClientInterface

def load_hmi_interface(protocol: str) -> None:
    """
    Load and instantiate the HMI client implementation for a protocol.

    The implementation module is derived from the protocol and is expected to
    define a create_hmi_client() factory function.

    Args:
        protocol: The protocol name, e.g. "modbus".

    Raises:
        RuntimeError: If the module cannot be imported, or the required factory
            function is not defined.
    """
    # HMI client modules follow the naming pattern "simulator.<protocol>.<protocol>_hmi".
    # e.g., simulator.modbus.modbus_hmi
    module_name = f"simulator.{protocol.lower()}.{protocol.lower()}_hmi"
    try:
        # Import the configured HMI client module dynamically so the web layer
        # remains protocol-agnostic.
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise RuntimeError(f"Could not load HMI client module '{module_name}': {e}") from e

    try:
        # Each HMI module must provide a create_hmi_client() factory.
        create_hmi_client = getattr(module, "create_hmi_client")
    except AttributeError as e:
        raise RuntimeError(f"Module '{module_name}' does not define a create_hmi_client() function") from e

    global interface
    interface = create_hmi_client()



# Flask network configuration for the HMI frontend.
WEB_HOST = "0.0.0.0"
WEB_PORT = 8090

app: Flask = Flask(__name__, template_folder="ui/templates", static_folder="ui/static")
app.config["TITLE"] = "Aloha"

@app.route('/')
def index():
    return render_template('index.html', title=app.config["TITLE"])


@app.route('/update', methods=['GET'])
def update():
    """
    Return the current simulation state as JSON for the web UI.

    Boolean values are converted to 0 or 1 so the frontend can consume a simple
    numeric status model.
    """
    return jsonify({
        'emergencyStopStatus' : 1 if interface.simulation.estop else 0,
        'pumpSwitchStatus'    : 1 if interface.simulation.pswitch else 0,
        'pumpStatus'          : 1 if interface.simulation.pstatus else 0,
        'inflowValveStatus'   : 1 if interface.simulation.in_valve else 0,
        'outflowValveStatus'  : 1 if interface.simulation.out_valve else 0,
        'inflowMode'          : 1 if interface.simulation.manual_op else 0,
        'overflowed'          : 1 if interface.simulation.of_alarm else 0,
        'lowLevelAlarm'       : 1 if interface.simulation.ll_alarm else 0,
        'operatorErrorAlarm'  : 1 if interface.simulation.oe_alarm else 0,
        'tankVolume'          : int(interface.simulation.level),
        'inflowRate'          : int(interface.simulation.in_flow),
        'outflowRate'         : int(interface.simulation.out_flow),
        'maxVolume'           : TANK_MAX
    })


@app.route('/write', methods=['POST'])
def write() -> tuple[Response, int]:
    """
    Validate and process a control write request from the web UI.

    The request must contain JSON with both a control name and a value. Valid
    controls are converted to HMIControl values and then forwarded to the
    loaded HMI interface.

    Returns:
        A Flask response object, typically paired with an HTTP status code.
    """
    # Require JSON input for all write requests.
    if not request.is_json:
        logger.error("Expected JSON POST to /write")
        return jsonify({"error": "Expected JSON"}), 400

    # A valid JSON body that is not an object has no fields to read.
    if not isinstance(request.json, dict):
        logger.error("Expected a JSON object POST to /write")
        return jsonify({"error": "Expected a JSON object"}), 400

    # Validate that the target control was provided.
    control = request.json.get('control')
    if control is None:
        logger.error("Request is missing control field")
        return jsonify({"error": "Missing control parameter"}), 400

    # Validate that the new value was provided.
    value = request.json.get('value')
    if value is None:
        logger.error("Request is missing value parameter")
        return jsonify({"error": "Missing value parameter"}), 400

    try:
        # Convert the submitted control string into a known enum value before
        # dispatching the command to the protocol-specific client.
        control_command = HMIControl(control)
        return interface.send_command_to_server(control_command, value)
    except ValueError as e:
        pass  # StrEnum raises ValueError when an invalid control string is provided.
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

    # If we get to this point, it's an invalid control, since we return
    logger.error(f"Invalid control {control}")
    return jsonify({"error": "Invalid control"}), 400


def add_hmi_arguments(parser) -> None:
    """
    Add the HMI's own flags to the shared command line.
    """
    parser.add_argument("--web-port", type=int, default=WEB_PORT, metavar="PORT",
                        help=f"web HMI port (default: {WEB_PORT})")
    parser.add_argument("--client-cidr", type=int, metavar="PREFIX",
                        help="prefix length for the HMI's own BACnet address; match the PLC's subnet "
                             "(default: read from the interface, else 24)")


def main(argv: list[str] | None = None) -> int:
    """
    Parse the command line, connect to the PLC and serve the web HMI.

    Returns:
        The process exit status.
    """
    args = parse_args(
        prog="python -m simulator.hmi",
        description=f"{SIM['name']} HMI: polls the PLC over Modbus or BACnet and serves the web page.",
        host_help="PLC to poll (default: ALOHA_IP in the config, 127.0.0.1)",
        port_help="PLC port (default: ALOHA_PORT in the config, 5020 for Modbus, 47808 for BACnet)",
        default_host="127.0.0.1",
        extra=add_hmi_arguments,
        argv=argv)
    configure_logging(args.debug)
    if not args.debug:
        logging.getLogger("werkzeug").setLevel(logging.WARNING)

    try:
        load_hmi_interface(args.protocol)
    except RuntimeError as e:
        # Startup cannot continue without a valid HMI client implementation.
        logger.error(e)
        return 1

    try:
        server = make_server(WEB_HOST, args.web_port, app, threaded=True)
    except (OSError, SystemExit):
        logger.error(f"Could not serve the web HMI on {WEB_HOST}:{args.web_port}")
        return 1

    app.config["TITLE"] = f"{SIM['protocols'][args.protocol]['name']} - Aloha"

    # Initialize the protocol-specific client before starting the web server.
    logger.info(f"Polling PLC at {args.host}:{args.port}")
    interface.initialize_client(args.host, args.port, args.client_cidr)
    logger.info(f"Web HMI at http://{WEB_HOST}:{args.web_port}")

    signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    logger.info("Stopped")
    return 0


if __name__ == '__main__':
    sys.exit(main())
