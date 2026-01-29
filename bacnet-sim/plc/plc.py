#!/usr/bin/env python3
"""
Aloha Water Treatment Plant PLC Simulation
BACnet server for water treatment process control
"""

import asyncio
import signal
import os
import BAC0
from BAC0.core.devices.local.factory import (
    analog_value, binary_value, binary_output
)
from plc_logic import plc_logic

BACNET_DEVICE_ID = 1001
BACNET_IP = os.getenv("BACNET_IP", "127.0.0.1/24")
TANK_MAX = 10000

is_active = True


def handle_signal(sig, frame):
    global is_active
    print("\nShutting down...")
    is_active = False


async def run_bacnet_plc():
    global is_active
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    BAC0.log_level('silence')
    
    try:
        bacnet = BAC0.start(
            ip=BACNET_IP,
            deviceId=BACNET_DEVICE_ID
        )
        
        bacnet.this_application.objectName = "AlohaWaterTreatment"
        bacnet.this_application.vendorName = "Aloha Water Treatment"
        bacnet.this_application.modelName = "ATC-100"
        bacnet.this_application.firmwareRevision = "1.0.0"
        bacnet.this_application.description = "Water Treatment Plant Controller"
        
        tank_level = analog_value(
            name="tankLevel",
            instance=1,
            description="Treatment tank water level",
            presentValue=0,
            is_commandable=False
        )
        inflow_rate = analog_value(
            name="inflowRate",
            instance=2,
            description="Inlet flow rate",
            presentValue=0,
            is_commandable=True
        )
        outflow_rate = analog_value(
            name="outflowRate",
            instance=3,
            description="Outlet flow rate",
            presentValue=0,
            is_commandable=True
        )
        emergency_stop = binary_value(
            name="emergencyStop",
            instance=1,
            description="Emergency stop button/status",
            presentValue=False,
            is_commandable=True
        )
        pump_switch = binary_value(
            name="pumpSwitch",
            instance=2,
            description="Main pump switch/status",
            presentValue=False,
            is_commandable=True
        )
        inflow_mode = binary_value(
            name="inflowMode",
            instance=3,
            description="Auto/manual mode (0=Auto, 1=Manual)",
            presentValue=False,
            is_commandable=True
        )
        pump_status = binary_output(
            name="pumpStatus",
            instance=1,
            description="Pump operational state",
            presentValue=False,
            is_commandable=False
        )
        inflow_valve = binary_output(
            name="inflowValve",
            instance=2,
            description="Inlet valve state/status",
            presentValue=False,
            is_commandable=False
        )
        outflow_valve = binary_output(
            name="outflowValve",
            instance=3,
            description="Outlet valve state/status",
            presentValue=False,
            is_commandable=False
        )
        overflow_alarm = binary_output(
            name="overflowAlarm",
            instance=4,
            description="High level alarm",
            presentValue=False,
            is_commandable=False
        )
        low_level_alarm = binary_output(
            name="lowLevelAlarm",
            instance=5,
            description="Low level alarm",
            presentValue=False,
            is_commandable=False
        )
        operator_error_alarm = binary_output(
            name="operatorErrorAlarm",
            instance=6,
            description="Operator error/safety violation",
            presentValue=False,
            is_commandable=False
        )
        
        tank_level.add_objects_to_application(bacnet)
        inflow_rate.add_objects_to_application(bacnet)
        outflow_rate.add_objects_to_application(bacnet)
        emergency_stop.add_objects_to_application(bacnet)
        pump_switch.add_objects_to_application(bacnet)
        auto_mode.add_objects_to_application(bacnet)
        pump_status.add_objects_to_application(bacnet)
        inflow_valve.add_objects_to_application(bacnet)
        outflow_valve.add_objects_to_application(bacnet)
        overflow_alarm.add_objects_to_application(bacnet)
        low_level_alarm.add_objects_to_application(bacnet)
        operator_error_alarm.add_objects_to_application(bacnet)
        
        bacnet_objects = {
            'tankLevel': tank_level.objects["tankLevel"],
            'inflowRate': inflow_rate.objects["inflowRate"],
            'outflowRate': outflow_rate.objects["outflowRate"],
            'emergencyStop': emergency_stop.objects["emergencyStop"],
            'pumpSwitch': pump_switch.objects["pumpSwitch"],
            'inflowMode': inflow_mode.objects["inflowMode"],
            'pumpStatus': pump_status.objects["pumpStatus"],
            'inflowValve': inflow_valve.objects["inflowValve"],
            'outflowValve': outflow_valve.objects["outflowValve"],
            'overflowAlarm': overflow_alarm.objects["overflowAlarm"],
            'lowLevelAlarm': low_level_alarm.objects["lowLevelAlarm"],
            'operatorErrorAlarm': operator_error_alarm.objects["operatorErrorAlarm"]
        }
        
        print(f"PLC running on BACnet device {BACNET_DEVICE_ID} at {BACNET_IP}")
        print("Water Treatment Plant Control System Ready")
        
        while is_active:
            try:
                plc_logic(bacnet_objects)
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Error in control loop: {e}")
                await asyncio.sleep(1)
        
        print("Stopping BACnet server...")
        bacnet.disconnect()
        
    except asyncio.CancelledError:
        print("BACnet PLC shutting down")
    except Exception as e:
        print(f"System error: {e}")
        if 'bacnet' in locals():
            try:
                bacnet.disconnect()
            except:
                pass


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(run_bacnet_plc())
    except KeyboardInterrupt:
        print("\nUser interrupted program execution")
    finally:
        pending = asyncio.all_tasks(loop)
        
        for task in pending:
            task.cancel()
        
        try:
            loop.run_until_complete(asyncio.sleep(0.1))
        except:
            pass
            
        loop.close()
