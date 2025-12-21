# Modo de uso:
#Windows host: sudo python3 lora_tun_multios.py --port COM# --baud 115200 --ip 10.10.0.1 --peer 10.10.0.2 --mtu 576
#Windows peer: sudo python3 lora_tun_multios.py --port COM# --baud 115200 --ip 10.10.0.2 --peer 10.10.0.1 --mtu 576
#MAC host: sudo python3 lora_tun_multios.py --port /dev/tty.usbmodem# --baud 115200 --ip 10.10.0.1 --peer 10.10.0.2 --mtu 576
#MAC peer: sudo python3 lora_tun_multios.py --port /dev/tty.usbmodem# --baud 115200 --ip 10.10.0.2 --peer 10.10.0.1 --mtu 576
#Linux host: sudo python3 lora_tun_multios.py --port /dev/ttyACM# --baud 115200 --ip 10.10.0.1 --peer 10.10.0.2 --mtu 576
#Linux peer: sudo python3 lora_tun_multios.py --port /dev/ttyACM# --baud 115200 --ip 10.10.0.2 --peer 10.10.0.1 --mtu 576

#!/usr/bin/env python3
import os
import sys
import time
import struct
import socket
import serial
import threading
import argparse
import subprocess
import platform

# ---------- CONFIG ----------      
AF_INET = socket.AF_INET # MacOS necesario

TUNSETIFF = 0x400454ca # Linux necesario
IFF_TUN   = 0x0001 # Linux necesario
IFF_NO_PI = 0x1000 # # Linux necesario obligatorio


# ================= SLIP            =================
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

# ================= WINDOWS (WINTUN)=================
def setup_wintun(ip, peer, mtu):
    import ctypes
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


    subprocess.run(["powershell", "-Command", f'New-NetIPAddress -InterfaceAlias "LoRaTun" ' f'-IPAddress {ip} -PrefixLength 32 -ErrorAction SilentlyContinue'], stdout=subprocess.DEVNULL)

    subprocess.run(["powershell", "-Command",f'New-NetRoute -DestinationPrefix {peer}/32 ' f'-InterfaceAlias "LoRaTun" -ErrorAction SilentlyContinue'], stdout=subprocess.DEVNULL)


    def tun_recv():
        size = ctypes.c_uint32()
        pkt = dll.WintunReceivePacket(session, ctypes.byref(size))
        if not pkt:
            return None
        data = ctypes.string_at(pkt, size.value)
        dll.WintunReleaseReceivePacket(session, pkt)
        return data

    def tun_send(pkt):
        out = dll.WintunAllocateSendPacket(session, len(pkt))
        ctypes.memmove(out, pkt, len(pkt))
        dll.WintunSendPacket(session, out)

    return tun_recv, tun_send

# ================= MACOS (UTUN)    =================
def setup_utun(ip, peer, mtu):    
    import fcntl
    sock = socket.socket(32, socket.SOCK_DGRAM, 2)

    info = struct.pack("I96s", 0, b"com.apple.net.utun_control")
    ctl = fcntl.ioctl(sock, 0xC0644E03, info)
    ctl_id = struct.unpack("I96s", ctl)[0]

    sock.connect((ctl_id, 0))
    name = sock.getsockopt(2, 2, 16).rstrip(b"\0").decode()

    subprocess.run([
        "ifconfig", name,
        "inet", ip, peer,
        "netmask", "255.255.255.255",
        "mtu", str(mtu), "up"
    ], check=True)

    subprocess.run([
        "route", "-n", "add", "-host", peer, "-iface", name
    ], check=True)

    def tun_recv():
        data = sock.recv(4096)
        if struct.unpack("!I", data[:4])[0] != AF_INET:
            return None
        return data[4:]

    def tun_send(pkt):
        sock.sendall(struct.pack("!I", AF_INET) + pkt)

    return tun_recv, tun_send    

# ================= LINUX           =================
def setup_linux_tun(ip, peer, mtu):
    import fcntl
    tun = open("/dev/net/tun", "r+b", buffering=0)
    ifr = struct.pack(
        "16sH",
        b"lora%d",
        IFF_TUN | IFF_NO_PI
    )
    ifs = fcntl.ioctl(tun, TUNSETIFF, ifr)
    name = ifs[:16].rstrip(b"\0").decode()
    subprocess.run(
        ["ip", "addr", "add", f"{ip}/32", "peer", peer, "dev", name],
        check=True
    )
    subprocess.run(
        ["ip", "link", "set", "dev", name, "mtu", str(mtu), "up"],
        check=True
    )
    # Añadir ruta al peer, ignorando si ya existe (lo crea automáticamente el kernel)
    result = subprocess.run(
        ["ip", "route", "add", peer, "dev", name],
        capture_output=True,
        text=True
    )
    if result.returncode != 0 and "File exists" not in result.stderr:
        raise RuntimeError(f"Error añadiendo ruta: {result.stderr}")

    def tun_recv():
        data = tun.read(4096)
        if not data:
            return None
        if data[0] >> 4 != 4:  # IPv4
            return None
        return data

    def tun_send(pkt):
        tun.write(pkt)

    return tun_recv, tun_send

# ================= SERIAL THREADS  =================
def run_bridge(tun_recv, tun_send, ser):
    def tun_to_serial():
        while True:
            pkt = tun_recv()
            if not pkt:
                time.sleep(0.001)
                continue
            if pkt[0] >> 4 != 4:
                continue
            try:
                ser.write(slip_encode(pkt))
            except serial.SerialException:
                os._exit(1)

    def serial_to_tun():
        dec = slip_decoder()
        next(dec)
        while True:
            for b in ser.read(256):
                pkt = dec.send(b)
                if pkt:
                    tun_send(pkt)

    threading.Thread(target=tun_to_serial, daemon=True).start()
    threading.Thread(target=serial_to_tun, daemon=True).start()

# ================= MAIN =================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200) # 921600 o 115200
    parser.add_argument("--ip", required=True)
    parser.add_argument("--peer", required=True)
    parser.add_argument("--mtu", type=int, default=576)
    args = parser.parse_args()

    ser = serial.Serial(args.port, args.baud, timeout=0.1)

    osname = platform.system().lower()
    
    if osname == "windows": # Ej. "COM#"
        tun_recv, tun_send = setup_wintun(args.ip, args.peer, args.mtu)
    elif osname == "darwin": # Ej. "/dev/tty.usbmodem101"  
        if os.geteuid() != 0:
            print("Ejecuta como root (sudo)")
            sys.exit(1)
        tun_recv, tun_send = setup_utun(args.ip, args.peer, args.mtu)
    elif osname == "linux": # Ej. "/dev/ttyACM0"   
        if os.geteuid() != 0:
            print("Ejecuta como root (sudo)")
            sys.exit(1)
        tun_recv, tun_send = setup_linux_tun(args.ip, args.peer, args.mtu)
    else:
        raise RuntimeError("Sistema Operativo aún no implementado.")

    run_bridge(tun_recv, tun_send, ser)

    print(f"TUN + SLIP activo ({osname})")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()    
