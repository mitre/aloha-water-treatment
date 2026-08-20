import logging
import threading
import time
import os

import aloha.modbus.modbus_plc as plc
from aloha.constants import AlohaEnvVar
from aloha.hmi.HMI import HMIClientInterface
from aloha.plc.plc_simulation import SimulationContext


from pymodbus.client import ModbusTcpClient

REGISTER_COUNT = 10

logger: logging.Logger = logging.getLogger(__name__)

class ModbusClient(HMIClientInterface):
    """
    Modbus-based HMI client implementation.

    This client connects to the Modbus PLC server, periodically reads process
    state into a local SimulationContext, and sends user-issued HMI commands
    back to the PLC.
    """
    # Local cached simulation state used by the web HMI.
    simulation: SimulationContext = SimulationContext()

    def initialize_client(self):
        """
        Initialize the Modbus TCP client connection and start the update loop.
        """
        server_ip  : str = os.getenv(AlohaEnvVar.ip.value, "127.0.0.1")
        server_port: int = int(os.getenv(AlohaEnvVar.port.value, "5020"))

        self.client = ModbusTcpClient(host=server_ip, port=server_port)
        self.client.connect()

        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.hmi_update_loop, daemon=True)
        self.thread.start()

    def set_estop(self, value: bool) -> bool:
        """
        Write the emergency stop command to both register and coil space.
        """
        logger.info(f"Sending command to toggle estop {"on" if value else "off"}")
        result = self.client.write_register(plc.HR_ESTOP, value, device_id=1)
        logger.debug(f"Write register result: {result}")
        result = self.client.write_coil(plc.COIL_ESTOP, bool(value), device_id=1)
        logger.debug(f"Write coil result: {result}")

    def set_inflow(self, value: float) -> bool:
        """
        Write the inflow rate command to the holding register space.
        """
        logger.info(f"Sending command to set inflow to {value}")
        result = self.client.write_register(plc.HR_IN_FLOW, int(value), device_id=1)
        logger.debug(f"Write register result: {result}")

    def set_outflow(self, value: float) -> bool:
        """
        Write the outflow rate command to the holding register space.
        """
        logger.info(f"Sending command to set outflow to {value}")
        result = self.client.write_register(plc.HR_OUT_FLOW, int(value), device_id=1)
        logger.debug(f"Write register result: {result}")

    def set_pumpSwitch(self, value: bool) -> bool:
        """
        Write the outflow rate command to the holding register space.
        """
        logger.info(f"Sending command to toggle pump {"on" if value else "off"}")
        result = self.client.write_register(plc.HR_POWER, value, device_id=1)
        logger.debug(f"Write register result: {result}")
        result = self.client.write_coil(plc.COIL_POWER, bool(value), device_id=1)
        logger.debug(f"Write coil result: {result}")

    def set_manualMode(self, value: bool) -> bool:
        """
        Write the operating mode command to both register and coil space.
        """
        logger.info(f"Sending command to toggle operating mode to {"manual" if value else "auto"}")
        result = self.client.write_register(plc.HR_MANUAL, value, device_id=1)
        logger.debug(f"Write register result: {result}")
        result = self.client.write_coil(plc.COIL_MANUAL, bool(value), device_id=1)
        logger.debug(f"Write coil result: {result}")


    def hmi_update_loop(self):
        """
        Continuously poll the PLC and refresh the local simulation snapshot.
        """
        while True:
            logger.debug(f"Pre-{self.simulation}")
            self.read_simulation_from_server()
            time.sleep(1)

    def read_simulation_from_server(self):
        """
        Read Modbus coil and holding register data into the local simulation context.
        """
        try:
            # Read coil values first
            coil_response = self.client.read_coils(plc.COIL_BASE, count=10)
            if not coil_response.isError():
                coil_values = coil_response.bits
                self.simulation.estop     = bool(coil_values[plc.COIL_ESTOP]) if coil_values[plc.COIL_ESTOP] is not None else None
                self.simulation.pswitch   = bool(coil_values[plc.COIL_POWER]) if coil_values[plc.COIL_POWER] is not None else None
                self.simulation.pstatus   = bool(coil_values[plc.COIL_PUMPING]) if coil_values[plc.COIL_PUMPING] is not None else None
                self.simulation.in_valve  = bool(coil_values[plc.COIL_IN_VALVE]) if coil_values[plc.COIL_IN_VALVE] is not None else None
                self.simulation.out_valve = bool(coil_values[plc.COIL_OUT_VALVE]) if coil_values[plc.COIL_OUT_VALVE] is not None else None
                self.simulation.manual_op = bool(coil_values[plc.COIL_MANUAL]) if coil_values[plc.COIL_MANUAL] is not None else None
                self.simulation.of_alarm  = bool(coil_values[plc.COIL_OFLOW_ALARM]) if coil_values[plc.COIL_OFLOW_ALARM] is not None else None
                self.simulation.ll_alarm  = bool(coil_values[plc.COIL_LOW_LEVEL_ALARM]) if coil_values[plc.COIL_LOW_LEVEL_ALARM] is not None else None
                self.simulation.oe_alarm  = bool(coil_values[plc.COIL_OPERATOR_ERROR_ALARM]) if coil_values[plc.COIL_OPERATOR_ERROR_ALARM] is not None else None
        except Exception as e :
            logger.error(f"Error reading coils: {e}")

        try:
            # Read holding registers for numeric process values. Some boolean
            # values also exist here, but those updates are intentionally left
            # disabled below because the coil reads already provide them.
            hr_response = self.client.read_holding_registers(plc.HR_BASE, count=REGISTER_COUNT)
            if not hr_response.isError():
                hr_values = hr_response.registers
                self.simulation.level     = int(hr_values[plc.HR_LEVEL])
                self.simulation.in_flow   = float(hr_values[plc.HR_IN_FLOW])
                self.simulation.out_flow  = float(hr_values[plc.HR_OUT_FLOW])

                # The following values are duplicated in holding registers by coils
                #self.simulation.estop     = hr_values[plc.HR_ESTOP]
                #self.simulation.pswitch   = hr_values[plc.HR_SWITCH]
                #self.simulation.pstatus   = hr_values[plc.HR_PUMP]
                #self.simulation.in_valve  = hr_values[plc.HR_IN_VALVE]
                #self.simulation.out_valve = hr_values[plc.HR_OUT_VALVE]
                #self.simulation.auto_mode = hr_values[plc.HR_AUTO]
                #self.simulation.of_alarm  = hr_values[plc.HR_ALARM]
        except Exception as e:
            logger.error(f"Error reading registers: {e}")

    def __del__(self):
        """
        Close the Modbus client connection during object cleanup.
        """
        if self.client is not None:
            self.client.close()
            self.client = None


def create_hmi_client() -> HMIClientInterface:
    """
    Create and return the Modbus HMI client implementation.
    """
    return ModbusClient()
