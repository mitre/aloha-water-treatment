import os
import tempfile
import unittest
from unittest import mock

from simulator import SIM
from simulator.config import parse_args


def parse(*argv, default_host=None):
    return parse_args("test", "test", "host", "port", default_host=default_host, argv=list(argv))


@mock.patch.dict(os.environ, {}, clear=True)
class CommandLineTests(unittest.TestCase):
    def test_plc_defaults_match_sim(self):
        for protocol, settings in SIM["protocols"].items():
            args = parse("--protocol", protocol)
            self.assertEqual(args.host, settings["bind"])
            self.assertEqual(args.port, settings["port"])

    def test_hmi_defaults_to_localhost(self):
        args = parse(default_host="127.0.0.1")
        self.assertEqual(args.protocol, "modbus")
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 5020)

    def test_environment_sets_defaults(self):
        env = {"ALOHA_PROTOCOL": "BACnet", "ALOHA_IP": "10.0.0.5", "ALOHA_PORT": "47809"}
        with mock.patch.dict(os.environ, env):
            args = parse()
        self.assertEqual((args.protocol, args.host, args.port), ("bacnet", "10.0.0.5", 47809))

    def test_flags_override_environment(self):
        with mock.patch.dict(os.environ, {"ALOHA_IP": "10.0.0.5", "ALOHA_PORT": "502"}):
            args = parse("--host", "plc", "--port", "5020")
        self.assertEqual((args.host, args.port), ("plc", 5020))

    def test_config_file_sets_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "aloha.env")
            with open(path, "w") as f:
                f.write("ALOHA_PROTOCOL=bacnet\nALOHA_PORT=47809\n")
            args = parse("--config", path)
            self.assertEqual((args.protocol, args.port), ("bacnet", 47809))
            with mock.patch.dict(os.environ, {"ALOHA_PORT": "47810"}):
                args = parse("--config", path)
            self.assertEqual(args.port, 47810)

    def test_rejects_bad_values(self):
        for argv, env in ((["--port", "0"], {}), ([], {"ALOHA_PROTOCOL": "dnp3"}),
                          ([], {"ALOHA_PORT": "abc"}), (["--config", "missing.env"], {})):
            with mock.patch.dict(os.environ, env), mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit):
                    parse(*argv)


if __name__ == "__main__":
    unittest.main()
