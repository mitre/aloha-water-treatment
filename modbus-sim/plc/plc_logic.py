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
    level = hr_values[HR_TANK_LEVEL]
    estop = hr_values[HR_EMERGENCY_STOP]
    switch = hr_values[HR_PUMP_SWITCH]
    in_valve = hr_values[HR_INFLOW_VALVE]
    out_valve = hr_values[HR_OUTFLOW_VALVE]
    in_flow = hr_values[HR_INFLOW_RATE]
    out_flow = hr_values[HR_OUTFLOW_RATE]
    auto_mode = hr_values[HR_INFLOW_MODE]
    alarm = hr_values[HR_OVERFLOW_ALARM]

    coil_values = coils.getValues(1, 10)
    coil_estop_value = coil_values[COIL_EMERGENCY_STOP]
    coil_switch_value = coil_values[COIL_PUMP_SWITCH]
    coil_auto_value = coil_values[COIL_INFLOW_MODE]

    if estop != coil_estop_value:
        holding_registers.setValues(HR_EMERGENCY_STOP + 1, [coil_estop_value])
        estop = coil_estop_value

    if switch != coil_switch_value:
        holding_registers.setValues(HR_PUMP_SWITCH + 1, [coil_switch_value])
        switch = coil_switch_value

    if auto_mode != coil_auto_value:
        holding_registers.setValues(HR_INFLOW_MODE + 1, [coil_auto_value])
        auto_mode = coil_auto_value
    
    pump = 0
    
    if switch and not estop:
        pump = in_valve = out_valve = 1
        
        if auto_mode == 0:
            out_flow = RATE_MIN
            
            if level <= 1000 and out_flow > 0:
                out_flow = 0
                out_valve = 0
            
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
        pump = in_valve = out_valve = 0
        in_flow = out_flow = 0
    
    if pump == 1:
        tank_volume = level + (in_flow - out_flow)
        
        if tank_volume < 0:
            tank_volume = 0
        elif tank_volume > TANK_MAX:
            alarm = 1
            
            if auto_mode == 0:
                tank_volume = TANK_MAX
                in_flow = 0
                holding_registers.setValues(HR_INFLOW_RATE + 1, [0])
            else:
                tank_volume = TANK_MAX
        elif tank_volume < TANK_MAX:
            alarm = 0
    else:
        tank_volume = level
    
    holding_registers.setValues(HR_PUMP_STATUS + 1, [pump])
    coils.setValues(COIL_PUMP_STATUS + 1, [pump])

    holding_registers.setValues(HR_TANK_LEVEL + 1, [tank_volume])
    holding_registers.setValues(HR_INFLOW_VALVE + 1, [in_valve])
    holding_registers.setValues(HR_OUTFLOW_VALVE + 1, [out_valve])
    holding_registers.setValues(HR_INFLOW_RATE + 1, [in_flow])
    holding_registers.setValues(HR_OUTFLOW_RATE + 1, [out_flow])
    holding_registers.setValues(HR_OVERFLOW_ALARM + 1, [alarm])

    coils.setValues(COIL_INFLOW_VALVE + 1, [in_valve])
    coils.setValues(COIL_OUTFLOW_VALVE + 1, [out_valve])
    coils.setValues(COIL_OVERFLOW_ALARM + 1, [alarm])

    low_level_alarm = 1 if (tank_volume <= 1000 and out_flow > 0) else 0
    coils.setValues(COIL_LOW_LEVEL_ALARM + 1, [low_level_alarm])

    operator_error_alarm = 0
    if auto_mode == 1:
        requested_in_flow = hr_values[HR_INFLOW_RATE]
        requested_out_flow = hr_values[HR_OUTFLOW_RATE]

        if tank_volume <= 1000 and requested_out_flow > 0:
            operator_error_alarm = 1
        elif tank_volume >= 9000 and requested_in_flow > 0:
            operator_error_alarm = 1

    coils.setValues(COIL_OPERATOR_ERROR_ALARM + 1, [operator_error_alarm])
