"""
Aloha Water Treatment Plant HMI
Flask web application for monitoring and controlling the treatment plant via BACnet
"""

import threading
import asyncio
import os
import BAC0

from flask import Flask, render_template, request, jsonify

FLASK_HOST = "0.0.0.0"
FLASK_PORT = 8090
DEVICE_IP = os.getenv("DEVICE_IP", "127.0.0.1")
DEVICE_ID = "1001"
TANK_MAX = 10000


class BACnetClient:
    def __init__(self, device_ip):
        self.device_ip = device_ip
        self.bacnet = None
        self.loop = None
        self.lock = threading.Lock()
        
        self.thread = threading.Thread(target=self._init_bacnet, daemon=True)
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
    
    def _init_bacnet(self):
        asyncio.run(self._async_init())
    
    async def _async_init(self):
        self.loop = asyncio.get_event_loop()
        
        while True:
            try:
                if self.bacnet is None:
                    try:
                        self.bacnet = BAC0.connect()
                        await asyncio.sleep(2)
                    except Exception as e:
                        await asyncio.sleep(5)
                        continue
                
                await self._read_all()
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Error in BACnet cycle: {e}")
                await asyncio.sleep(2)
    
    async def _read_all(self):
        if self.bacnet is None:
            return
        
        try:
            tasks = [
                self._read_value('analogValue', 1, 'presentValue'),
                self._read_value('analogValue', 2, 'presentValue'),
                self._read_value('analogValue', 3, 'presentValue'),
                self._read_value('binaryValue', 1, 'presentValue'),
                self._read_value('binaryValue', 2, 'presentValue'),
                self._read_value('binaryValue', 3, 'presentValue'),
                self._read_value('binaryOutput', 1, 'presentValue'),
                self._read_value('binaryOutput', 2, 'presentValue'),
                self._read_value('binaryOutput', 3, 'presentValue'),
                self._read_value('binaryOutput', 4, 'presentValue'),
                self._read_value('binaryOutput', 5, 'presentValue'),
                self._read_value('binaryOutput', 6, 'presentValue'),
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            self.data['tank_volume'] = int(results[0]) if results[0] is not None else 0
            self.data['inflow_rate'] = int(results[1]) if results[1] is not None else 0
            self.data['outflow_rate'] = int(results[2]) if results[2] is not None else 0
            self.data['emergency_stop_status'] = 1 if str(results[3]) == 'active' else 0
            self.data['pump_switch_status'] = 1 if str(results[4]) == 'active' else 0
            self.data['inflow_mode'] = 1 if str(results[5]) == 'active' else 0
            self.data['pump_status'] = 1 if str(results[6]) == 'active' else 0
            self.data['inflow_valve_status'] = 1 if str(results[7]) == 'active' else 0
            self.data['outflow_valve_status'] = 1 if str(results[8]) == 'active' else 0
            self.data['overflowed'] = 1 if str(results[9]) == 'active' else 0
            self.data['low_level_alarm'] = 1 if str(results[10]) == 'active' else 0
            self.data['operator_error_alarm'] = 1 if str(results[11]) == 'active' else 0
            
        except Exception as e:
            print(f"Error reading BACnet data: {e}")
    
    async def _read_value(self, obj_type, instance, prop):
        try:
            command = f'{self.device_ip} {obj_type} {instance} {prop}'
            task = asyncio.create_task(self.bacnet.read(command))
            value = await asyncio.wait_for(task, timeout=10.0)
            return value
        except Exception:
            return None
    
    async def _write_value(self, obj_type, instance, prop, value, priority=5):
        try:
            command = f'{self.device_ip} {obj_type} {instance} {prop} {value} - {priority}'
            await self.bacnet._write(command)
            return True
        except Exception as e:
            print(f"Error writing {obj_type} {instance}: {e}")
            return False
    
    def write_data(self, control, value):
        print(f"Command: {control}={value}")
        
        if self.bacnet is None or self.loop is None:
            return jsonify({"error": "BACnet not connected"}), 503
        
        try:
            if self.data['inflow_mode'] == 0:
                if control in ['outflowRate', 'inflowRate']:
                    return jsonify({"error": "Flow rates are auto-controlled in auto mode"}), 400
            
            obj_type = None
            instance = None
            write_value = None
            
            if control == 'emergencyStop':
                obj_type = 'binaryValue'
                instance = 1
                write_value = 'active' if value else 'inactive'
                
            elif control == 'pumpSwitch':
                obj_type = 'binaryValue'
                instance = 2
                write_value = 'active' if value else 'inactive'
                
            elif control == 'inflowMode':
                obj_type = 'binaryValue'
                instance = 3
                write_value = 'active' if value else 'inactive'
                
            elif control == 'inflowRate':
                obj_type = 'analogValue'
                instance = 2
                write_value = int(value)
                
            elif control == 'outflowRate':
                obj_type = 'analogValue'
                instance = 3
                write_value = int(value)
                
            else:
                return jsonify({"error": "Unknown control"}), 400
            
            with self.lock:
                future = asyncio.run_coroutine_threadsafe(
                    self._write_value(obj_type, instance, 'presentValue', write_value),
                    self.loop
                )
                success = future.result(timeout=5.0)
            
            if success:
                print("Command sent")
                return jsonify({"success": "Command sent"}), 200
            else:
                return jsonify({"error": "Write failed"}), 500
                
        except Exception as e:
            print(f"Error: {e}")
            return jsonify({"error": str(e)}), 500
    
    def __del__(self):
        if self.bacnet is not None:
            try:
                asyncio.run(self.bacnet.disconnect())
            except:
                pass


app = Flask(__name__)

bacnet_client = BACnetClient(DEVICE_IP)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/update', methods=['GET'])
def update():
    return jsonify({
        'tankVolume': bacnet_client.data['tank_volume'],
        'inflowRate': bacnet_client.data['inflow_rate'],
        'outflowRate': bacnet_client.data['outflow_rate'],
        'pumpSwitchStatus': bacnet_client.data['pump_switch_status'],
        'emergencyStopStatus': bacnet_client.data['emergency_stop_status'],
        'inflowValveStatus': bacnet_client.data['inflow_valve_status'],
        'outflowValveStatus': bacnet_client.data['outflow_valve_status'],
        'inflowMode': bacnet_client.data['inflow_mode'],
        'overflowed': bacnet_client.data['overflowed'],
        'maxVolume': bacnet_client.data['max_volume'],
        'lowLevelAlarm': bacnet_client.data['low_level_alarm'],
        'operatorErrorAlarm': bacnet_client.data['operator_error_alarm'],
        'pumpStatus': bacnet_client.data['pump_status']
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
            return bacnet_client.write_data(control, value)
        except Exception as e:
            print(f"Error: {e}")
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Invalid control"}), 400


if __name__ == '__main__':
    BAC0.log_level('silence')
    app.run(host=FLASK_HOST, port=FLASK_PORT)
