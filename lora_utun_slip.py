import os
import time
import struct
import socket
import serial
import threading
import subprocess
import fcntl

# ---------- CONFIG ----------
PORT = "/dev/tty.usbmodem101"
BAUD = 115200
IP_LOCAL = "10.10.0.2"
IP_PEER  = "10.10.0.1"
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

# ---------- UTUN ----------
def create_utun():
    UTUN = b"com.apple.net.utun_control"
    sock = socket.socket(32, socket.SOCK_DGRAM, 2)

    info = struct.pack("I96s", 0, UTUN)
    ctl = fcntl.ioctl(sock, 0xC0644E03, info)
    ctl_id = struct.unpack("I96s", ctl)[0]

    sock.connect((ctl_id, 0))
    name = sock.getsockopt(2, 2, 16).rstrip(b"\0").decode()

    subprocess.run([
        "ifconfig", name,
        "inet", IP_LOCAL, IP_PEER,
        "netmask", "255.255.255.255",
        "mtu", str(MTU), "up"
    ], check=True)

    subprocess.run([
        "route", "-n", "add", "-host", IP_PEER, "-iface", name
    ], check=True)

    return sock

tun = create_utun()
ser = serial.Serial(PORT, BAUD, timeout=0.1)

# ---------- TUN → SERIAL ----------
def tun_to_serial():
    while True:
        data = tun.recv(4096)
        if struct.unpack("!I", data[:4])[0] != socket.AF_INET:
            continue

        ip = data[4:]
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
                tun.sendall(struct.pack("!I", socket.AF_INET) + pkt)

threading.Thread(target=tun_to_serial, daemon=True).start()
threading.Thread(target=serial_to_tun, daemon=True).start()

print("UTUN + SLIP activo")
while True:
    time.sleep(1)
