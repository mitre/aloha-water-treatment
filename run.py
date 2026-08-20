#!/usr/bin/env python3
"""
Aloha Water Treatment Plant startup script
Run the treatment plant with an interactive startup script
"""

import logging
import sys
import os
import subprocess
import time

from pathlib import Path
from aloha.constants import AlohaEnvVar, ImplementedProtocol, configure_logging

AppPath = Path(__file__).parent.absolute()  
logger = logging.getLogger(__name__)


def run_local(env: dict[str:str]) -> None:
    """
    Start both the PLC and HMI locally using the provided environment.

    The PLC is started as a background subprocess first, then the HMI is run in
    the foreground. When the HMI exits, the PLC process is terminated.

    Args:
        env: Environment variables to pass to both subprocesses.
    """
    logger.info("Starting PLC locally")
    # The -m flag is necessary to ensure package resolution
    plc = subprocess.Popen(
        [sys.executable, "-m", "aloha.plc.PLC"], cwd=AppPath, env=env)
    time.sleep(2)
    logger.info("Starting HMI locally")
    # The -m flag is necessary to ensure package resolution
    try:
        subprocess.run([sys.executable, "-m", "aloha.hmi.HMI"],
                       cwd=AppPath, env=env)
    except KeyboardInterrupt:
        pass
    finally:
        # Ensure the PLC subprocess is stopped when the local session ends.
        plc.terminate()
        plc.wait()


def run_plc(env: dict[str:str]):
    """
    Start only the PLC process using the current environment configuration.

    Args:
        env: Environment variables to pass to the PLC subprocess.
    """
    run_ip   = env[AlohaEnvVar.ip.value]
    run_port = env[AlohaEnvVar.port.value]
    protocol = env[AlohaEnvVar.protocol.value]
    logger.info(f"Starting up PLC for {protocol} at {run_ip}:{run_port}")
    # The -m flag is necessary to ensure package resolution
    subprocess.run([sys.executable, "-m", "aloha.plc.PLC"],
                   cwd=AppPath, env=env)


def run_hmi(env: dict[str:str]):
    """
    Start only the HMI process using the current environment configuration.

    Args:
        env: Environment variables to pass to the HMI subprocess.
    """
    run_ip   = env[AlohaEnvVar.ip.value]
    run_port = env[AlohaEnvVar.port.value]
    protocol = env[AlohaEnvVar.protocol.value]
    logger.info(
        f"Starting up HMI for {protocol}, connecting to {run_ip}:{run_port}")
    # The -m flag is necessary to ensure package resolution
    subprocess.run([sys.executable, "-m", "aloha.hmi.HMI"],
                   cwd=AppPath, env=env)


def select_protocol(env: dict[str:str]) -> None:
    """
    Prompt the user to select the OT protocol and store it in the environment.

    Args:
        env: Mutable environment mapping updated with the selected protocol.
    """
    options = {str(i): protocol for i, protocol in enumerate(ImplementedProtocol)}
    options_str = "\n".join([f"{i}. {protocol.name}" for i, protocol in enumerate(ImplementedProtocol)])
    print( f"Aloha Water Treatment Simulator\n\nProtocol:\n{options_str}" )
    while True: 
        protocol_choice = input("\n Select protocol: ").strip()
        if protocol_choice in options:
            env[AlohaEnvVar.protocol.value] = options[protocol_choice]
            return
        print(f"Unrecognized choice {protocol_choice}")


def select_runmode(env: dict[str:str]) -> None:
    """
    Prompt the user to select the deployment mode and store it in the environment.

    Args:
        env: Mutable environment mapping updated with the selected run mode.
    """
    options = {"1": "local", "2": "plc", "3": "hmi"}
    print("\nDeployment:\n1. Local (HMI+PLC)\n2. Distributed (PLC)\n3. Distributed (HMI)")
    while True:
        runmode_choice = input("\n Select runmode: ").strip()
        if runmode_choice in options:
            env[AlohaEnvVar.runmode.value] = options[runmode_choice]
            return
        print(f"Unrecognized choice {runmode_choice}")
    

def select_host(env: dict[str:str]) -> None:
    """
    Prompt the user for the PLC host address and store it in the environment.

    Args:
        env: Mutable environment mapping updated with the selected host.
    """
    host_address = input("\nIP to run PLC on [127.0.0.1]: ").strip() or "127.0.0.1"
    env[AlohaEnvVar.ip.value] = host_address


def select_port(env: dict[str:str]) -> None:
    """
    Prompt the user for the PLC port and store it in the environment.

    Args:
        env: Mutable environment mapping updated with the selected port.
    """
    while True: 
        host_port = input("Port to run PLC on [>0]: ").strip()
        try:
            if int(host_port) >= 0:
                env[AlohaEnvVar.port.value] = host_port
                return
        except (ValueError, AssertionError):
            print(f"'{host_port}' is not a positive integer")


def main():
    """
    Collect runtime configuration from the user and launch using the selected mode.
    """
    # Start from the current process environment and extend it with user input.
    env = os.environ.copy()
    select_protocol(env)
    select_runmode(env)
    select_host(env)
    select_port(env)

    configure_logging()

    # Launch the component(s) selected by the configured run mode.
    match env[AlohaEnvVar.runmode.value]:
        case "local":
            run_local(env)
        case "plc":
            run_plc(env)
        case "hmi":
            run_hmi(env)
        case _:
            raise EnvironmentError(
                f"Unrecognized value |{os.getenv(AlohaEnvVar.runmode.value)}| for runmode. Must be 'local', 'plc' or 'hmi'")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("Keyboard interrupt detected, shutting down simulation")
