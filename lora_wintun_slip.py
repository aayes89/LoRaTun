import os
import time
import struct
import serial
import socket
import threading
import ctypes
import subprocess

# ---------- CONFIG ----------
PORT = "COM12"
BAUD = 115200
IP_LOCAL = "10.10.0.1"
IP_PEER  = "10.10.0.2"
MTU = 576

# ---------- SLIP ----------
SLIP_END = 0xC0
SLIP_ESC = 0xDB
SLIP_ESC_END = 0xDC
SLIP_ESC_ESC = 0xDD

def slip_encode(pkt: bytes) -> bytes:
    out = bytearray([SLIP_END])
    for b in pkt:
        if b == SLIP_END:
            out += bytes([SLIP_ESC, SLIP_ESC_END])
        elif b == SLIP_ESC:
            out += bytes([SLIP_ESC, SLIP_ESC_ESC])
        else:
            out.append(b)
    out.append(SLIP_END)
    return bytes(out)

def slip_decoder():
    buf = bytearray()
    esc = False
    while True:
        b = yield None
        if b == SLIP_END:
            if buf:
                yield bytes(buf)
                buf.clear()
            continue
        if esc:
            buf.append(SLIP_END if b == SLIP_ESC_END else SLIP_ESC)
            esc = False
            continue
        if b == SLIP_ESC:
            esc = True
            continue
        buf.append(b)

# ---------- WINTUN ----------
dll = ctypes.WinDLL(os.path.join(os.path.dirname(__file__), "wintun.dll"))

class ADAPTER(ctypes.Structure): pass
class SESSION(ctypes.Structure): pass

dll.WintunCreateAdapter.argtypes = [
    ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p
]
dll.WintunCreateAdapter.restype = ctypes.c_void_p

dll.WintunStartSession.argtypes = [
    ctypes.c_void_p, ctypes.c_uint32
]
dll.WintunStartSession.restype = ctypes.c_void_p

dll.WintunReceivePacket.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)
]
dll.WintunReceivePacket.restype = ctypes.c_void_p

dll.WintunReleaseReceivePacket.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p
]
dll.WintunReleaseReceivePacket.restype = None

dll.WintunAllocateSendPacket.argtypes = [
    ctypes.c_void_p, ctypes.c_uint32
]
dll.WintunAllocateSendPacket.restype = ctypes.c_void_p

dll.WintunSendPacket.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p
]
dll.WintunSendPacket.restype = None


dll.WintunCreateAdapter.restype = ctypes.POINTER(ADAPTER)
dll.WintunStartSession.restype = ctypes.POINTER(SESSION)
dll.WintunReceivePacket.restype = ctypes.c_void_p

adapter = dll.WintunCreateAdapter("LoRaTun", "LoRa", None)
if not adapter:
    raise RuntimeError("No se pudo crear adapter")

session = dll.WintunStartSession(adapter, 0x400000)
if not session:
    raise RuntimeError("No se pudo iniciar sesión")


subprocess.run([
    "powershell", "-Command",
    f'New-NetIPAddress -InterfaceAlias "LoRaTun" '
    f'-IPAddress {IP_LOCAL} -PrefixLength 24 -ErrorAction SilentlyContinue'
], stdout=subprocess.DEVNULL)

ser = serial.Serial(PORT, BAUD, timeout=0.1)

# ---------- TUN → SERIAL ----------
def tun_to_serial():
    while True:
        size = ctypes.c_uint32()
        pkt = dll.WintunReceivePacket(session, ctypes.byref(size))
        if not pkt:
            time.sleep(0.001)
            continue

        ip = ctypes.string_at(pkt, size.value)
        dll.WintunReleaseReceivePacket(session, pkt)

        if ip[0] >> 4 != 4:
            continue

        ser.write(slip_encode(ip))

# ---------- SERIAL → TUN ----------
def serial_to_tun():
    dec = slip_decoder()
    next(dec)

    while True:
        data = ser.read(256)
        for b in data:
            pkt = dec.send(b)
            if pkt:
                out = dll.WintunAllocateSendPacket(session, len(pkt))
                ctypes.memmove(out, pkt, len(pkt))
                dll.WintunSendPacket(session, out)

threading.Thread(target=tun_to_serial, daemon=True).start()
threading.Thread(target=serial_to_tun, daemon=True).start()

print("WINTUN + SLIP activo")
while True:
    time.sleep(1)
