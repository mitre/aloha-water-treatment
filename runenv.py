#!/usr/bin/env python3
"""
Aloha Water Treatment Plant startup script
Necessary variables need to be established in a .env file
"""

import os
import sys

from dotenv import load_dotenv

from run import foreground, module, run_local
from simulator import SIM
from simulator.config import AlohaEnvVar

RUNMODES = ("local", "plc", "hmi")


def main() -> int:
    """
    Load .env, check its settings, and run the PLC, the HMI, or both.

    Returns:
        The exit status of the PLC or HMI, or 1 if a setting is invalid.
    """
    load_dotenv()

    protocol = (os.getenv(AlohaEnvVar.protocol) or "").lower()
    if protocol not in SIM["protocols"]:
        print(f"{AlohaEnvVar.protocol.value} must be one of: {', '.join(SIM['protocols'])}", file=sys.stderr)
        return 1
    runmode = (os.getenv(AlohaEnvVar.runmode) or "").lower()
    if runmode not in RUNMODES:
        print(f"{AlohaEnvVar.runmode.value} must be one of: {', '.join(RUNMODES)}", file=sys.stderr)
        return 1
    settings = SIM["protocols"][protocol]
    if runmode == "local" and not settings["local"]:
        print(f"{settings['name']} can't run locally: the PLC and the HMI each need the same port. "
              f"Run them on different hosts.", file=sys.stderr)
        return 1

    host = os.getenv(AlohaEnvVar.ip) or (settings["bind"] if runmode == "plc" else "127.0.0.1")
    port = os.getenv(AlohaEnvVar.port) or str(settings["port"])
    target = ["--host", host, "--port", port, "--protocol", protocol]
    plc = module("simulator.plc", *target)
    hmi = module("simulator.hmi", *target)

    if runmode == "local":
        return run_local(plc, hmi, host, port)
    return foreground(plc if runmode == "plc" else hmi)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
