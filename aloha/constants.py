"""
Aloha Water Treatment Plant PLC Simulation
Defines shared constants that both the HMI and PLC should be aware of
"""

import logging
from enum import StrEnum

class ImplementedProtocol(StrEnum):
    """
    Currently implemented protocol list
    """
    BACNET = "bacnet"
    MODBUS = "modbus"

class AlohaEnvVar(StrEnum):
    """
    Core environment variable names
    """
    runmode  = "ALOHA_RUNMODE"
    protocol = "ALOHA_PROTOCOL"
    ip       = "ALOHA_IP"
    port     = "ALOHA_PORT"

def configure_logging(level: int = logging.INFO) -> None:
    """
    Standardized logging config
    """
    logging.basicConfig(
        level   = level,
        format  = "%(asctime)s [%(levelname)-8s: %(filename)-15s] | '%(message)s'",
        datefmt = "%H:%M:%S",
    )
