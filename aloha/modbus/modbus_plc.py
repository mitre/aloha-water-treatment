"""
Aloha Water Treatment Plant Control Logic
Modbus PLC implementation
"""

import logging
import os
import signal
import time

from threading import Thread, Event

from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusDeviceContext
from pymodbus import ModbusDeviceIdentification

from aloha.plc.PLC import PLCProtocolInterface
from aloha.plc.plc_simulation import simulation_step, SimulationContext



# Initial values loaded into the simulated PLC data store at startup.
# These define the default state for registers and coils before the
# server begins accepting client connections.
INIT_LEVEL     = 0
INIT_ESTOP     = 0
INIT_POWER     = 0
INIT_PUMPING   = 0
INIT_IN_VALVE  = 0
INIT_OUT_VALVE = 0
INIT_IN_FLOW   = 0
INIT_OUT_FLOW  = 0
INIT_MANUAL    = 0
INIT_ALARM     = 0

# Holding register offsets used by the simulation.
# These constants map semantic field names to Modbus register positions.
HR_BASE      = 0
HR_LEVEL     = 0
HR_ESTOP     = 1
HR_POWER     = 2
HR_PUMPING   = 3
HR_IN_VALVE  = 4
HR_OUT_VALVE = 5
HR_IN_FLOW   = 6
HR_OUT_FLOW  = 7
HR_MANUAL    = 8
HR_ALARM     = 9

# Coil offsets used by the simulation.
# Coils primarily represent boolean control and alarm states.
COIL_BASE                 = 0
COIL_ESTOP                = 0
COIL_POWER                = 1
COIL_PUMPING              = 2
COIL_IN_VALVE             = 3
COIL_OUT_VALVE            = 4
COIL_MANUAL               = 5
COIL_OFLOW_ALARM          = 6
COIL_LOW_LEVEL_ALARM      = 7
COIL_OPERATOR_ERROR_ALARM = 8

logger: logging.Logger = logging.getLogger(__name__)


class ModbusPLCInterface(PLCProtocolInterface):
    """
    Modbus-backed PLC simulation interface.

    This class initializes a Modbus TCP server, maintains the backing
    data blocks for registers and coils, and synchronizes PLC state with
    the simulation context on a periodic loop.
    """
    server_started    : Event = Event()
    context           : SimulationContext = SimulationContext()
    is_active         : bool = True

    holding_registers : ModbusSequentialDataBlock
    coils             : ModbusSequentialDataBlock
    input_registers   : ModbusSequentialDataBlock
    discrete_inputs   : ModbusSequentialDataBlock
    device            : ModbusDeviceIdentification
    device_context    : ModbusDeviceContext
    server_context    : ModbusServerContext

    # Important variables
    MODBUS_HOST = os.getenv("ALOHA_IP", "0.0.0.0")
    MODBUS_PORT = int(os.getenv("ALOHA_PORT", "5020"))
    REGISTER_COUNT: int = 15

    def setup_plc(self) -> None:
        """
        Initialize Modbus data blocks, device identity, and server context.

        The datastore is intentionally created with a leading placeholder
        value because the rest of the implementation reads and writes most
        registers and coils using 1-based offsets.
        """

        holding_register_values = [
            INIT_LEVEL,
            INIT_ESTOP,
            INIT_POWER,
            INIT_PUMPING,
            INIT_IN_VALVE,
            INIT_OUT_VALVE,
            INIT_IN_FLOW,
            INIT_OUT_FLOW,
            INIT_MANUAL,
            INIT_ALARM]
        coil_values = [
            INIT_ESTOP,
            INIT_POWER,
            INIT_PUMPING,
            INIT_IN_VALVE,
            INIT_OUT_VALVE,
            INIT_MANUAL,
            INIT_ALARM,
            0, 0]


        # A leading zero is included so later reads/writes using index + 1
        # align with the logical register constants defined above.
        self.holding_registers = ModbusSequentialDataBlock(
            0x00,
            [0] + holding_register_values + [0] * (self.REGISTER_COUNT - len(holding_register_values))
        )

        self.coils = ModbusSequentialDataBlock(
            0x00,
            [0] + coil_values + [0] * (self.REGISTER_COUNT - len(coil_values))
        )

        # Input registers and discrete inputs are initialized but not
        # currently populated with simulation-specific values at startup.
        self.input_registers = ModbusSequentialDataBlock(0x00, [0] * self.REGISTER_COUNT)
        self.discrete_inputs = ModbusSequentialDataBlock(0x00, [0] * self.REGISTER_COUNT)

        # Modbus device identification exposed to clients.
        self.device = ModbusDeviceIdentification()
        self.device.VendorName         = "Aloha Water Treatment"
        self.device.ProductCode        = "AWT-100-MOD"
        self.device.VendorUrl          = "http://example.com"
        self.device.ProductName        = "Aloha Treatment Controller"
        self.device.ModelName          = "ATC-100"
        self.device.MajorMinorRevision = "1.1.0"

        # Assemble the per-device context from the individual data blocks.
        self.device_context = ModbusDeviceContext(
            di = self.discrete_inputs,
            co = self.coils,
            hr = self.holding_registers,
            ir = self.input_registers
        )

        # Create the server context in single-device mode.
        self.modbus_context = ModbusServerContext(devices=self.device_context, single=True)

    def run_server(self) -> None:
        """
        Start the Modbus TCP server and run the simulation update loop.

        The Modbus server runs in a daemon thread while the main loop
        repeatedly synchronizes PLC state with the simulation context.
        """

        self.setup_plc()

        # Register shutdown handlers so the loop can stop gracefully.
        signal.signal(signal.SIGINT,  self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        # Start the Modbus TCP server in a background thread so the main
        # thread can continue running the simulation loop.
        server_thread = Thread(
            target=StartTcpServer,
            kwargs={
                'context' : self.modbus_context,
                'identity': self.device,
                'address' : (self.MODBUS_HOST, self.MODBUS_PORT),
            },
            daemon=True
        )
        # Allow the server a brief moment to initialize before signaling
        # readiness to other parts of the application.
        server_thread.start()
        time.sleep(1)

        self.server_started.set()
        logger.info(f"PLC running on port {self.MODBUS_PORT}")

        try:
            while self.is_active:
                try:
                    # Pull operator/client inputs from the PLC datastore,
                    # run one simulation cycle, then publish outputs back.
                    self.update_simulation_from_plc()
                    simulation_step(self.context)
                    self.update_plc_from_simulation()
                except Exception as e:
                    logger.error(f"Error: {e}")

                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nStopped by keyboard interrupt")

    def handle_signal(self, sig: int, frame: object | None) -> None:
        """
        Handle process termination signals by stopping the main loop.

        Args:
            sig: The received signal number.
            frame: The current stack frame, if provided by the signal handler.
        """
        logger.info("Shutting down...")
        self.is_active = False


    def update_simulation_from_plc(self) -> None:
        """
        Read PLC values from the Modbus datastore into the simulation context.

        This method copies operator-controlled values from holding registers
        and coils into the simulation context. Coil values are treated as the
        authoritative source for selected HMI-driven boolean controls.
        """
        # Refresh all data blocks from their current values. This keeps access
        # patterns consistent across the simulation loop, even though these
        # calls effectively rewrite each block with its existing contents.
        self.discrete_inputs.setValues(0, self.discrete_inputs.getValues(0, self.REGISTER_COUNT + 1))
        self.coils.setValues(0, self.coils.getValues(0, self.REGISTER_COUNT + 1))
        self.holding_registers.setValues(0, self.holding_registers.getValues(0, self.REGISTER_COUNT + 1))
        self.input_registers.setValues(0,   self.input_registers.getValues(0, self.REGISTER_COUNT + 1))

        # Read holding registers starting at address 1 to match the
        # 1-based indexing convention used throughout this class.
        hr_values = self.holding_registers.getValues(1, self.REGISTER_COUNT)

        # Transfer client-visible PLC state into the simulation context.
        self.context.estop     = hr_values[HR_ESTOP]
        self.context.pswitch   = hr_values[HR_POWER]
        #self.context.pstatus is set within the simulation step logic
        self.context.in_valve  = hr_values[HR_IN_VALVE]
        self.context.out_valve = hr_values[HR_OUT_VALVE]
        self.context.manual_op = hr_values[HR_MANUAL]
        self.context.of_alarm  = hr_values[HR_ALARM]
        #self.context.ll_alarm is set within the simulation step logic
        #self.context.oe_alarm is set within the simulation step logic

        self.context.level     = hr_values[HR_LEVEL]
        self.context.in_flow   = hr_values[HR_IN_FLOW]
        self.context.out_flow  = hr_values[HR_OUT_FLOW]

        # Read coil values separately because some HMI toggles are modeled
        # there and should override matching holding register values.
        coil_values = self.coils.getValues(1, 10)
        coil_estop_value  = coil_values[COIL_ESTOP]
        coil_switch_value = coil_values[COIL_POWER]
        coil_auto_value   = coil_values[COIL_MANUAL]

        if self.context.estop != coil_estop_value:
            self.holding_registers.setValues(HR_ESTOP + 1, [coil_estop_value])
            self.context.estop = coil_estop_value

        if self.context.pswitch != coil_switch_value:
            self.holding_registers.setValues(HR_POWER + 1, [coil_switch_value])
            self.context.pswitch = coil_switch_value

        if self.context.manual_op != coil_auto_value:
            self.holding_registers.setValues(HR_MANUAL + 1, [coil_auto_value])
            self.context.manual_op = coil_auto_value

    def update_plc_from_simulation(self) -> None:
        """
        Write simulation state back into the PLC Modbus datastore.

        Only values owned by the simulation are written here. HMI-controlled
        values remain commented out to avoid overwriting operator inputs.
        """

        # Publish process state into holding registers.
        # Commented lines are controlled by the HMI and are listed for context.
        self.holding_registers.setValues(HR_LEVEL + 1,      [self.context.level])
        # self.holding_registers.setValues(HR_ESTOP + 1,      [self.context.estop])
        # self.holding_registers.setValues(HR_SWITCH + 1,     [self.context.switch])
        self.holding_registers.setValues(HR_PUMPING + 1,       [self.context.pstatus])
        self.holding_registers.setValues(HR_IN_VALVE + 1,   [self.context.in_valve])
        self.holding_registers.setValues(HR_OUT_VALVE + 1,  [self.context.out_valve])
        self.holding_registers.setValues(HR_IN_FLOW + 1,    [self.context.in_flow])
        self.holding_registers.setValues(HR_OUT_FLOW + 1,   [self.context.out_flow])
        self.holding_registers.setValues(HR_MANUAL + 1,       [self.context.manual_op])
        self.holding_registers.setValues(HR_ALARM + 1,      [self.context.of_alarm])

        # Publish process state and alarm outputs into coils.
        # Commented lines are controlled by the HMI and are listed for context.
        # self.coils.setValues(COIL_ESTOP + 1,                [self.context.estop])
        # self.coils.setValues(COIL_SWITCH + 1,               [self.context.switch])
        self.coils.setValues(COIL_PUMPING + 1,              [self.context.pstatus])
        self.coils.setValues(COIL_IN_VALVE + 1,             [self.context.in_valve])
        self.coils.setValues(COIL_OUT_VALVE + 1,            [self.context.out_valve])
        # self.coils.setValues(COIL_AUTO + 1,                 [self.context.auto_mode])
        self.coils.setValues(COIL_OFLOW_ALARM + 1,          [self.context.of_alarm])
        self.coils.setValues(COIL_LOW_LEVEL_ALARM + 1,      [self.context.ll_alarm])
        self.coils.setValues(COIL_OPERATOR_ERROR_ALARM + 1, [self.context.oe_alarm])



def create_plc() -> PLCProtocolInterface:
    """
    Create and return a Modbus PLC interface implementation for the generic sim.
    """
    return ModbusPLCInterface()
