import unittest

from simulator.sim import (
    DRAIN_VOLUME_MIN,
    FILL_VOLUME_MAX,
    TANK_MAX,
    TARGET_VOLUME,
    SimulationContext,
    simulation_step,
)


class SimulationTests(unittest.TestCase):
    def test_estop_keeps_pump_stopped(self):
        sim = SimulationContext(pswitch=True, estop=True, level=5000)
        simulation_step(sim)
        self.assertFalse(sim.pstatus)
        self.assertFalse(sim.in_valve)
        self.assertFalse(sim.out_valve)
        self.assertEqual(sim.in_flow, 0)
        self.assertEqual(sim.out_flow, 0)
        self.assertEqual(sim.level, 5000)

    def test_auto_mode_fills_toward_target(self):
        sim = SimulationContext(pswitch=True)
        for _ in range(300):
            simulation_step(sim)
        self.assertTrue(sim.pstatus)
        self.assertGreaterEqual(sim.level, TARGET_VOLUME - FILL_VOLUME_MAX)
        self.assertLessEqual(sim.level, TARGET_VOLUME)

    def test_overflow_alarm_at_tank_max(self):
        sim = SimulationContext(
            pswitch=True, manual_op=True, level=TANK_MAX - 10, in_flow=100, out_flow=0)
        simulation_step(sim)
        self.assertTrue(sim.of_alarm)
        self.assertEqual(sim.level, TANK_MAX)

    def test_low_level_alarm_while_draining(self):
        sim = SimulationContext(
            pswitch=True, manual_op=True, level=DRAIN_VOLUME_MIN // 2, in_flow=0, out_flow=50)
        simulation_step(sim)
        self.assertLessEqual(sim.level, DRAIN_VOLUME_MIN)
        self.assertTrue(sim.ll_alarm)

    def test_operator_error_alarm_only_in_manual_mode(self):
        manual = SimulationContext(
            pswitch=True, manual_op=True, level=DRAIN_VOLUME_MIN // 2, in_flow=0, out_flow=50)
        simulation_step(manual)
        self.assertTrue(manual.oe_alarm)

        auto = SimulationContext(
            pswitch=True, level=DRAIN_VOLUME_MIN // 2, in_flow=0, out_flow=50)
        simulation_step(auto)
        self.assertFalse(auto.oe_alarm)


if __name__ == "__main__":
    unittest.main()
