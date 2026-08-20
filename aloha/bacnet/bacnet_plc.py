"""
Aloha Water Treatment Plant Control Logic
BACnet PLC implementation
"""

import asyncio
import logging
import signal
import os
import BAC0

from typing import Any

from BAC0.core.devices.local.factory import (
    analog_value, binary_value, binary_output
)

from aloha.constants import AlohaEnvVar
from aloha.plc.plc_simulation import simulation_step, SimulationContext
from aloha.plc.PLC import PLCProtocolInterface

# String keys used to store and access BACnet object references.
BAC_level    : str = 'tankLevel'
BAC_inflow   : str = 'inflowRate'
BAC_outflow  : str = 'outflowRate'
BAC_estop    : str = 'emergencyStop'
BAC_switch   : str = 'pumpSwitch'
BAC_manualop : str = 'manualMode'
BAC_pump     : str = 'pumpStatus'
BAC_invalve  : str = 'inflowValve'
BAC_outvalve : str = 'outflowValve'
BAC_OFalarm  : str = 'overflowAlarm'
BAC_LLalarm  : str = 'lowLevelAlarm'
BAC_OEalarm  : str = 'operatorErrorAlarm'

logger: logging.Logger = logging.getLogger(__name__)


class BacnetPLCInterface(PLCProtocolInterface):
    """
    BACnet-backed PLC implementation for the water treatment simulation.

    This class creates BACnet objects for process values, commands, and alarms,
    then keeps those objects synchronized with the shared simulation context.
    """
    # Shared runtime state used by the server loop.
    is_active: bool = True
    context: SimulationContext = SimulationContext()

    # BACnet network and device configuration.
    BACNET_DEVICE_ID: int = 1001
    BACNET_IP: str  = os.getenv(AlohaEnvVar.ip.value, "127.0.0.1/24")
    BACNET_PORT: int = int(os.getenv(AlohaEnvVar.port.value, 47808))

    # BACnet runtime objects initialized during startup.
    bacnet: BAC0.lite = None
    bacnet_objects: dict[str: Any]


    def setup_plc(self) -> None:
        """
        Placeholder for protocol setup.

        BACnet object creation is performed asynchronously in async_setup_plc(),
        so this synchronous setup hook is intentionally left empty.
        """
        pass

    def run_server(self) -> None:
        """
        Create an event loop and run the asynchronous BACnet server.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.run_server_async())
        except KeyboardInterrupt:
            logging.warning("User interrupted program execution")
        finally:
            # Cancel any remaining tasks so the loop can shut down cleanly.
            pending = asyncio.all_tasks(loop)

            for task in pending:
                task.cancel()
            try:
                loop.run_until_complete(asyncio.sleep(0.1))
            except:
                pass

            loop.close()

    def handle_signal(self, sig: int, frame: object | None) -> None:
        """
        Handle termination signals by stopping the main loop.

        Args:
            sig: The received signal number.
            frame: The current stack frame, if provided by the signal handler.
        """
        logger.info("Shutting down BACNET PLC")
        self.is_active = False

    async def async_setup_plc(self) -> None:
        """
        Create BACnet objects and register them with the BACnet application.
        """
        # Populate BACnet device metadata exposed to clients.
        self.bacnet.this_application.objectName       = "AlohaWaterTreatment"
        self.bacnet.this_application.vendorName       = "Aloha Water Treatment"
        self.bacnet.this_application.modelName        = "ATC-100-BAC"
        self.bacnet.this_application.firmwareRevision = "1.0.0"
        self.bacnet.this_application.description      = "Water Treatment Plant Controller [BACNET]"

        # Create the analog BACnet objects used for tank level and flow rates.
        tank_level = analog_value(name="TankLevel",
                                    instance=1,
                                    description="Treatment tank water level",
                                    presentValue=0,
                                    is_commandable=False
                                    )

        inflow_rate = analog_value(name="InflowRate",
                                    instance=2,
                                    description="Inlet flow rate",
                                    presentValue=0,
                                    is_commandable=True
                                    )

        outflow_rate = analog_value(name="OutflowRate",
                                    instance=3,
                                    description="Outlet flow rate",
                                    presentValue=0,
                                    is_commandable=True
                                    )

        # Create the binary BACnet values used for operator commands.
        emergency_stop = binary_value(name="EmergencyStop",
                                        instance=1,
                                        description="Emergency stop button",
                                        presentValue=False,
                                        is_commandable=True
                                        )

        pump_switch = binary_value(name="PumpSwitch",
                                    instance=2,
                                    description="Main pump switch",
                                    presentValue=False,
                                    is_commandable=True
                                    )

        manual_mode = binary_value(name="ManualMode",
                                    instance=3,
                                    description="Auto/Manual mode (False=Auto, True=Manual)",
                                    presentValue=False,
                                    is_commandable=True
                                    )

        # Create the binary outputs used for status and alarm indicators.
        pump_status = binary_output(name="PumpStatus",
                                    instance=1,
                                    description="Pump operational state",
                                    presentValue=False,
                                    is_commandable=False
                                    )

        inflow_valve = binary_output(name="InflowValve",
                                        instance=2,
                                        description="Inlet valve state",
                                        presentValue=False,
                                        is_commandable=False
                                        )

        outflow_valve = binary_output(name="OutflowValve",
                                        instance=3,
                                        description="Outlet valve state",
                                        presentValue=False,
                                        is_commandable=False
                                        )

        overflow_alarm = binary_output(name="OverflowAlarm",
                                        instance=4,
                                        description="High level alarm",
                                        presentValue=False,
                                        is_commandable=False
                                        )

        low_level_alarm = binary_output(name="LowLevelAlarm",
                                        instance=5,
                                        description="Low level alarm",
                                        presentValue=False,
                                        is_commandable=False
                                        )

        operator_error_alarm = binary_output(name="OperatorErrorAlarm",
                                                instance=6,
                                                description="Operator error / safety violation",
                                                presentValue=False,
                                                is_commandable=False
                                                )

        # Register all BACnet objects with the active BACnet application.
        tank_level.add_objects_to_application(self.bacnet)
        inflow_rate.add_objects_to_application(self.bacnet)
        outflow_rate.add_objects_to_application(self.bacnet)
        emergency_stop.add_objects_to_application(self.bacnet)
        pump_switch.add_objects_to_application(self.bacnet)
        manual_mode.add_objects_to_application(self.bacnet)
        pump_status.add_objects_to_application(self.bacnet)
        inflow_valve.add_objects_to_application(self.bacnet)
        outflow_valve.add_objects_to_application(self.bacnet)
        overflow_alarm.add_objects_to_application(self.bacnet)
        low_level_alarm.add_objects_to_application(self.bacnet)
        operator_error_alarm.add_objects_to_application(self.bacnet)

        # Store direct references to the created BACnet objects so the control
        # loop can read and write them by logical name.
        self.bacnet_objects = {
            BAC_level    : tank_level.objects["TankLevel"],
            BAC_inflow   : inflow_rate.objects["InflowRate"],
            BAC_outflow  : outflow_rate.objects["OutflowRate"],
            BAC_estop    : emergency_stop.objects["EmergencyStop"],
            BAC_switch   : pump_switch.objects["PumpSwitch"],
            BAC_manualop : manual_mode.objects["ManualMode"],
            BAC_pump     : pump_status.objects["PumpStatus"],
            BAC_invalve  : inflow_valve.objects["InflowValve"],
            BAC_outvalve : outflow_valve.objects["OutflowValve"],
            BAC_OFalarm  : overflow_alarm.objects["OverflowAlarm"],
            BAC_LLalarm  : low_level_alarm.objects["LowLevelAlarm"],
            BAC_OEalarm  : operator_error_alarm.objects["OperatorErrorAlarm"]
        }



    async def run_server_async(self) -> None:
        """
        Start the BACnet server and execute the asynchronous simulation loop.
        """
        # Register signal handlers so the loop can stop cleanly.
        signal.signal(signal.SIGINT,  self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        # Reduce BAC0 logging noise during normal operation.
        BAC0.log_level('silence')

        try:
            # Start the BACnet stack and bind to the configured device identity.
            self.bacnet = BAC0.start(
                ip      =self.BACNET_IP,
                deviceId=self.BACNET_DEVICE_ID
            )

            await self.async_setup_plc()

            logger.info(f"PLC running on BACnet device {self.BACNET_DEVICE_ID} at {self.BACNET_IP}")
            logger.info("Water Treatment Plant Control System Ready")

            while self.is_active:
                try:
                    # Synchronize BACnet inputs into the simulation, execute
                    # one simulation step, then write updated outputs back.
                    self.update_simulation_from_plc()
                    simulation_step(self.context)
                    self.update_plc_from_simulation()
                    await asyncio.sleep(1)

                except Exception as e:
                    logging.error(f"Error in control loop: {e}")
                    await asyncio.sleep(1)

            logger.info("Stopping BACnet server...")
            self.bacnet.disconnect()
        except asyncio.CancelledError:
            logger.warning("BACnet PLC shutting down")
        except Exception as e:
            logger.error(f"System error: {e}")
            if 'bacnet' in locals():
                try:
                    self.bacnet.disconnect()
                except:
                    pass

    def update_simulation_from_plc(self) -> None:
        """
        Copy BACnet object values into the shared simulation context.
        """
        # Read operator-controlled and externally visible values from the
        # BACnet objects into the protocol-neutral simulation context.
        self.context.estop     = self.bacnet_objects[BAC_estop].presentValue
        self.context.pswitch   = self.bacnet_objects[BAC_switch].presentValue
        #self.context.pstatus is determined within the simulation step logic
        #self.context.in_valve is determined within the simulation step logic
        #self.context.out_valve is determined within the simulation step logic
        self.context.manual_op = self.bacnet_objects[BAC_manualop].presentValue
        self.context.of_alarm  = self.bacnet_objects[BAC_OFalarm].presentValue
        #self.context.ll_alarm is set within the simulation step logic
        #self.context.oe_alarm is set within the simulation step logic

        self.context.level     = self.bacnet_objects[BAC_level].presentValue
        self.context.in_flow   = self.bacnet_objects[BAC_inflow].presentValue
        self.context.out_flow  = self.bacnet_objects[BAC_outflow].presentValue


    def update_plc_from_simulation(self) -> None:
        """
        Copy simulation values from the context back into BACnet objects.
        """
        # Write simulation-owned status and alarm values back to BACnet.
        # Commented assignments are for toggles controlled by the HMI
        #self.bacnet_objects[BAC_estop].presentValue = self.context.estop
        #self.bacnet_objects[BAC_swtich].presentValue = self.context.switch
        self.bacnet_objects[BAC_pump].presentValue = self.context.pstatus
        self.bacnet_objects[BAC_invalve].presentValue = self.context.in_valve
        self.bacnet_objects[BAC_outvalve].presentValue = self.context.out_valve
        #self.bacnet_objects[BAC_manualop].presentValue = self.context.auto_mode
        self.bacnet_objects[BAC_OFalarm].presentValue = self.context.of_alarm
        self.bacnet_objects[BAC_LLalarm].presentValue = self.context.ll_alarm
        self.bacnet_objects[BAC_OEalarm].presentValue = self.context.oe_alarm

        # Write the latest numeric process values back to BACnet.
        self.bacnet_objects[BAC_level].presentValue = int(self.context.level)
        self.bacnet_objects[BAC_inflow].presentValue =  int(self.context.in_flow)
        self.bacnet_objects[BAC_outflow].presentValue = int(self.context.out_flow)



def create_plc() -> PLCProtocolInterface:
    """
    Create and return the BACnet PLC implementation.
    """
    return BacnetPLCInterface()
