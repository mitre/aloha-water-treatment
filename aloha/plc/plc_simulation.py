"""
Aloha Water Treatment Plant Control Logic
Core PLC simulation logic
"""

import logging
from dataclasses import dataclass


# Core tank capacity and control target values used by the simulation.
TANK_MAX            = 10000
TARGET_VOLUME       = 2/3 * TANK_MAX
RATE_LV3            = 80  # Fast fill boost when volume is far below target.
RATE_LV2            = 40  # Medium fill boost when volume is moderately below target.
RATE_LV1            = 20  # Slow fill boost when volume is slightly below target.
RATE_MIN            = 50  # Baseline flow rate used for normal operation.

# Operating thresholds for draining and filling behavior.
DRAIN_VOLUME_MIN    = 1000
FILL_VOLUME_MAX     = 500

# Thresholds used for operator error detection in manual mode.
TANK_ERR_THRESH_MIN = DRAIN_VOLUME_MIN
TANK_ERR_THRESH_MAX = TANK_MAX - TANK_ERR_THRESH_MIN

# Global backing store for the simulated tank volume.
tank_volume = 0

logger: logging.Logger = logging.getLogger(__name__)

@dataclass
class SimulationContext:
    """
    Protocol-neutral state container for the water treatment simulation.

    This dataclass abstracts away protocol-specific data representation details so
    the simulation can operate on a common in-memory model regardless of backing
    PLC communication OT protocol being used.

    To use this, an OT protocol must implement the Pythonic Protocol class defined
    in PLC.py and use those interfaces to synchronize its PLC state with a context object.
    """
    # Command, status, and alarm flags.
    estop     : bool  = False  # Emergency Stop       (True = Active,  False = Inactive)
    pswitch   : bool  = False  # Pump Switch          (True = On,      False = Off)
    pstatus   : bool  = False  # Pump Status          (True = Running, False = Stopped)
    in_valve  : bool  = False  # Inflow Valve         (True = Open,    False = Closed)
    out_valve : bool  = False  # Outflow Valve        (True = Open,    False = Closed)
    manual_op : bool  = False  # Pump manual mode     (True = Manual,  False = Auto)
    of_alarm  : bool  = False  # Overflow Alarm       (True = Active,  False = Inactive)
    ll_alarm  : bool  = False  # Low Level Alarm      (True = Active,  False = Inactive)
    oe_alarm  : bool  = False  # Operator Error Alarm (True = Active,  False = Inactive)

    # Physical process values.
    level     : int   = 0      # Current tank level   (0-10000)
    in_flow   : float = 0.0    # Current pump inflow rate  (>0 when pump active)
    out_flow  : float = 0.0    # Current pump outflow rate (>0 when pump active)

    def __repr__(self) -> str:
        """
        Return a compact debug-friendly representation of simulation state.
        """
        return "".join(["CTX: [",
            f"{1 if self.estop     else 0},",
            f"{1 if self.pswitch   else 0},",
            f"{1 if self.pstatus   else 0},",
            f"{1 if self.in_valve  else 0},",
            f"{1 if self.out_valve else 0},",
            f"{1 if self.manual_op else 0},",
            f"{1 if self.of_alarm  else 0},",
            f"{1 if self.ll_alarm  else 0},",
            f"{1 if self.oe_alarm  else 0}] ",
            f"Level: {self.level}; Inflow: {self.in_flow}/s; Outflow: {self.out_flow}/s"])

def simulation_step(sim: SimulationContext) -> None:
    """
    Advance the water treatment simulation by one step.

    The function updates pump state, valve state, flow rates, tank level, and
    alarm conditions based on the current control inputs in the simulation
    context. In automatic mode, inflow is adjusted to steer the tank toward the
    target volume. In manual mode, the function leaves operator-selected flow
    behavior unchanged where applicable.

    Alarms are raised depending on certain tank thresholds and flow rates

    Args:
        sim: The simulation context to update in place.
    """
    global tank_volume

    # Default to a stopped pump at the beginning of each cycle. The pump is
    # enabled again below only if the switch is on and E-stop is not active.
    sim.pstatus = False

    logger.debug(f"Pre-{sim}")

    # The pump and valves can only run when the pump switch is enabled and the
    # emergency stop is not active.
    if sim.pswitch and not sim.estop:
        sim.pstatus = sim.in_valve = sim.out_valve = True

        if not sim.manual_op:   # Manual override is disabled
            # Auto mode always attempts a minimum outflow first, unless the tank
            # is already too low to drain safely.
            sim.out_flow = RATE_MIN

            if sim.level <= DRAIN_VOLUME_MIN and sim.out_flow > 0:
                sim.out_flow = 0
                sim.out_valve = False

            # In auto mode, inflow is adjusted in steps based on how far the
            # current level is below the target volume.
            if sim.level < TARGET_VOLUME:
                deficit = TARGET_VOLUME - sim.level
                if deficit > 3000:
                    sim.in_flow = RATE_MIN + RATE_LV3
                elif deficit > 1500:
                    sim.in_flow = RATE_MIN + RATE_LV2
                elif deficit > 500:
                    sim.in_flow = RATE_MIN + RATE_LV1
                else:
                    sim.in_flow = RATE_MIN
            else:
                # Once the target is reached, inflow is either maintained at the
                # baseline rate or shut off if the level exceeds the permitted
                # fill margin above the target.
                if sim.level > TARGET_VOLUME + FILL_VOLUME_MAX:
                    sim.in_flow = 0
                else:
                    sim.in_flow = RATE_MIN
        else:
            # In manual mode, this function intentionally does not overwrite
            # flow values here. The current values are assumed to come from
            # external operator or PLC-controlled inputs.
            pass
    else:
        # If the pump is not allowed to run, all active process movement stops.
        sim.pstatus = sim.in_valve = sim.out_valve = False
        sim.in_flow = sim.out_flow = 0

    # Update tank volume only while the pump system is considered active.
    if sim.pstatus:
        tank_volume = sim.level + (sim.in_flow - sim.out_flow)

        # Clamp the lower bound to prevent negative volume.
        if tank_volume < 0:
            tank_volume = 0
        elif tank_volume > TANK_MAX:
            # Overflow condition has been reached.
            sim.of_alarm = True

            # In manual mode, inflow is explicitly shut off once the tank is
            # full. In auto mode, the level is still clamped but inflow is not
            # modified here.
            tank_volume = TANK_MAX
            if sim.manual_op:
                sim.in_flow = 0
        elif tank_volume < TANK_MAX:
            # Clear overflow alarm whenever the tank is below maximum capacity.
            sim.of_alarm = False
    else:
        # When the system is not actively running, preserve the current level.
        tank_volume = sim.level

    # Publish the computed tank volume back into the shared context.
    sim.level = tank_volume

    # Low-level alarm is active only when the tank is at or below the minimum
    # drain threshold while outflow is still occurring.
    sim.ll_alarm = True if (
        tank_volume <= TANK_ERR_THRESH_MIN and sim.out_flow > 0) else False

    # Operator error alarm is used only in manual mode to flag actions that
    # would worsen an unsafe low or high tank condition.
    sim.oe_alarm = False
    if sim.manual_op:
        if tank_volume <= TANK_ERR_THRESH_MIN and sim.out_flow > 0:
            sim.oe_alarm = True
        elif tank_volume >= TANK_ERR_THRESH_MAX and sim.in_flow > 0:
            sim.oe_alarm = True

    logger.debug(f"Post-{sim}")
