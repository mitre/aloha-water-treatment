# Adding a Protocol

Aloha keeps the water treatment logic separate from the protocol used to expose it. A protocol implementation has two parts:

* a PLC server under `simulator/<protocol>/<protocol>_plc.py`
* an HMI client under `simulator/<protocol>/<protocol>_hmi.py`

The Modbus and BACnet implementations are working examples of both parts.

## Source Tree

The protocol layer sits on top of shared code:

* `simulator/__init__.py` contains `SIM`, with each protocol's menu name, default port and default bind address
* `simulator/config.py` contains the environment variable names, logging setup and the command line
* `simulator/network.py` contains the address helpers the BACnet PLC and HMI use
* `simulator/sim.py` contains the plant simulation
* `simulator/plc.py` contains the PLC interface
* `simulator/hmi.py` contains the Flask frontend and HMI client interface
* `simulator/ui/` contains the frontend templates and static assets

## File Layout

For a new protocol named `foo`, add:

```text
simulator/foo/
simulator/foo/__init__.py
simulator/foo/foo_plc.py
simulator/foo/foo_hmi.py
```

Then add it to `SIM["protocols"]` in `simulator/__init__.py`:

```python
"foo": {"name": "Foo", "port": 1234, "bind": "0.0.0.0", "local": True},
```

`local` says whether the PLC and the HMI can share one host. `python -m simulator.plc --protocol foo` then imports `simulator.foo.foo_plc`, `python -m simulator.hmi --protocol foo` imports `simulator.foo.foo_hmi`, and `run.py` offers Foo in its protocol menu.

## PLC Side

The PLC module needs a `create_plc(host, port)` function that returns an object matching `PLCProtocolInterface` from `simulator/plc.py`.

At a high level, the PLC should:

* create protocol-specific objects or registers in `setup_plc()`
* in `run_server()`, log `PLC listening on <host>:<port>` once the server is bound, or return `1` if it cannot start
* read operator or client values into `self.context`
* call `simulation_step(self.context)` once per tick
* write updated simulation values back to the protocol objects
* sleep about one second between ticks
* on SIGINT or SIGTERM, stop the loop, log `Stopped` and return `0`

Minimal shape:

```python
import logging
import time

from simulator.plc import PLCProtocolInterface
from simulator.sim import SimulationContext, simulation_step


logger = logging.getLogger(__name__)


class FooPLCInterface(PLCProtocolInterface):
    context: SimulationContext = SimulationContext()
    is_active: bool = True

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def setup_plc(self) -> None:
        ...

    def run_server(self) -> int:
        ...
        logger.info(f"PLC listening on {self.host}:{self.port}")
        while self.is_active:
            self.update_simulation_from_plc()
            simulation_step(self.context)
            self.update_plc_from_simulation()
            time.sleep(1)
        logger.info("Stopped")
        return 0

    def handle_signal(self, sig: int, frame: object | None) -> None:
        self.is_active = False

    def update_simulation_from_plc(self) -> None:
        ...

    def update_plc_from_simulation(self) -> None:
        ...


def create_plc(host: str, port: int) -> PLCProtocolInterface:
    return FooPLCInterface(host, port)
```

## HMI Side

The HMI module needs a `create_hmi_client()` function that returns an object matching `HMIClientInterface` from `simulator/hmi.py`.

The HMI client should:

* connect to the PLC at the given host and port in `initialize_client(host, port, client_cidr)`; `client_cidr` is the prefix length for a protocol that binds its own client address, as BACnet does, and other protocols ignore it
* keep a local `SimulationContext` updated for the web UI
* implement the five command methods used by the frontend, each returning `True` if the PLC accepted the write and `False` if it did not:
  * `set_estop`
  * `set_inflow`
  * `set_outflow`
  * `set_pumpSwitch`
  * `set_manualMode`

The generic HMI interface handles command validation and routing. As long as those five methods are implemented, the existing frontend can call into the new protocol without changing the Flask routes.

Minimal shape:

```python
from simulator.hmi import HMIClientInterface
from simulator.sim import SimulationContext


class FooClient(HMIClientInterface):
    simulation: SimulationContext = SimulationContext()

    def initialize_client(self, host: str, port: int, client_cidr: int | None = None):
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

The shared plant state lives in `simulator/sim.py`. Protocol code should translate between its own objects and `SimulationContext`, then let `simulation_step()` handle the plant behavior.

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
