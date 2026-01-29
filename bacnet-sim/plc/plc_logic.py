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

    tank_level = bacnet_objects['tankLevel'].presentValue
    emergency_stop = bacnet_objects['emergencyStop'].presentValue
    pump_switch = bacnet_objects['pumpSwitch'].presentValue
    inflow_rate = bacnet_objects['inflowRate'].presentValue
    outflow_rate = bacnet_objects['outflowRate'].presentValue
    inflow_mode = bacnet_objects['inflowMode'].presentValue
    overflow_alarm = bacnet_objects['overflowAlarm'].presentValue
    
    pump = False
    in_valve = False
    out_valve = False
    
    if pump_switch and not emergency_stop:
        pump = inflow_valve = outflow_valve = True
        if not inflow_mode:
            outflow_rate = RATE_MIN
            if tank_level <= 1000 and outflow_rate > 0:
                outflow_rate = 0
                outflow_valve = False
            if tank_level < target_volume:
                deficit = target_volume - tank_level
                if deficit > 3000:
                    inflow_rate = RATE_MIN + 80
                elif deficit > 1500:
                    inflow_rate = RATE_MIN + 40
                elif deficit > 500:
                    inflow_rate = RATE_MIN + 20
                else:
                    inflow_rate = RATE_MIN
            else:
                if tank_level > target_volume + 500:
                    inflow_rate = 0
                else:
                    inflow_rate = RATE_MIN
        else:
            pass
    else:
        pump = inflow_valve = outflow_valve = False
        inflow_rate = outflow_rate = 0
    if pump:
        tank_volume = tank_level + (inflow_rate - outflow_rate)
        if tank_volume < 0:
            tank_volume = 0
        elif tank_volume > TANK_MAX:
            overflow_alarm = True
            if not inflow_mode:
                tank_volume = TANK_MAX
                inflow_rate = 0
            else:
                tank_volume = TANK_MAX
        elif tank_volume < TANK_MAX:
            overflow_alarm = False
    else:
        tank_volume = tank_level
    bacnet_objects['pumpStatus'].presentValue = pump
    bacnet_objects['tankLevel'].presentValue = int(tank_volume)
    bacnet_objects['inflowValve'].presentValue = inflow_valve
    bacnet_objects['outflowValve'].presentValue = outflow_valve
    bacnet_objects['inflowRate'].presentValue = int(inflow_rate)
    bacnet_objects['outflowRate'].presentValue = int(outflow_rate)
    bacnet_objects['overflowAlarm'].presentValue = overflow_alarm
    low_level_alarm = (tank_volume <= 1000 and outflow_rate > 0)
    bacnet_objects['lowLevelAlarm'].presentValue = low_level_alarm
    operator_error_alarm = False
    if inflow_mode:
        if tank_volume <= 1000 and bacnet_objects['inflowRate'].presentValue > 0 and outflow_rate > 0:
            operator_error_alarm = True
        elif tank_volume >= 9000 and inflow_rate > 0:
            operator_error_alarm = True
    bacnet_objects['operatorErrorAlarm'].presentValue = operator_error_alarm
