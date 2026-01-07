# Aloha Water Treatment Simulator

A simplified simulation of a water treatment plant with Modbus and BACnet process control.
Designed to serve as a target for MITRE Caldera for OT.

![Aloha Water Treatment HMI](display.png)

## Description

This simulator provides a Modbus and BACnet-enabled water treatment plant for testing and
training. It includes PLC servers and web-based HMIs, useful for practicing
protocol interactions without physical hardware.

## Getting Started

### Dependencies

* Python 3
* Flask, BAC0, pymodbus (see requirements.txt)

### Installation

1. Clone this repo:
```bash
git clone https://github.com/mitre/aloha-water-treatment.git
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the simulator:
```bash
python run.py
```

## Usage

Follow the steps below to interact with the Aloha Water Treatment control
system using the web interface or protocol clients:

### Step 1: Start the Simulator
```bash
python run.py
```

Select your deployment mode from the menu:

**Modbus**
*   **Local**: Runs both PLC and HMI on the same system
    *   Prompts for port selection (502 or 5020, default 5020)
*   **Distributed**: Runs PLC or HMI separately on different systems
    *   For PLC: Prompts for bind IP address (default 0.0.0.0) and port (502 or 5020, default 5020)
    *   For HMI: Prompts for PLC IP address to connect to (default 127.0.0.1) and port (default 5020)
*   Note: Port 502 is the standard Modbus port but requires root/admin privileges
*   PLC listens on selected port, HMI runs on port 8090

**BACnet**
*   **Distributed**: Runs PLC or HMI separately (required for BACnet)
    *   For PLC: Prompts for PLC IP address (default 127.0.0.1, automatically adds /24)
    *   For HMI: Prompts for PLC IP address to connect to (default 127.0.0.1)
*   PLC uses BACnet device ID 1001, HMI runs on port 8090
*   Note: BACnet components must run on separate endpoints

## Modbus Register Map

The Modbus PLC exposes the following registers on port 5020:

### Coils (Read/Write)
| Address | Name | Description |
|---------|------|-------------|
| 0 | COIL_ESTOP | Emergency Stop (1 = Active) |
| 1 | COIL_SWITCH | Pump Switch (1 = On) |
| 2 | COIL_PUMP | Pump Status (1 = Running) |
| 3 | COIL_IN_VALVE | Inflow Valve (1 = Open) |
| 4 | COIL_OUT_VALVE | Outflow Valve (1 = Open) |
| 5 | COIL_AUTO | Auto Mode (1 = Auto, 0 = Manual) |
| 6 | COIL_ALARM | Overflow Alarm (1 = Active) |
| 7 | COIL_LOW_LEVEL_ALARM | Low Level Alarm (1 = Active) |
| 8 | COIL_OPERATOR_ERROR_ALARM | Operator Error Alarm (1 = Active) |

### Holding Registers (Read/Write)
| Address | Name | Description |
|---------|------|-------------|
| 0 | HR_LEVEL | Tank Level (0-10000) |
| 1 | HR_ESTOP | Emergency Stop Status |
| 2 | HR_SWITCH | Pump Switch Status |
| 3 | HR_PUMP | Pump Status |
| 4 | HR_IN_VALVE | Inflow Valve Status |
| 5 | HR_OUT_VALVE | Outflow Valve Status |
| 6 | HR_IN_FLOW | Inflow Rate |
| 7 | HR_OUT_FLOW | Outflow Rate |
| 8 | HR_AUTO | Auto Mode Status |
| 9 | HR_ALARM | Alarm Status |

## BACnet Object List

The BACnet PLC exposes the following objects (Device ID 1001):

### Analog Values
| Instance | Name | Description |
|----------|------|-------------|
| 1 | TankLevel | Treatment tank water level |
| 2 | InflowRate | Inlet flow rate |
| 3 | OutflowRate | Outlet flow rate |

### Binary Values
| Instance | Name | Description |
|----------|------|-------------|
| 1 | EmergencyStop | Emergency stop button |
| 2 | PumpSwitch | Main pump switch |
| 3 | AutoMode | Auto/Manual mode (False=Auto, True=Manual) |

### Binary Outputs
| Instance | Name | Description |
|----------|------|-------------|
| 1 | PumpStatus | Pump operational state |
| 2 | InflowValve | Inlet valve state |
| 3 | OutflowValve | Outlet valve state |
| 4 | OverflowAlarm | High level alarm |
| 5 | LowLevelAlarm | Low level alarm |
| 6 | OperatorErrorAlarm | Operator error / safety violation |
