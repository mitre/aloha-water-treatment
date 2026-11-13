# Scenario 2: Manual Overflow

## Overview

| Field | Value |
|---|---|
| **Tactic** | Impair Process Control, Impact |
| **Techniques** | [T0855 - Unauthorized Command Message](https://attack.mitre.org/techniques/T0855/), [T0831 - Manipulation of Control](https://attack.mitre.org/techniques/T0831/), [T0826 - Loss of Availability](https://attack.mitre.org/techniques/T0826/) |
| **Adversary** | Aloha Modbus Manual Overflow (`docs/adversaries/modbus-manual-overflow.yml`), Aloha BACnet Manual Overflow (`docs/adversaries/bacnet-manual-overflow.yml`) |
| **Fact source** | Aloha Water Treatment Facts (`docs/sources/aloha-simulator-facts.yml`) |

## Description

The adversary turns the pump on, switches the plant to manual mode, and sets the inflow far above the outflow. In automatic mode the PLC keeps the tank near two thirds full, but in manual mode it takes the written flow rates as given, so the tank fills until it overflows.

![Aloha Water Treatment HMI manual overflow state](../images/scenario-2-manual-overflow.png)

## Modbus Variant

### Facts Used

| Fact | Description | Type | Value |
|---|---|---|---|
| `modbus.server.ip` | IP address of the Modbus PLC | string | `127.0.0.1` |
| `modbus.server.port` | TCP port of the Modbus PLC | int | `5020` |
| `modbus.read_coil.start` | First coil to read | int | `0` |
| `modbus.read_coil.count` | Number of coils to read | int | `9` |
| `modbus.read_holding.start` | First holding register to read | int | `0` |
| `modbus.read_holding.count` | Number of holding registers to read | int | `10` |
| `modbus.write_coil.start` | Coil to write | int | `1` (PumpSwitch), `5` (InflowMode) |
| `modbus.write_coil.value` | Coil value to write | string | `ON` |
| `modbus.write_register.start` | Holding register to write | int | `6` (InflowRate), `7` (OutflowRate) |
| `modbus.write_register.value` | Holding register value to write | int | `900` (high inflow), `50` (low outflow) |

### Control Data

| Control | Modbus Address | Value |
|---|---|---|
| PumpSwitch | Coil `1` | `ON` |
| InflowMode | Coil `5` | `ON` (manual) |
| InflowRate | Holding register `6` | `900` |
| OutflowRate | Holding register `7` | `50` |

### Steps

Run the adversary with the fact source above, or add these abilities to an operation in this order:

| # | Ability | ID | Facts |
|---|---|---|---|
| 1 | Modbus - Read Coils | `d80b9cd5-b1d8-482a-a745-71d74f9d0885` | baseline: `modbus.read_coil.start=0`, `modbus.read_coil.count=9` |
| 2 | Modbus - Write Single Coil | `056e6289-4cbf-417f-928a-d75125e4db4f` | pump on: `modbus.write_coil.start=1`, `modbus.write_coil.value=ON` |
| 3 | Modbus - Write Single Coil | `056e6289-4cbf-417f-928a-d75125e4db4f` | manual mode: `modbus.write_coil.start=5`, `modbus.write_coil.value=ON` |
| 4 | Modbus - Write Single Register | `d6991b6b-d3b2-4398-ad3f-d736ae09acf9` | inflow: `modbus.write_register.start=6`, `modbus.write_register.value=900` |
| 5 | Modbus - Write Single Register | `d6991b6b-d3b2-4398-ad3f-d736ae09acf9` | outflow: `modbus.write_register.start=7`, `modbus.write_register.value=50` |
| 6 | Modbus - Read Holding Registers | `bc8961a2-7534-4b2a-bbc3-2456f58243be` | verify: `modbus.read_holding.start=0`, `modbus.read_holding.count=10` |
| 7 | Modbus - Read Coils | `d80b9cd5-b1d8-482a-a745-71d74f9d0885` | verify: `modbus.read_coil.start=0`, `modbus.read_coil.count=9` |

## BACnet Variant

### Facts Used

| Fact | Description | Type | Value |
|---|---|---|---|
| `bacnet.device.instance` | Device instance of the BACnet PLC | int | `1001` |
| `bacnet.obj.type` | Object type to write | string | `binary-value`, `analog-value` |
| `bacnet.obj.instance` | Object instance to write | int | `2` (PumpSwitch, InflowRate), `3` (ManualMode, OutflowRate) |
| `bacnet.obj.property` | Property to write | string | `present-value` |
| `bacnet.write.priority` | Write priority | int | `8` (manual operator, the same as the HMI) |
| `bacnet.write.index` | Array index to write | int | `-1` (whole property) |
| `bacnet.write.tag` | Application tag of the value | int | `9` (enumerated, binary values), `4` (real, analog values) |
| `bacnet.write.value` | Value to write | int | `1` (active), `900` (high inflow), `50` (low outflow) |
| `bacnet.object.type` | Object type for Object Collection | string | `analog-value`, `binary-output` |
| `bacnet.object.instance` | Object instance for Object Collection | int | `1` (TankLevel, PumpStatus), `4` (OverflowAlarm) |

### Control Data

| Control | BACnet Object | Value |
|---|---|---|
| PumpSwitch | `binary-value 2 present-value` | `active` |
| ManualMode | `binary-value 3 present-value` | `active` |
| InflowRate | `analog-value 2 present-value` | `900` |
| OutflowRate | `analog-value 3 present-value` | `50` |

### Steps

Run the adversary with the fact source above, or add these abilities to an operation in this order:

| # | Ability | ID | Facts |
|---|---|---|---|
| 1 | BACnet Object Collection - Basic | `bd13ac81-b932-463d-95aa-a22aeefbc9ac` | baseline: `bacnet.object.type=analog-value`, `bacnet.object.instance=1` |
| 2 | BACnet Write Property | `1a2faf5a-4601-11eb-b378-0242ac130002` | pump on: `bacnet.obj.type=binary-value`, `bacnet.obj.instance=2`, `bacnet.write.tag=9`, `bacnet.write.value=1` |
| 3 | BACnet Write Property | `1a2faf5a-4601-11eb-b378-0242ac130002` | manual mode: `bacnet.obj.type=binary-value`, `bacnet.obj.instance=3`, `bacnet.write.tag=9`, `bacnet.write.value=1` |
| 4 | BACnet Write Property | `1a2faf5a-4601-11eb-b378-0242ac130002` | inflow: `bacnet.obj.type=analog-value`, `bacnet.obj.instance=2`, `bacnet.write.tag=4`, `bacnet.write.value=900` |
| 5 | BACnet Write Property | `1a2faf5a-4601-11eb-b378-0242ac130002` | outflow: `bacnet.obj.type=analog-value`, `bacnet.obj.instance=3`, `bacnet.write.tag=4`, `bacnet.write.value=50` |
| 6 | BACnet Object Collection - Basic | `bd13ac81-b932-463d-95aa-a22aeefbc9ac` | verify: `bacnet.object.type=analog-value`, `bacnet.object.instance=1` |

## Expected Observations

- The PLC accepts every write without authentication and logs each one (`Client wrote ...`). The BACnet PLC logs a write only when it changes the value.
- The pump switch and manual mode turn on: Modbus coils 1 and 5 read `ON`, and the HMI shows the pump running in manual mode.
- The inflow rate reads `900` and the outflow rate `50` (Modbus holding registers 6 and 7, BACnet `analog-value` 2 and 3), so the tank level rises by 850 each second.
- Once the level passes 9000 with inflow still on, the operator error alarm turns on. When the level reaches 10000, the overflow alarm turns on for one cycle and the PLC cuts the inflow to `0`.
- After the overflow the level falls by 50 each second. The verify reads show the tank level between 9000 and 10000 and an inflow of `0`, or a rising level if the tank has not filled yet.
