import unittest

from pymodbus.pdu.bit_message import WriteMultipleCoilsRequest, WriteSingleCoilRequest
from pymodbus.pdu.register_message import WriteSingleRegisterRequest

from simulator.modbus.modbus_plc import ModbusPLCInterface


class ModbusPLCLogTests(unittest.TestCase):
    def setUp(self):
        self.plc = ModbusPLCInterface("127.0.0.1", 5020)
        self.plc.setup_plc()

    def test_client_writes_are_logged(self):
        with self.assertLogs("simulator.modbus.modbus_plc", "INFO") as logs:
            self.plc.trace_pdu(False, WriteSingleCoilRequest(address=0, bits=[True]))
            self.plc.trace_pdu(False, WriteMultipleCoilsRequest(address=1, bits=[True, False]))
            self.plc.trace_pdu(False, WriteSingleRegisterRequest(address=6, registers=[900]))
            self.plc.trace_pdu(False, WriteSingleRegisterRequest(address=200, registers=[7]))
        self.assertEqual(
            [record.getMessage() for record in logs.records],
            [
                "Client wrote coil 0 = ON",
                "Client wrote coils 1-2 = ON,OFF",
                "Client wrote holding register 6 = 900",
                "Rejected client write to holding register 200 = 7: address out of range",
            ],
        )

    def test_connections_are_not_logged_at_info(self):
        with self.assertNoLogs("simulator.modbus.modbus_plc", "INFO"):
            self.plc.trace_connect(True)
            self.plc.trace_connect(False)


if __name__ == "__main__":
    unittest.main()
