#!/usr/bin/env python3
"""
Aloha Water Treatment Plant PLC Simulation
Modbus TCP server for water treatment process control
"""

import signal
import sys
import os
import time
from threading import Thread, Event

from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusDeviceContext
from pymodbus import ModbusDeviceIdentification
from plc_logic import plc_logic

MODBUS_HOST = os.getenv("MODBUS_HOST", "0.0.0.0")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "5020"))
REGISTER_COUNT = 15
TANK_MAX = 10000
RATE_MIN = 50

INIT_LEVEL = 0
INIT_ESTOP = 0
INIT_SWITCH = 0
INIT_PUMP = 0
INIT_IN_VALVE = 0
INIT_OUT_VALVE = 0
INIT_IN_FLOW = 0
INIT_OUT_FLOW = 0
INIT_AUTO = 0
INIT_ALARM = 0

HR_BASE = 0
HR_TANK_LEVEL = 0
HR_EMERGENCY_STOP = 1
HR_PUMP_SWITCH = 2
HR_PUMP_STATUS = 3
HR_INFLOW_VALVE = 4
HR_OUTFLOW_VALVE = 5
HR_INFLOW_RATE = 6
HR_OUTFLOW_RATE = 7
HR_INFLOW_MODE = 8
HR_OVERFLOW_ALARM = 9

COIL_BASE = 0
COIL_EMERGENCY_STOP = 0
COIL_PUMP_SWITCH = 1
COIL_PUMP_STATUS = 2
COIL_INFLOW_VALVE = 3
COIL_OUTFLOW_VALVE = 4
COIL_INFLOW_MODE = 5
COIL_OVERFLOW_ALARM = 6
COIL_LOW_LEVEL_ALARM = 7
COIL_OPERATOR_ERROR_ALARM = 8

is_active = True
server_started = Event()


def setup_modbus_server():
    holding_register_values = [
        INIT_LEVEL, INIT_ESTOP, INIT_SWITCH, INIT_PUMP,
        INIT_IN_VALVE, INIT_OUT_VALVE, INIT_IN_FLOW, 
        INIT_OUT_FLOW, INIT_AUTO, INIT_ALARM
    ]
    
    coil_values = [
        INIT_ESTOP, INIT_SWITCH, INIT_PUMP,
        INIT_IN_VALVE, INIT_OUT_VALVE, INIT_AUTO, INIT_ALARM,
        0, 0
    ]
    
    holding_registers = ModbusSequentialDataBlock(
        0x00, 
        [0] + holding_register_values + [0] * (REGISTER_COUNT - len(holding_register_values))
    )
    
    coils = ModbusSequentialDataBlock(
        0x00, 
        [0] + coil_values + [0] * (REGISTER_COUNT - len(coil_values))
    )
    
    input_registers = ModbusSequentialDataBlock(0x00, [0] * REGISTER_COUNT)
    discrete_inputs = ModbusSequentialDataBlock(0x00, [0] * REGISTER_COUNT)

    device = ModbusDeviceIdentification()
    device.VendorName = "Aloha Water Treatment"
    device.ProductCode = "AWT-100"
    device.VendorUrl = "http://example.com"
    device.ProductName = "Aloha Treatment Controller"
    device.ModelName = "ATC-100"
    device.MajorMinorRevision = "1.0.0"

    device_context = ModbusDeviceContext(
        di=discrete_inputs,
        co=coils,
        hr=holding_registers,
        ir=input_registers
    )

    modbus_context = ModbusServerContext(devices=device_context, single=True)
    
    return modbus_context, device, discrete_inputs, coils, holding_registers, input_registers


def handle_signal(sig, frame):
    global is_active
    print("\nShutting down...")
    is_active = False
    sys.exit(0)


def run_modbus_server():
    global is_active
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    modbus_context, device, discrete_inputs, coils, holding_registers, input_registers = setup_modbus_server()

    server_thread = Thread(
        target=StartTcpServer,
        kwargs={
            'context': modbus_context,
            'identity': device,
            'address': (MODBUS_HOST, MODBUS_PORT),
        },
        daemon=True
    )
    server_thread.start()
    
    time.sleep(1)
    
    server_started.set()
    print(f"PLC running on port {MODBUS_PORT}")
    
    try:
        while is_active:
            try:
                discrete_inputs.setValues(0, discrete_inputs.getValues(0, REGISTER_COUNT + 1))
                coils.setValues(0, coils.getValues(0, REGISTER_COUNT + 1))
                holding_registers.setValues(0, holding_registers.getValues(0, REGISTER_COUNT + 1))
                input_registers.setValues(0, input_registers.getValues(0, REGISTER_COUNT + 1))

                plc_logic(discrete_inputs, coils, holding_registers, input_registers)
            except Exception as e:
                print(f"Error: {e}")
                
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    run_modbus_server()
