"""
Aloha Water Treatment Plant HMI
Flask web application for monitoring and controlling the treatment plant via BACnet
"""

import asyncio
import logging
import threading
import socket
import BAC0

from typing import Any

import simulator.bacnet.bacnet_plc as plc
from simulator.hmi import HMIClientInterface
from simulator.network import primary_ip, primary_prefix
from simulator.sim import SimulationContext

logger: logging.Logger = logging.getLogger(__name__)

WRITE_PRIORITY = 8

CLIENT_DEVICE_ID = 9101

POLL_INTERVAL = 1


class BACnetClient(HMIClientInterface):
    """
    BACnet-based HMI client implementation.

    This client maintains a local simulation snapshot for the web UI, sends
    operator commands to the BACnet PLC, and periodically polls BACnet objects
    to refresh displayed process state.
    """
    simulation: SimulationContext = SimulationContext()
    bacnet = None

    def initialize_client(self, host: str, port: int, client_cidr: int | None = None):
        """
        Initialize the BACnet client state and start the background update loop.

        Args:
            host: The BACnet PLC's address or hostname.
            port: The BACnet PLC's UDP port.
            client_cidr: Prefix length for the client's own BACnet address, or
                None to read it from the interface.
        """
        # BAC0's write parser only accepts a numeric address, so resolve a
        # hostname to its IP.
        self.host = host.split("/")[0]
        self.port = port
        ip = primary_ip()
        self.client_ip = f"{ip}/{client_cidr if client_cidr is not None else primary_prefix(ip)}"
        self._resolve_device()
        self.bacnet = None
        self.loop = None

        if not logging.getLogger().isEnabledFor(logging.DEBUG):
            BAC0.log_level('silence')
            logging.getLogger('bacpypes3').setLevel(logging.CRITICAL)
        logging.getLogger("BAC0_Root").propagate = False

        # Start a background thread that owns the async BACnet polling loop.
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.hmi_update_loop, daemon=True)
        self.thread.start()

    def _resolve_device(self):
        """
        Look up the BACnet PLC's current IP from its hostname.
        """
        try:
            ip = socket.gethostbyname(self.host)
        except socket.gaierror:
            ip = self.host
        self.device_ip = ip if self.port == 47808 else f"{ip}:{self.port}"

    def set_estop(self, value: bool) -> bool:
        """
        Set the emergency stop bit to the given value
        """
        return self._write_to_server(*plc.OBJ_ESTOP,
                                     write_value='active' if value else 'inactive')

    def set_inflow(self, value: float) -> bool:
        """
        Write the inflow rate to the BACnet server.
        """
        return self._write_to_server(*plc.OBJ_INFLOW,
                                     write_value=int(value))

    def set_outflow(self, value: float) -> bool:
        """
        Write the outflow rate to the BACnet server.
        """
        return self._write_to_server(*plc.OBJ_OUTFLOW,
                                     write_value=int(value))

    def set_pumpSwitch(self, value: bool) -> bool:
        """
        Set the pump switch bit to the given value.
        """
        return self._write_to_server(*plc.OBJ_SWITCH,
                                     write_value='active' if value else 'inactive')

    def set_manualMode(self, value: bool) -> bool:
        """
        Set the manual mode bit to the given value
        """
        return self._write_to_server(*plc.OBJ_MANUAL,
                                     write_value='active' if value else 'inactive')

    def _write_to_server(self, obj_type: str, instance: int, write_value: Any):
        """
        Submit a BACnet write request onto the background event loop.

        The write is scheduled thread-safely because HMI requests originate
        outside the async polling loop.
        """
        with self.lock:
            future = asyncio.run_coroutine_threadsafe(
                self._write_value_wrapper(obj_type, instance, 'presentValue', write_value),
                self.loop
            )
            return future.result(timeout=5.0)

    async def _write_value_wrapper(self, obj_type: str, instance: int, prop: str, value: Any, priority=WRITE_PRIORITY):
        """
        Execute a BACnet write command for a specific object property.

        Args:
            obj_type: BACnet object type name.
            instance: BACnet object instance number.
            prop: BACnet property name to write.
            value: Value to write.
            priority: BACnet write priority.
        """
        try:
            # BAC0 expects writes as formatted command strings.
            command = f'{self.device_ip} {obj_type} {instance} {prop} {value} - {priority}'
            await self.bacnet._write(command)
            return True
        except Exception as e:
            logger.error(f"Error writing {obj_type} {instance}: {e}")
            return False

    def hmi_update_loop(self):
        """
        Start the asynchronous BACnet polling loop in this thread.
        """
        asyncio.run(self.async_hmi_update_loop())

    def read_simulation_from_server(self):
        """
        Trigger a one-time refresh of BACnet values into the local context.
        """
        asyncio.run(self._read_all())

    async def async_hmi_update_loop(self):
        """
        Maintain the BACnet connection and periodically refresh HMI state.
        """
        # Store the event loop so write requests from other threads can submit
        # coroutines to it safely.
        self.loop = asyncio.get_event_loop()

        while True:
            try:
                if self.bacnet is None:
                    try:
                        # Connect lazily so the loop can retry if the BACnet
                        # server is not yet available.
                        self.bacnet = BAC0.lite(ip=self.client_ip, deviceId=CLIENT_DEVICE_ID, ping=False)
                        await asyncio.sleep(2)
                    except Exception as e:
                        await asyncio.sleep(5)
                        continue

                self._resolve_device()
                await self._read_all()
                await asyncio.sleep(POLL_INTERVAL)

            except Exception as e:
                logger.error(f"Error in BACnet cycle: {e}")
                await asyncio.sleep(POLL_INTERVAL)


    async def _read_all(self):
        """
        Read all relevant BACnet objects and update the local simulation context.
        """
        if self.bacnet is None:
            return

        async def _read_value(obj_type: str, instance: int, prop: str):
            """
            Read a single BACnet property value.

            Args:
                obj_type: BACnet object type name.
                instance: BACnet object instance number.
                prop: BACnet property name to read.
            """
            try:
                command = f'{self.device_ip} {obj_type} {instance} {prop}'
                logger.debug(command)
                task = asyncio.create_task(self.bacnet.read(command))
                value = await asyncio.wait_for(task, timeout=10.0)
                return value
            except Exception:
                return None

        try:
            # Read all required process, command, status, and alarm values in
            # parallel to reduce total polling latency.
            tasks = [
                _read_value(*plc.OBJ_LEVEL, 'presentValue'),    # simulation.level
                _read_value(*plc.OBJ_INFLOW, 'presentValue'),   # simulation.in_flow
                _read_value(*plc.OBJ_OUTFLOW, 'presentValue'),  # simulation.out_flow
                _read_value(*plc.OBJ_ESTOP, 'presentValue'),    # simulation.estop
                _read_value(*plc.OBJ_SWITCH, 'presentValue'),   # simulation.pswitch
                _read_value(*plc.OBJ_MANUAL, 'presentValue'),   # simulation.manual_op
                _read_value(*plc.OBJ_PUMP, 'presentValue'),     # simulation.pstatus
                _read_value(*plc.OBJ_INVALVE, 'presentValue'),  # simulation.in_valve
                _read_value(*plc.OBJ_OUTVALVE, 'presentValue'), # simulation.out_valve
                _read_value(*plc.OBJ_OFALARM, 'presentValue'),  # simulation.of_alarm
                _read_value(*plc.OBJ_LLALARM, 'presentValue'),  # simulation.ll_alarm
                _read_value(*plc.OBJ_OEALARM, 'presentValue'),  # simulation.oe_alarm
            ]

            # Convert the returned BACnet values into the local simulation model.
            # Binary values are represented as the strings 'active'/'inactive'.
            results = await asyncio.gather(*tasks, return_exceptions=True)

            self.simulation.level     = int(results[0]) if results[0] is not None else 0
            self.simulation.in_flow   = int(results[1]) if results[1] is not None else 0
            self.simulation.out_flow  = int(results[2]) if results[2] is not None else 0
            self.simulation.estop     = True if str(results[3])  == 'active' else False
            self.simulation.pswitch   = True if str(results[4])  == 'active' else False
            self.simulation.manual_op = True if str(results[5])  == 'active' else False
            self.simulation.pstatus   = True if str(results[6])  == 'active' else False
            self.simulation.in_valve  = True if str(results[7])  == 'active' else False
            self.simulation.out_valve = True if str(results[8])  == 'active' else False
            self.simulation.of_alarm  = True if str(results[9])  == 'active' else False
            self.simulation.ll_alarm  = True if str(results[10]) == 'active' else False
            self.simulation.oe_alarm  = True if str(results[11]) == 'active' else False

        except Exception as e:
            logger.error(f"Error reading BACnet data: {e}")

    def __del__(self):
        """
        Disconnect from BACnet during object cleanup.
        """
        if self.bacnet is not None:
            try:
                asyncio.run(self.bacnet.disconnect())
            except:
                pass

def create_hmi_client() -> HMIClientInterface:
    return BACnetClient()
