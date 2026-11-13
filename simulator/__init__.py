SIM = {
    "name": "Aloha Water Treatment",
    "protocols": {
        "modbus": {"name": "Modbus", "port": 5020, "bind": "0.0.0.0", "local": True},
        "bacnet": {"name": "BACnet", "port": 47808, "bind": "auto", "local": False},
    },
    "web_optional": False,
    "test_client": None,
}
