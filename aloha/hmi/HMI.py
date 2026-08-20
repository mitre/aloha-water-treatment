"""
Aloha Water Treatment Plant HMI
Flask web application for monitoring and controlling the treatment plant
"""


import importlib
import logging
import os

from enum import StrEnum
from flask import Flask, render_template, request, jsonify, Response
from typing import Protocol, runtime_checkable

from aloha.constants import configure_logging, AlohaEnvVar
from aloha.plc.plc_simulation import SimulationContext, TANK_MAX

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


    def initialize_client(self):
        """
        Initialize the HMI client and any protocol-specific resources.
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
            if   command == HMIControl.estop:    self.set_estop(value)
            elif command == HMIControl.inflow:   self.set_inflow(value)
            elif command == HMIControl.outflow:  self.set_outflow(value)
            elif command == HMIControl.pswitch:  self.set_pumpSwitch(value)
            elif command == HMIControl.manualop: self.set_manualMode(value)
            else:
                logger.error(f"Unknown control {command}")
                return jsonify({"error": "Unknown control"}), 400

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

def load_hmi_interface() -> None:
    """
    Load and instantiate the configured HMI client implementation.

    The implementation module is derived from the configured protocol value and
    is expected to define a create_hmi_client() factory function.

    Returns:
        The configured HMI client interface type as declared by the function
        signature.

    Raises:
        RuntimeError: If the protocol is missing, the module cannot be imported,
            or the required factory function is not defined.
    """
    # Read the configured protocol name from the environment.
    protocol_name = os.getenv(AlohaEnvVar.protocol.value)
    if not protocol_name: raise RuntimeError(f"{AlohaEnvVar.protocol.value} is not set")

    # HMI client modules follow the naming pattern "aloha.<protocol>.<protocol>_hmi".
    # e.g., aloha.modbus.modbus_hmi
    module_name = f"aloha.{protocol_name.lower()}.{protocol_name.lower()}_hmi"
    try:
        # Import the configured HMI client module dynamically so the web layer
        # remains protocol-agnostic.
        module = importlib.import_module(f"{module_name}")
    except ImportError as e:
        msg = f"Could not load HMI client module '{module_name}'"
        logger.error(msg)
        raise RuntimeError(msg) from e

    try:
        # Each HMI module must provide a create_hmi_client() factory.
        create_hmi_client = getattr(module, "create_hmi_client")
    except AttributeError as e:
        msg = f"Module '{module_name}' does not define a create_hmi_client() function"
        logger.error(msg)
        raise RuntimeError(f"Module '{module_name}' does not define a create_hmi_client() function") from e

    global interface
    interface = create_hmi_client()

    # Runtime interface validation is intentionally disabled here.
    #if not isinstance(plc, PLCProtocolInterface):
    #    raise TypeError(f"{module_name}.create_plc() does not return a PLCProtocolInterface")



# Flask network configuration for the HMI frontend.
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 8090

app: Flask = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')


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
        logging.error("Expected JSON POST to /write")
        return jsonify({"error": "Expected JSON"}), 400

    # Validate that the target control was provided.
    control = request.json.get('control')
    if control is None:
        logging.error(f"Request is missing control field")
        return jsonify({"error": "Missing control parameter"}), 400

    # Validate that the new value was provided.
    value = request.json.get('value')
    if value is None:
        logging.error(f"Request is missing value parameter")
        return jsonify({"error": "Missing value parameter"}), 400

    try:
        # Convert the submitted control string into a known enum value before
        # dispatching the command to the protocol-specific client.
        control_command = HMIControl(control)
        return interface.send_command_to_server(control_command, value)
    except ValueError as e:
        pass  # StrEnum raises ValueError when an invalid control string is provided.
    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

    # If we get to this point, it's an invalid control, since we return
    logging.error(f"Invalid control {control}")
    return jsonify({"error": "Invalid control"}), 400


if __name__ == '__main__':
    configure_logging()
    try:
        load_hmi_interface()
    except RuntimeError as e:
    # Startup cannot continue without a valid HMI client implementation.
        logger.critical(f"Unable to load HMI interface, exiting")
        exit(1)

    # Initialize the protocol-specific client before starting the web server.
    interface.initialize_client()
    app.run(host=FLASK_HOST, port=FLASK_PORT)
