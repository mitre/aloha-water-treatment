#!/usr/bin/env python3
"""
Aloha Water Treatment Plant startup script
Necessary variables need to be established in a .env file
"""

import logging
import sys
import os
import subprocess
import time

from dotenv import load_dotenv
from pathlib import Path

from aloha.constants import AlohaEnvVar, ImplementedProtocol, configure_logging

# The root path that this codebase exists at. May need modification for docker
AppPath = Path(__file__).parent.absolute()  
logger = logging.getLogger(__name__)


def check_environment(variable: AlohaEnvVar, error_msg: str) -> None:
    """
    Verify that a required environment variable is set.

    Args:
        variable: The environment variable definition to check.
        error_msg: Error message to log and raise if the variable is missing.

    Raises:
        EnvironmentError: If the required environment variable is not set.
    """
    if os.getenv(variable.value) is None:
        logger.error(error_msg)
        raise EnvironmentError(error_msg)


def identifyProtocol() -> ImplementedProtocol | None:
    """
    Read and validate the configured protocol from the environment.

    Returns:
        The configured ImplementedProtocol value if parsing succeeds.

    Raises:
        EnvironmentError: If the configured protocol value is invalid.
    """
    try:
        return ImplementedProtocol(os.getenv(AlohaEnvVar.protocol.value).lower())
    except ValueError as e:
        raise EnvironmentError() from e


def run_local() -> None:
    """
    Start both the PLC and HMI locally using the provided environment.

    The PLC is started as a background subprocess first, then the HMI is run in
    the foreground. When the HMI exits, the PLC process is terminated.
    """
    env = os.environ.copy()
    logger.info("Starting PLC locally")
    # The -m flag is necessary to ensure package resolution
    plc = subprocess.Popen(
        [sys.executable, "-m", "aloha.plc.PLC"], cwd=AppPath, env=env)
    time.sleep(2)
    logger.info("Starting HMI locally")
    try:
        # The -m flag is necessary to ensure package resolution
        subprocess.run([sys.executable, "-m", "aloha.hmi.HMI"],
                       cwd=AppPath, env=env)
    except KeyboardInterrupt:
        pass
    finally:
        # Ensure the PLC subprocess is stopped when the local session ends.
        plc.terminate()
        plc.wait()


def run_plc():
    """
    Start only the PLC process using the current environment configuration.
    """
    run_ip = os.getenv(AlohaEnvVar.ip.value)
    run_port = os.getenv(AlohaEnvVar.port.value)
    protocol = os.getenv(AlohaEnvVar.protocol.value)
    env = os.environ.copy()
    logger.info(f"Starting up PLC for {protocol} at {run_ip}:{run_port}")
    # The -m flag is necessary to ensure package resolution
    subprocess.run([sys.executable, "-m", "aloha.plc.PLC"],
                   cwd=AppPath, env=env)


def run_hmi():
    """
    Start only the HMI process using the current environment configuration.
    """
    run_ip = os.getenv(AlohaEnvVar.ip.value)
    run_port = os.getenv(AlohaEnvVar.port.value)
    protocol = os.getenv(AlohaEnvVar.protocol.value)
    env = os.environ.copy()
    logger.info(
        f"Starting up HMI for {protocol}, connecting to {run_ip}:{run_port}")
    # The -m flag is necessary to ensure package resolution
    subprocess.run([sys.executable, "-m", "aloha.hmi.HMI"],
                   cwd=AppPath, env=env)


def main():
    load_dotenv()
    configure_logging()

    try:
        # Validate that the configured protocol is recognized.
        protocol: ImplementedProtocol = identifyProtocol()
    except EnvironmentError as e:
        raise EnvironmentError(
            f"Unrecognized protocol {protocol}. Must be one of [{', '.join([p.value for p in ImplementedProtocol])}]")

    # Validate the required network configuration before launching.
    check_environment(AlohaEnvVar.ip,
                      f"You must specify a target IP address using |{AlohaEnvVar.ip.value}|")
    check_environment(AlohaEnvVar.port,
                      f"You must specify a target Port using |{AlohaEnvVar.port.value}|")

    # Launch the component(s) selected by the configured run mode.
    match os.getenv(AlohaEnvVar.runmode.value):
        case "local":
            run_local()
        case "plc":
            run_plc()
        case "hmi":
            run_hmi()
        case _:
            raise EnvironmentError(
                f"Unrecognized {AlohaEnvVar.runmode.value} variable value |{os.getenv(AlohaEnvVar.runmode.value)}|. Must be 'local', 'plc' or 'hmi'")


# Allow this module to be run directly as the environment-aware launcher.
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt detected, shutting down")
