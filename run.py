#!/usr/bin/env python3
import sys
import os
import subprocess
import time

def run_modbus_local():
    port = input("\nEnter port to run on [5020]: ").strip() or "5020"
    
    env = os.environ.copy()
    env["MODBUS_PORT"] = port
    
    print("Starting PLC...")
    plc = subprocess.Popen([sys.executable, "plc.py"], cwd=os.path.join("modbus-sim", "plc"), env=env)
    time.sleep(2)
    print("Starting HMI...")
    try:
        subprocess.run([sys.executable, "HMI.py"], cwd=os.path.join("modbus-sim", "hmi"), env=env)
    except KeyboardInterrupt:
        pass
    finally:
        plc.terminate()
        plc.wait()

def run_modbus_distributed():
    print("\nRun component:\n1. PLC (server)\n2. HMI (web interface)")
    choice = input("\nSelect component: ").strip()
    
    env = os.environ.copy()
    
    if choice == "1":
        ip = input("\nIP to run PLC on [0.0.0.0]: ").strip() or "0.0.0.0"
        port = input("Port to run PLC on [5020]: ").strip() or "5020"
        env["MODBUS_HOST"] = ip
        env["MODBUS_PORT"] = port
        subprocess.run([sys.executable, "plc.py"], cwd=os.path.join("modbus-sim", "plc"), env=env)
    elif choice == "2":
        ip = input("\nIP of PLC to connect to [127.0.0.1]: ").strip() or "127.0.0.1"
        port = input("Port of PLC [5020]: ").strip() or "5020"
        env["MODBUS_HOST"] = ip
        env["MODBUS_PORT"] = port
        subprocess.run([sys.executable, "HMI.py"], cwd=os.path.join("modbus-sim", "hmi"), env=env)

def run_bacnet_distributed():
    print("\nRun component:\n1. PLC (server)\n2. HMI (web interface)")
    choice = input("\nSelect component: ").strip()
    
    env = os.environ.copy()
    
    if choice == "1":
        ip = input("\nIP to run PLC on [127.0.0.1]: ").strip() or "127.0.0.1"
        env["BACNET_IP"] = f"{ip}/24"
        subprocess.run([sys.executable, "plc.py"], cwd=os.path.join("bacnet-sim", "plc"), env=env)
    elif choice == "2":
        ip = input("\nIP of PLC to connect to [127.0.0.1]: ").strip() or "127.0.0.1"
        env["DEVICE_IP"] = ip
        subprocess.run([sys.executable, "HMI.py"], cwd=os.path.join("bacnet-sim", "hmi"), env=env)

def run_modbus():
    print("\nDeployment:\n1. Local\n2. Distributed")
    choice = input("\nSelect deployment: ").strip()
    
    if choice == "1":
        run_modbus_local()
    elif choice == "2":
        run_modbus_distributed()

def run_bacnet():
    run_bacnet_distributed()

def main():
    print("\nAloha Water Treatment Simulator\n\nProtocol:\n1. Modbus\n2. BACnet")
    choice = input("\nSelect protocol: ").strip()
    
    if choice == "1":
        run_modbus()
    elif choice == "2":
        run_bacnet()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("")
