"""
Aloha Water Treatment Plant PLC Simulation
Defines shared constants and the command line both the HMI and PLC use
"""

import argparse
import logging
import os
from enum import StrEnum
from pathlib import Path

from dotenv import dotenv_values

from simulator import SIM

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / ".env.example"

class AlohaEnvVar(StrEnum):
    """
    Core environment variable names
    """
    runmode  = "ALOHA_RUNMODE"
    protocol = "ALOHA_PROTOCOL"
    ip       = "ALOHA_IP"
    port     = "ALOHA_PORT"

def configure_logging(debug: bool = False) -> None:
    """
    Standardized logging config
    """
    logging.basicConfig(
        level  = logging.DEBUG if debug else logging.INFO,
        format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

def parse_args(prog: str, description: str, host_help: str, port_help: str,
               default_host: str | None = None, extra=None,
               argv: list[str] | None = None) -> argparse.Namespace:
    """
    Parse the flags shared by the PLC and the HMI.

    The ALOHA_* environment variables set the defaults, then the same variables
    in the --config file. Without them, the protocol defaults to Modbus, the
    port to the protocol's port, and the host to default_host, or the
    protocol's bind address when default_host is None.

    Args:
        prog: Program name shown in --help.
        description: Description shown in --help.
        host_help: Help text for --host.
        port_help: Help text for --port.
        default_host: Default for --host, or None for the protocol's bind address.
        extra: Optional callable that adds more arguments to the parser.
        argv: Arguments to parse, sys.argv when None.

    Returns:
        The parsed arguments, with protocol, host and port filled in.
    """
    parser = argparse.ArgumentParser(
        prog=prog,
        description=f"{description} ALOHA_* environment variables take precedence over the config.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), metavar="PATH",
                        help="configuration file (default: .env.example in the repo root)")
    parser.add_argument("--host", metavar="HOST", help=host_help)
    parser.add_argument("--port", type=int, metavar="PORT", help=port_help)
    parser.add_argument("--protocol", choices=list(SIM["protocols"]),
                        help="protocol (default: ALOHA_PROTOCOL in the config, modbus)")
    if extra:
        extra(parser)
    parser.add_argument("--debug", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.config):
        parser.error(f"config file {args.config} not found")
    config = dotenv_values(args.config)

    def setting(name: AlohaEnvVar) -> str | None:
        return os.getenv(name) or config.get(name) or None

    args.protocol = args.protocol or (setting(AlohaEnvVar.protocol) or "modbus").lower()
    if args.protocol not in SIM["protocols"]:
        parser.error(f"unknown protocol '{args.protocol}' (choose from {', '.join(SIM['protocols'])})")
    settings = SIM["protocols"][args.protocol]
    if args.host is None:
        args.host = setting(AlohaEnvVar.ip) or default_host or settings["bind"]
    if args.port is None:
        port = setting(AlohaEnvVar.port)
        if port is not None and not port.isdigit():
            parser.error(f"ALOHA_PORT '{port}' is not a number")
        args.port = int(port) if port is not None else settings["port"]
    if not 0 < args.port < 65536:
        parser.error(f"port {args.port} is not between 1 and 65535")
    return args
