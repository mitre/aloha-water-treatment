"""
Address helpers shared by the PLC and the HMI.

BACnet/IP broadcasts (Who-Is) only reach the device when its address carries the
subnet mask, so "auto" reads both the IP and the mask from the interface.
"""

import socket


def primary_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        # No route (no default gateway): fall back to loopback.
        return "127.0.0.1"
    finally:
        s.close()


def primary_prefix(ip, default=24):
    try:
        import fcntl
        import struct
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            for _, name in socket.if_nameindex():
                req = struct.pack("256s", name.encode()[:15])
                try:
                    if socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, req)[20:24]) == ip:
                        mask = fcntl.ioctl(s.fileno(), 0x891B, req)[20:24]
                        return bin(int.from_bytes(mask, "big")).count("1")
                except OSError:
                    continue
        finally:
            s.close()
    except (ImportError, OSError):
        pass
    return default


def resolve_address(address):
    """Return "ip/prefix". "auto" uses this host's primary interface and its mask."""
    if address.split("/")[0] == "auto":
        ip = primary_ip()
        prefix = address.split("/")[1] if "/" in address else primary_prefix(ip)
        return f"{ip}/{prefix}"
    if "/" not in address:
        return f"{address}/24"
    return address
