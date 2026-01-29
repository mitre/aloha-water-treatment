"""
Aloha Water Treatment Plant HMI
Flask web application for monitoring and controlling the treatment plant
"""

import threading
import time
import os

from flask import Flask, render_template, request, jsonify
from pymodbus.client import ModbusTcpClient

FLASK_HOST = "0.0.0.0"
FLASK_PORT = 8090
MODBUS_HOST = os.getenv("MODBUS_HOST", "127.0.0.1")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "5020"))
REGISTER_COUNT = 10
TANK_MAX = 10000

COIL_BASE = 0
COIL_ESTOP = 0
COIL_SWITCH = 1
COIL_PUMP = 2
COIL_IN_VALVE = 3
COIL_OUT_VALVE = 4
COIL_AUTO = 5
COIL_ALARM = 6
COIL_LOW_LEVEL_ALARM = 7
COIL_OPERATOR_ERROR_ALARM = 8

HR_BASE = 0
HR_LEVEL = 0
HR_ESTOP = 1
HR_SWITCH = 2
HR_PUMP = 3
HR_IN_VALVE = 4
HR_OUT_VALVE = 5
HR_IN_FLOW = 6
HR_OUT_FLOW = 7
HR_AUTO = 8
HR_ALARM = 9


class ModbusClient:
    def __init__(self, server_ip, server_port):
        self.client = ModbusTcpClient(host=server_ip, port=server_port)
        self.client.connect()
        
        self.thread = threading.Thread(target=self._read_data, daemon=True)
        self.thread.start()

        self.data = {
            'emergency_stop_status': None,
            'pump_switch_status': None,
            'pump_status': None,
            'inflow_valve_status': None,
            'outflow_valve_status': None,
            'overflowed': None,
            'inflow_mode': None,
            'tank_volume': None,
            'max_volume': TANK_MAX,
            'inflow_rate': None,
            'outflow_rate': None,
            'low_level_alarm': None,
            'operator_error_alarm': None
        }

    def _read_data(self):
        while True:
            try:
                coil_response = self.client.read_coils(COIL_BASE, count=10)
                if not coil_response.isError():
                    coil_values = coil_response.bits
                    self.data['emergency_stop_status'] = int(coil_values[COIL_ESTOP]) if coil_values[COIL_ESTOP] is not None else None
                    self.data['pump_switch_status'] = int(coil_values[COIL_SWITCH]) if coil_values[COIL_SWITCH] is not None else None
                    self.data['pump_status'] = int(coil_values[COIL_PUMP]) if coil_values[COIL_PUMP] is not None else None
                    self.data['inflow_valve_status'] = int(coil_values[COIL_IN_VALVE]) if coil_values[COIL_IN_VALVE] is not None else None
                    self.data['outflow_valve_status'] = int(coil_values[COIL_OUT_VALVE]) if coil_values[COIL_OUT_VALVE] is not None else None
                    self.data['overflowed'] = int(coil_values[COIL_ALARM]) if coil_values[COIL_ALARM] is not None else None
                    self.data['inflow_mode'] = int(coil_values[COIL_AUTO]) if coil_values[COIL_AUTO] is not None else None
                    self.data['low_level_alarm'] = int(coil_values[COIL_LOW_LEVEL_ALARM]) if coil_values[COIL_LOW_LEVEL_ALARM] is not None else None
                    self.data['operator_error_alarm'] = int(coil_values[COIL_OPERATOR_ERROR_ALARM]) if coil_values[COIL_OPERATOR_ERROR_ALARM] is not None else None
            except Exception as e:
                print(f"Error reading coils: {e}")

            try:
                hr_response = self.client.read_holding_registers(HR_BASE, count=REGISTER_COUNT)
                if not hr_response.isError():
                    hr_values = hr_response.registers
                    self.data['tank_volume'] = hr_values[HR_LEVEL]
                    self.data['emergency_stop_status'] = hr_values[HR_ESTOP]
                    self.data['pump_switch_status'] = hr_values[HR_SWITCH]
                    self.data['pump_status'] = hr_values[HR_PUMP]
                    self.data['inflow_valve_status'] = hr_values[HR_IN_VALVE]
                    self.data['outflow_valve_status'] = hr_values[HR_OUT_VALVE]
                    self.data['inflow_rate'] = hr_values[HR_IN_FLOW]
                    self.data['outflow_rate'] = hr_values[HR_OUT_FLOW]
                    self.data['inflow_mode'] = hr_values[HR_AUTO]
                    self.data['overflowed'] = hr_values[HR_ALARM]
            except Exception as e:
                print(f"Error reading registers: {e}")
                
            time.sleep(1)

    def write_data(self, control, value):
        print(f"Command: {control}={value}")
        try:
            if self.data['inflow_mode'] == 0:
                if control in ['outflowRate', 'inflowRate']:
                    return jsonify({"error": "Flow rates are auto-controlled in auto mode"}), 400
            
            if control == 'emergencyStop':
                result = self.client.write_register(HR_ESTOP, value, device_id=1)
                print(f"Write register result: {result}")
                result = self.client.write_coil(COIL_ESTOP, bool(value), device_id=1)
                print(f"Write coil result: {result}")
                
            elif control == 'inflowRate':
                result = self.client.write_register(HR_IN_FLOW, int(value), device_id=1)
                print(f"Write register result: {result}")
                
            elif control == 'outflowRate':
                result = self.client.write_register(HR_OUT_FLOW, int(value), device_id=1)
                print(f"Write register result: {result}")
                
            elif control == 'pumpSwitch':
                result = self.client.write_register(HR_SWITCH, value, device_id=1)
                print(f"Write register result: {result}")
                result = self.client.write_coil(COIL_SWITCH, bool(value), device_id=1)
                print(f"Write coil result: {result}")
                
            elif control == 'inflowMode':
                result = self.client.write_register(HR_AUTO, value, device_id=1)
                print(f"Write register result: {result}")
                result = self.client.write_coil(COIL_AUTO, bool(value), device_id=1)
                print(f"Write coil result: {result}")
                
            else:
                return jsonify({"error": "Unknown control"}), 400
                
            print("Command sent")
            return jsonify({"success": "Command sent"}), 200
            
        except Exception as e:
            print(f"Error: {e}")
            return jsonify({"error": str(e)}), 500

    def __del__(self):
        if self.client is not None:
            self.client.close()
            self.client = None


app = Flask(__name__)

modbus = ModbusClient(MODBUS_HOST, MODBUS_PORT)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/update', methods=['GET'])
def update():
    return jsonify({
        'tankLevel': modbus.data['tank_volume'],
        'inflowRate': modbus.data['inflow_rate'],
        'outflowRate': modbus.data['outflow_rate'],
        'pumpSwitch': modbus.data['pump_switch_status'],
        'emergencyStop': modbus.data['emergency_stop_status'],
        'inflowValve': modbus.data['inflow_valve_status'],
        'outflowValve': modbus.data['outflow_valve_status'],
        'inflowMode': modbus.data['inflow_mode'],
        'overflowAlarm': modbus.data['overflowed'],
        'maxVolume': modbus.data['max_volume'],
        'lowLevelAlarm': modbus.data['low_level_alarm'],
        'operatorErrorAlarm': modbus.data['operator_error_alarm'],
        'pumpStatus': modbus.data['pump_status']
    })


@app.route('/write', methods=['POST'])
def write():
    if not request.is_json:
        return jsonify({"error": "Expected JSON"}), 400

    control = request.json.get('control')
    if control is None:
        return jsonify({"error": "Missing control parameter"}), 400

    value = request.json.get('value')
    if value is None:
        return jsonify({"error": "Missing value parameter"}), 400
        
    if control in ['pumpSwitch', 'emergencyStop', 'inflowMode', 'inflowRate', 'outflowRate']:
        try:
            return modbus.write_data(control, value)
        except Exception as e:
            print(f"Error: {e}")
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Invalid control"}), 400


if __name__ == '__main__':
    app.run(host=FLASK_HOST, port=FLASK_PORT)