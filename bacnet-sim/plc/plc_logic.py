"""
Aloha Water Treatment Plant Control Logic
BACnet implementation
"""

TANK_MAX = 10000
RATE_MIN = 50

tank_volume = 0


def plc_logic(bacnet_objects):
    """
    Process control logic for water treatment plant
    Updates BACnet objects based on current state and inputs
    """
    global tank_volume
    
    target_volume = int(2 / 3 * TANK_MAX)

    level = bacnet_objects['tankLevel'].presentValue
    estop = bacnet_objects['emergencyStop'].presentValue
    switch = bacnet_objects['pumpSwitch'].presentValue
    in_flow = bacnet_objects['inflowRate'].presentValue
    out_flow = bacnet_objects['outflowRate'].presentValue
    auto_mode = bacnet_objects['autoMode'].presentValue
    alarm = bacnet_objects['overflowAlarm'].presentValue
    
    pump = False
    in_valve = False
    out_valve = False
    
    if switch and not estop:
        pump = in_valve = out_valve = True
        
        if not auto_mode:
            out_flow = RATE_MIN
            
            if level <= 1000 and out_flow > 0:
                out_flow = 0
                out_valve = False
            
            if level < target_volume:
                deficit = target_volume - level
                if deficit > 3000:
                    in_flow = RATE_MIN + 80
                elif deficit > 1500:
                    in_flow = RATE_MIN + 40
                elif deficit > 500:
                    in_flow = RATE_MIN + 20
                else:
                    in_flow = RATE_MIN
            else:
                if level > target_volume + 500:
                    in_flow = 0
                else:
                    in_flow = RATE_MIN
        else:
            pass
    else:
        pump = in_valve = out_valve = False
        in_flow = out_flow = 0
    
    if pump:
        tank_volume = level + (in_flow - out_flow)
        
        if tank_volume < 0:
            tank_volume = 0
        elif tank_volume > TANK_MAX:
            alarm = True
            
            if not auto_mode:
                tank_volume = TANK_MAX
                in_flow = 0
            else:
                tank_volume = TANK_MAX
        elif tank_volume < TANK_MAX:
            alarm = False
    else:
        tank_volume = level
    
    bacnet_objects['pumpStatus'].presentValue = pump
    bacnet_objects['tankLevel'].presentValue = int(tank_volume)
    bacnet_objects['inflowValve'].presentValue = in_valve
    bacnet_objects['outflowValve'].presentValue = out_valve
    bacnet_objects['inflowRate'].presentValue = int(in_flow)
    bacnet_objects['outflowRate'].presentValue = int(out_flow)
    bacnet_objects['overflowAlarm'].presentValue = alarm
    
    low_level_alarm = (tank_volume <= 1000 and out_flow > 0)
    bacnet_objects['lowLevelAlarm'].presentValue = low_level_alarm
    
    operator_error_alarm = False
    if auto_mode:
        if tank_volume <= 1000 and bacnet_objects['inflowRate'].presentValue > 0 and out_flow > 0:
            operator_error_alarm = True
        elif tank_volume >= 9000 and in_flow > 0:
            operator_error_alarm = True
    
    bacnet_objects['operatorErrorAlarm'].presentValue = operator_error_alarm
