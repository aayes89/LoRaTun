#!/usr/bin/env python3
import os
import sys
import time
import struct
import socket
import serial
import threading
import argparse
import logging
import subprocess
import fcntl

# ---------------- CONFIG ----------------

DEFAULT_PORT = "/dev/tty.usbmodem0001"
DEFAULT_BAUD = 115200
DEFAULT_IP = "10.10.0.1"
PEER_IP    = "10.10.0.2"
DEFAULT_MTU = 120

UTUN_HEADER_SIZE = 4
LEN_HDR = 2
AF_INET = socket.AF_INET
#PF_INET = socket.PF_INET

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
log = logging.getLogger("lora-macos")

# ---------------- UTUN ----------------

def create_utun(ip, peer, mtu):
    UTUN_CONTROL_NAME = b"com.apple.net.utun_control"
    PF_SYSTEM = 32
    SYSPROTO_CONTROL = 2
    SOCK_DGRAM = 2
    CTLIOCGINFO = 0xC0644E03

    sock = socket.socket(PF_SYSTEM, SOCK_DGRAM, SYSPROTO_CONTROL)

    ctl_info = struct.pack("I96s", 0, UTUN_CONTROL_NAME)
    ctl_info = fcntl.ioctl(sock, CTLIOCGINFO, ctl_info)
    ctl_id = struct.unpack("I96s", ctl_info)[0]

    # 👇 ESTA ES LA FORMA CORRECTA EN PYTHON
    sock.connect((ctl_id, 0))

    utun_name = sock.getsockopt(SYSPROTO_CONTROL, 2, 16)
    utun_name = utun_name.rstrip(b"\x00").decode()
    log.info(f"UTUN creado: {utun_name}")

    subprocess.run(
        ["ifconfig", utun_name, ip, peer, "mtu", str(mtu), "up"],
        check=True
    )

    return sock


# ---------------- SERIAL ----------------

def open_serial(port, baud):
    ser = serial.Serial(port, baud, timeout=0.1)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    return ser

# ---------------- UTUN -> SERIAL ----------------
def tun_to_serial1(tun, ser, mtu):
    ip_mtu = mtu - 20

    while True:
        data = tun.recv(4096)
        if not data:
            continue

        if struct.unpack("!I", data[:4])[0] != socket.AF_INET:
            continue

        ip_packet = data[4:]

        fragments = [
            ip_packet[i:i+ip_mtu]
            for i in range(0, len(ip_packet), ip_mtu)
        ]

        total = len(fragments)

        for i, frag in enumerate(fragments):
            frame = build_frame(i, total, frag)
            ser.write(struct.pack("<H", len(frame)))
            ser.write(frame)

def tun_to_serial(tun, ser, mtu):
    ip_mtu = mtu - 2

    while True:
        data = tun.recv(2048)
        if not data:
            continue

        if struct.unpack("!I", data[:4])[0] != socket.AF_INET:
            continue

        payload = data[4:]

        if 0 < len(payload) <= ip_mtu:
            ser.write(struct.pack("<H", len(payload)))
            ser.write(payload)

# ---------------- SERIAL -> UTUN ----------------
rx_packets = {}

def serial_to_tun1(tun, ser, mtu):
    buf = bytearray()

    while True:
        buf.extend(ser.read(256))

        while len(buf) >= 2:
            size = struct.unpack("<H", buf[:2])[0]

            if len(buf) < 2 + size:
                break

            frame = buf[2:2+size]
            del buf[:2+size]

            parsed = parse_frame(frame)
            if not parsed:
                continue

            ftype, seq, total, data = parsed

            rx_packets.setdefault(total, {})[seq] = data

            if len(rx_packets[total]) == total:
                ip_packet = b''.join(
                    rx_packets[total][i] for i in range(total)
                )

                pkt = struct.pack("!I", socket.AF_INET) + ip_packet
                tun.sendall(pkt)

                del rx_packets[total]

def serial_to_tun(tun, ser, mtu):
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
            pkt = struct.pack("!I", socket.AF_INET) + payload
            tun.sendall(pkt)

            del buf[:2+size]

# ---------------- MAIN ----------------

def main():
    if os.geteuid() != 0:
        print("Ejecuta como root (sudo).")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument("--peer", default=PEER_IP)
    parser.add_argument("--mtu", type=int, default=DEFAULT_MTU)
    args = parser.parse_args()

    ser = open_serial(args.port, args.baud)    

    tun = create_utun(args.ip, args.peer, args.mtu)

    t1 = threading.Thread(
        target=tun_to_serial, args=(tun, ser, args.mtu), daemon=True
    )
    t2 = threading.Thread(
        target=serial_to_tun, args=(tun, ser, args.mtu), daemon=True
    )

    t1.start()
    t2.start()

    log.info("Bridge activo en macOS")
    log.info("Prueba: ping %s", args.peer)

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
