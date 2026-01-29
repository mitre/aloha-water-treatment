# Aloha Water Treatment Simulator

A simplified simulation of a water treatment plant with Modbus and BACnet process control.
Designed to serve as a target for MITRE Caldera for OT.

![Aloha Water Treatment HMI](assets/display.png)

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
| Address | Name               | Description                      |
|---------|--------------------|----------------------------------|
| 0       | emergencyStop      | Emergency stop (1=active)        |
| 1       | pumpSwitch         | Pump switch (1=on)               |
| 2       | pumpStatus         | Pump status (1=running)          |
| 3       | inflowValve        | Inflow valve (1=open)            |
| 4       | outflowValve       | Outflow valve (1=open)           |
| 5       | inflowMode         | Mode select (0=auto, 1=manual)   |
| 6       | overflowAlarm      | Overflow alarm (1=active)        |
| 7       | lowLevelAlarm      | Low level alarm (1=active)       |
| 8       | operatorErrorAlarm | Operator error (1=active)        |

### Holding Registers (Read/Write)
| Address | Name               | Description                      |
|---------|--------------------|----------------------------------|
| 0       | tankLevel          | Tank level (0-10000)             |
| 1       | emergencyStop      | Emergency stop (1=active)        |
| 2       | pumpSwitch         | Pump switch (1=on)               |
| 3       | pumpStatus         | Pump status (1=running)          |
| 4       | inflowValve        | Inflow valve (1=open)            |
| 5       | outflowValve       | Outflow valve (1=open)           |
| 6       | inflowRate         | Inflow rate (L/s)                |
| 7       | outflowRate        | Outflow rate (L/s)               |
| 8       | inflowMode         | Mode select (0=auto, 1=manual)   |
| 9       | overflowAlarm      | Overflow alarm (1=active)        |

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
