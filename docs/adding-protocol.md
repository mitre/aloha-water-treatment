# Adding a Protocol

Aloha keeps the water treatment logic separate from the protocol used to expose it. A protocol implementation has two parts:

* a PLC server under `aloha/<protocol>/<protocol>_plc.py`
* an HMI client under `aloha/<protocol>/<protocol>_hmi.py`

The Modbus implementation is the synchronous example. The BACnet implementation is the asynchronous example.

## Source Tree

The protocol layer sits on top of shared code:

* `aloha/constants.py` contains shared environment and protocol names
* `aloha/plc/` contains the plant simulation and PLC interface
* `aloha/hmi/` contains the Flask frontend and HMI client interface

## File Layout

For a new protocol named `foo`, add:

```text
aloha/foo/
aloha/foo/__init__.py
aloha/foo/foo_plc.py
aloha/foo/foo_hmi.py
```

Then add the protocol name to `ImplementedProtocol` in `aloha/constants.py`:

```python
class ImplementedProtocol(StrEnum):
    BACNET = "bacnet"
    MODBUS = "modbus"
    FOO = "foo"
```

The launcher uses that value to import `aloha.foo.foo_plc` and `aloha.foo.foo_hmi`.

## PLC Side

The PLC module needs a `create_plc()` function that returns an object matching `PLCProtocolInterface` from `aloha/plc/PLC.py`.

At a high level, the PLC should:

* create protocol-specific objects or registers in `setup_plc()`
* read operator or client values into `self.context`
* call `simulation_step(self.context)` once per tick
* write updated simulation values back to the protocol objects
* sleep about one second between ticks

Minimal shape:

```python
import time

from aloha.plc.PLC import PLCProtocolInterface
from aloha.plc.plc_simulation import SimulationContext, simulation_step


class FooPLCInterface(PLCProtocolInterface):
    context: SimulationContext = SimulationContext()
    is_active: bool = True

    def setup_plc(self) -> None:
        ...

    def run_server(self) -> None:
        while self.is_active:
            self.update_simulation_from_plc()
            simulation_step(self.context)
            self.update_plc_from_simulation()
            time.sleep(1)

    def handle_signal(self, sig: int, frame: object | None) -> None:
        self.is_active = False

    def update_simulation_from_plc(self) -> None:
        ...

    def update_plc_from_simulation(self) -> None:
        ...


def create_plc() -> PLCProtocolInterface:
    return FooPLCInterface()
```

## HMI Side

The HMI module needs a `create_hmi_client()` function that returns an object matching `HMIClientInterface` from `aloha/hmi/HMI.py`.

The HMI client should:

* connect to the protocol server in `initialize_client()`
* keep a local `SimulationContext` updated for the web UI
* implement the five command methods used by the frontend:
  * `set_estop`
  * `set_inflow`
  * `set_outflow`
  * `set_pumpSwitch`
  * `set_manualMode`

The generic HMI interface handles command validation and routing. As long as those five methods are implemented, the existing frontend can call into the new protocol without changing the Flask routes.

Minimal shape:

```python
from aloha.hmi.HMI import HMIClientInterface
from aloha.plc.plc_simulation import SimulationContext


class FooClient(HMIClientInterface):
    simulation: SimulationContext = SimulationContext()

    def initialize_client(self):
        ...

    def hmi_update_loop(self):
        ...

    def read_simulation_from_server(self):
        ...

    def set_estop(self, value: bool) -> bool:
        ...

    def set_inflow(self, value: float) -> bool:
        ...

    def set_outflow(self, value: float) -> bool:
        ...

    def set_pumpSwitch(self, value: bool) -> bool:
        ...

    def set_manualMode(self, value: bool) -> bool:
        ...


def create_hmi_client() -> HMIClientInterface:
    return FooClient()
```

## Simulation Context

The shared plant state lives in `aloha/plc/plc_simulation.py`. Protocol code should translate between its own objects and `SimulationContext`, then let `simulation_step()` handle the plant behavior.

Command and status values:

* `estop`
* `pswitch`
* `pstatus`
* `in_valve`
* `out_valve`
* `manual_op`
* `of_alarm`
* `ll_alarm`
* `oe_alarm`

Process values:

* `level`
* `in_flow`
* `out_flow`
