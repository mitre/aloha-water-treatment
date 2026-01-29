"""
Aloha Water Treatment Plant Control Logic
"""

TANK_MAX = 10000
RATE_MIN = 50

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

COIL_EMERGENCY_STOP = 0
COIL_PUMP_SWITCH = 1
COIL_PUMP_STATUS = 2
COIL_INFLOW_VALVE = 3
COIL_OUTFLOW_VALVE = 4
COIL_INFLOW_MODE = 5
COIL_OVERFLOW_ALARM = 6
COIL_LOW_LEVEL_ALARM = 7
COIL_OPERATOR_ERROR_ALARM = 8

tank_volume = 0


def plc_logic(discrete_inputs, coils, holding_registers, input_registers):
    global tank_volume
    
    register_count = 10
    target_volume = int(2/3 * TANK_MAX)

    hr_values = holding_registers.getValues(1, register_count)
    tank_level = hr_values[HR_TANK_LEVEL]
    emergency_stop = hr_values[HR_EMERGENCY_STOP]
    pump_switch = hr_values[HR_PUMP_SWITCH]
    inflow_valve = hr_values[HR_INFLOW_VALVE]
    outflow_valve = hr_values[HR_OUTFLOW_VALVE]
    inflow_rate = hr_values[HR_INFLOW_RATE]
    outflow_rate = hr_values[HR_OUTFLOW_RATE]
    inflow_mode = hr_values[HR_INFLOW_MODE]
    overflow_alarm = hr_values[HR_OVERFLOW_ALARM]
    
    coil_values = coils.getValues(1, 10)
    coil_emergency_stop = coil_values[COIL_EMERGENCY_STOP]
    coil_pump_switch = coil_values[COIL_PUMP_SWITCH]
    coil_inflow_mode = coil_values[COIL_INFLOW_MODE]
    
    if emergency_stop != coil_emergency_stop:
        holding_registers.setValues(HR_EMERGENCY_STOP + 1, [coil_emergency_stop])
        emergency_stop = coil_emergency_stop
    
    if pump_switch != coil_pump_switch:
        holding_registers.setValues(HR_PUMP_SWITCH + 1, [coil_pump_switch])
        pump_switch = coil_pump_switch
    
    if inflow_mode != coil_inflow_mode:
        holding_registers.setValues(HR_INFLOW_MODE + 1, [coil_inflow_mode])
        inflow_mode = coil_inflow_mode
    
    pump = 0
    
    if pump_switch and not emergency_stop:
        pump = inflow_valve = outflow_valve = 1
        
        if inflow_mode == 0:
            outflow_rate = RATE_MIN
            
            if tank_level <= 1000 and outflow_rate > 0:
                outflow_rate = 0
                outflow_valve = 0
            
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
        pump = inflow_valve = outflow_valve = 0
        inflow_rate = outflow_rate = 0
    
    if pump == 1:
        tank_volume = tank_level + (inflow_rate - outflow_rate)
        
        if tank_volume < 0:
            tank_volume = 0
        elif tank_volume > TANK_MAX:
            overflow_alarm = 1
            
            if inflow_mode == 0:
                tank_volume = TANK_MAX
                inflow_rate = 0
                holding_registers.setValues(HR_INFLOW_RATE + 1, [0])
            else:
                tank_volume = TANK_MAX
        elif tank_volume < TANK_MAX:
            overflow_alarm = 0
    else:
        tank_volume = tank_level
    
    holding_registers.setValues(HR_PUMP_STATUS + 1, [pump])
    coils.setValues(COIL_PUMP_STATUS + 1, [pump])
    
    holding_registers.setValues(HR_TANK_LEVEL + 1, [tank_volume])
    holding_registers.setValues(HR_INFLOW_VALVE + 1, [inflow_valve])
    holding_registers.setValues(HR_OUTFLOW_VALVE + 1, [outflow_valve])
    holding_registers.setValues(HR_INFLOW_RATE + 1, [inflow_rate])
    holding_registers.setValues(HR_OUTFLOW_RATE + 1, [outflow_rate])
    holding_registers.setValues(HR_OVERFLOW_ALARM + 1, [overflow_alarm])
    
    coils.setValues(COIL_INFLOW_VALVE + 1, [inflow_valve])
    coils.setValues(COIL_OUTFLOW_VALVE + 1, [outflow_valve])
    coils.setValues(COIL_OVERFLOW_ALARM + 1, [overflow_alarm])
    
    low_level_alarm = 1 if (tank_volume <= 1000 and outflow_rate > 0) else 0
    coils.setValues(COIL_LOW_LEVEL_ALARM + 1, [low_level_alarm])
    
    operator_error_alarm = 0
    if inflow_mode == 1:
        requested_inflow_rate = hr_values[HR_INFLOW_RATE]
        requested_outflow_rate = hr_values[HR_OUTFLOW_RATE]
        
        if tank_volume <= 1000 and requested_outflow_rate > 0:
            operator_error_alarm = 1
        elif tank_volume >= 9000 and requested_inflow_rate > 0:
            operator_error_alarm = 1
    
    coils.setValues(COIL_OPERATOR_ERROR_ALARM + 1, [operator_error_alarm])
