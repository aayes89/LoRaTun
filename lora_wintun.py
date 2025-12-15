import os
import time
import struct
import serial
import time
import socket
import threading
import argparse
import logging
import ctypes
import subprocess

# ---------------- CONFIG ----------------

DEFAULT_PORT = "COM12"
DEFAULT_BAUD = 115200
DEFAULT_IP = "10.10.0.1"
PEER_IP    = "10.10.0.2"
DEFAULT_MTU = 120

# Nuevos
MAGIC = 0xA5

def build_frame(seq, total, data):
    header = struct.pack("<BBHHH",
        MAGIC,
        0x01,
        seq,
        total,
        len(data)
    )
    crc = crc16(header + data)
    return header + data + struct.pack("<H", crc)
def parse_frame(raw):
    if len(raw) < 10:
        return None
    magic, ftype, seq, total, length = struct.unpack("<BBHHH", raw[:8])
    if magic != MAGIC:
        return None
    data = raw[8:8+length]
    crc_recv = struct.unpack("<H", raw[8+length:10+length])[0]
    if crc16(raw[:8+length]) != crc_recv:
        return None
    return ftype, seq, total, data


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc

# ---------------- LOG ----------------

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger("lora-wintun")

# ---------------- WINTUN ----------------

#wintun = ctypes.WinDLL("wintun.dll")
dll_path = os.path.join(os.path.dirname(__file__), "wintun.dll")
wintun = ctypes.WinDLL(dll_path)


class WINTUN_ADAPTER(ctypes.Structure):
    pass

class WINTUN_SESSION(ctypes.Structure):
    pass

wintun.WintunCreateAdapter.argtypes = [
    ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p
]
wintun.WintunCreateAdapter.restype = ctypes.POINTER(WINTUN_ADAPTER)

wintun.WintunStartSession.argtypes = [
    ctypes.POINTER(WINTUN_ADAPTER), ctypes.c_uint32
]
wintun.WintunStartSession.restype = ctypes.POINTER(WINTUN_SESSION)

wintun.WintunAllocateSendPacket.argtypes = [
    ctypes.POINTER(WINTUN_SESSION), ctypes.c_uint32
]
wintun.WintunAllocateSendPacket.restype = ctypes.c_void_p

wintun.WintunSendPacket.argtypes = [
    ctypes.POINTER(WINTUN_SESSION), ctypes.c_void_p
]

wintun.WintunReceivePacket.argtypes = [
    ctypes.POINTER(WINTUN_SESSION), ctypes.POINTER(ctypes.c_uint32)
]
wintun.WintunReceivePacket.restype = ctypes.c_void_p

wintun.WintunReleaseReceivePacket.argtypes = [
    ctypes.POINTER(WINTUN_SESSION), ctypes.c_void_p
]

# ---------------- SERIAL ----------------

def open_serial(port, baud):
    ser = serial.Serial(port, baud, timeout=0.1)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    return ser

# ---------------- CONFIG IP ----------------

def config_ip(adapter_name, ip):
    ps = f"""
    $if = Get-NetAdapter | Where-Object {{$_.Name -eq "{adapter_name}"}}
    if ($if) {{
        # borrar IP previa si existe
        Get-NetIPAddress -InterfaceIndex $if.ifIndex `
            -AddressFamily IPv4 `
            -ErrorAction SilentlyContinue | `
            Where-Object {{$_.IPAddress -eq "{ip}"}} | `
            Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue

        # asignar IP
        New-NetIPAddress `
            -InterfaceIndex $if.ifIndex `
            -IPAddress "{ip}" `
            -PrefixLength 24 `
            -AddressFamily IPv4 `
            -ErrorAction SilentlyContinue
    }}
    """
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

# ---------------- TUN -> SERIAL ----------------
def tun_to_serial1(session, ser, mtu):
    ip_mtu = mtu - 20
    seq_id = 0

    while True:
        size = ctypes.c_uint32()
        pkt = wintun.WintunReceivePacket(session, ctypes.byref(size))
        if not pkt:
            time.sleep(0.001)
            continue

        ip_packet = ctypes.string_at(pkt, size.value)
        wintun.WintunReleaseReceivePacket(session, pkt)

        fragments = [
            ip_packet[i:i+ip_mtu]
            for i in range(0, len(ip_packet), ip_mtu)
        ]

        total = len(fragments)

        for i, frag in enumerate(fragments):
            frame = build_frame(i, total, frag)
            ser.write(struct.pack("<H", len(frame)))
            ser.write(frame)

def tun_to_serial(session, ser, mtu):
    ip_mtu = mtu - 2

    while True:
        size = ctypes.c_uint32()
        pkt = wintun.WintunReceivePacket(session, ctypes.byref(size))
        if not pkt:
            time.sleep(0.001)
            continue

        data = ctypes.string_at(pkt, size.value)
        wintun.WintunReleaseReceivePacket(session, pkt)

        if 0 < len(data) <= ip_mtu:
            ser.write(struct.pack("<H", len(data)))
            ser.write(data)

# ---------------- SERIAL -> TUN ----------------
rx_buffer = {}
rx_expected = {}

def serial_to_tun1(session, ser, mtu):
    buf = bytearray()

    while True:
        buf.extend(ser.read(256))

        while len(buf) >= 2:
            size = struct.unpack("<H", buf[:2])[0]
            if len(buf) < 2 + size:
                break

            frame = buf[2:2+size]
            parsed = parse_frame(frame)
            del buf[:2+size]

            if not parsed:
                continue

            ftype, seq, total, data = parsed

            if ftype != 0x01:
                continue

            rx_buffer.setdefault(total, {})[seq] = data

            if len(rx_buffer[total]) == total:
                packet = b''.join(
                    rx_buffer[total][i] for i in range(total)
                )

                pkt = wintun.WintunAllocateSendPacket(session, len(packet))
                ctypes.memmove(pkt, packet, len(packet))
                wintun.WintunSendPacket(session, pkt)

                del rx_buffer[total]

def serial_to_tun(session, ser, mtu):
    buf = bytearray()
    ip_mtu = mtu - 2

    while True:
        buf.extend(ser.read(128))

        while len(buf) >= 2:
            size = struct.unpack("<H", buf[:2])[0]

            if size == 0 or size > ip_mtu:
                buf.pop(0)
                continue

            if len(buf) < 2 + size:
                break

            payload = bytes(buf[2:2+size])

            pkt = wintun.WintunAllocateSendPacket(session, size)
            ctypes.memmove(pkt, payload, size)
            wintun.WintunSendPacket(session, pkt)

            del buf[:2+size]

# ---------------- MAIN ----------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument("--peer", default=PEER_IP)
    parser.add_argument("--mtu", type=int, default=DEFAULT_MTU)
    args = parser.parse_args()

    ser = open_serial(args.port, args.baud)   
    
    adapter = wintun.WintunCreateAdapter("LoRaTun", "LoRa", None)
    if not adapter:
        raise RuntimeError("No se pudo crear Wintun adapter")

    session = wintun.WintunStartSession(adapter, 0x400000)
    if not session:
        raise RuntimeError("No se pudo iniciar sesión Wintun")

    config_ip("LoRaTun", args.ip)

    t1 = threading.Thread(
        target=tun_to_serial, args=(session, ser, args.mtu), daemon=True
    )
    t2 = threading.Thread(
        target=serial_to_tun, args=(session, ser, args.mtu), daemon=True
    )

    t1.start()
    t2.start()

    log.info("Wintun activo")
    log.info("Prueba: ping %s", args.peer)

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
