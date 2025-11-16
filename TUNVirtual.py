"""
Configuración
Dependencias: pip install pywin32 wmi pyserial

Windows: 
 Instala: https://swupdate.openvpn.org/community/releases/tap-windows-9.24.2-I601-Win10.exe
 En PowerShel obten el GUID del adaptador usando este comando: Get-NetAdapter | Where-Object {$_.InterfaceDescription -Like "*TAP*"} | Format-List -Property Name, InterfaceDescription, InterfaceGuid

 netsh interface ip set address name="LoRaTun0" static 10.10.0.1 255.255.255.0

Linux/MacOS: 
 sudo ip addr add 10.10.0.1/24 dev LoRaTun0
 sudo ip link set LoRaTun0 up

"""
#!/usr/bin/env python3
# Multiplatform TUN/TAP bridge for Pico LoRa transparent firmware
# This version autodetects TAP adapter on Windows by calling PowerShell.
import os
import sys
import time
import struct
import serial
import threading
import subprocess
import json
import platform
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"
if IS_WINDOWS:
    import win32file
    import win32con
SERIAL_PORT = "COM14" if IS_WINDOWS else "/dev/ttyACM0"
SERIAL_BAUD = 115200
# -------------------
# Windows TAP detection: PowerShell -> ConvertTo-Json
# -------------------
def find_windows_tap_ps_adapter():
    ps_cmd = (
        "$OutputEncoding = [System.Text.Encoding]::UTF8; "
        "Get-NetAdapter | "
        "Where-Object { $_.InterfaceDescription -match 'TAP|tap' -or $_.Name -match 'TAP|tap' } | "
        "Select-Object -Property Name, InterfaceDescription, InterfaceGuid | ConvertTo-Json -Depth 2"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=False, timeout=6
        )
        if completed.returncode != 0:
            return None
        out = completed.stdout.decode('utf-8').strip()
    except (FileNotFoundError, UnicodeDecodeError, subprocess.TimeoutExpired):
        return None
    if not out:
        return None
    try:
        data = json.loads(out)
    except Exception:
        return None
    candidates = []
    if isinstance(data, dict):
        candidates.append(data)
    elif isinstance(data, list):
        candidates.extend(data)
    else:
        return None
    for item in candidates:
        name = item.get("Name", "")
        desc = item.get("InterfaceDescription", "")
        guid = item.get("InterfaceGuid", "")
        if not guid:
            continue
        if "tap" in desc.lower() or "tap" in name.lower():
            return name, guid
    # Fallback: return first if any
    if candidates:
        item = candidates[0]
        return item.get("Name", ""), item.get("InterfaceGuid", "")
    return None
# -------------------
# Fallback: wmic nic query (older systems)
# -------------------
def find_windows_tap_wmic_adapter():
    try:
        completed = subprocess.run(
            ["wmic", "nic", "where", "Description like '%TAP%'", "get", "GUID,Name", "/format:csv"],
            capture_output=True, text=False, timeout=6
        )
        if completed.returncode != 0:
            return None
        out = completed.stdout.decode('cp1252', errors='replace').strip()
    except (FileNotFoundError, UnicodeDecodeError, subprocess.TimeoutExpired):
        return None
    if not out:
        return None
    # Parse CSV, skip header
    for line in out.splitlines()[1:]:
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) == 3:
            guid = parts[1]
            name = parts[2].replace('\xa0', ' ')  # Fix NBSP
            if guid and guid != "GUID":
                if not guid.startswith("{"):
                    guid = "{" + guid + "}"
                return name, guid
    return None
def find_windows_tap_adapter():
    res = find_windows_tap_ps_adapter()
    if res:
        name, guid = res
        print(f"[+] find_windows_tap_adapter: found via PowerShell -> {name} ({guid})")
        return res
    # Fallback to WMIC
    res = find_windows_tap_wmic_adapter()
    if res:
        name, guid = res
        print(f"[+] find_windows_tap_adapter: found via WMIC -> {name} ({guid})")
        return res
    return None
# -------------------
# Create interface depending on OS
# -------------------
def create_interface():
    if IS_WINDOWS:
        res = find_windows_tap_adapter()
        if not res:
            raise RuntimeError("No TAP adapter found. Install TAP-Windows and ensure adapter exists.")
        adapter_name, guid = res
        # Enable interface
        print(f"[+] Enabling interface '{adapter_name}'")
        try:
            subprocess.run(
                ["netsh", "interface", "set", "interface", f'name="{adapter_name}"', "admin=enabled"],
                capture_output=True, text=False, timeout=10
            )
            print("[+] Interface enabled.")
        except subprocess.CalledProcessError as e:
            print(f"[!] Enable failed: {e.returncode}")
            if e.stderr:
                stderr_dec = e.stderr.decode('cp1252', errors='replace')
                print(f"[!] Error output: {stderr_dec}")
        # Skip clear and set IP since manual        
        print(f"[!] Configure manually: netsh interface ip set address name=\"{adapter_name}\" static 10.10.0.1 255.255.255.0")
        # Try to open TAP device (synchronous)
        tap_paths = [
            r"\\.\Global\{}.tap".format(guid),
            r"\\.\{}.tap".format(guid)
        ]
        handle = None
        for tap_path in tap_paths:
            print(f"[+] Trying to open: {tap_path}")
            try:
                handle = win32file.CreateFile(
                    tap_path,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                    None,
                    win32file.OPEN_EXISTING,
                    win32file.FILE_ATTRIBUTE_SYSTEM,  # As in gist
                    None
                )
                print(f"[+] Opened TAP at {tap_path}")
                break
            except Exception as e_open:
                print(f"[!] Failed to open {tap_path}: {e_open}")
                continue
        if not handle:
            raise FileNotFoundError(f"TAP device not found at any path. Check adapter GUID and privileges.")
        # Activate TAP (set media status) with correct ioctl
        TAP_IOCTL_SET_MEDIA_STATUS = 0x00220018  # Correct value from TAP driver
        try:
            in_buf = b'\x01\x00\x00\x00'  # Connected
            win32file.DeviceIoControl(handle, TAP_IOCTL_SET_MEDIA_STATUS, in_buf, None)
            print("[+] TAP media status set OK.")
        except Exception as e_ioctl:
            print(f"[!] Warning: DeviceIoControl failed: {e_ioctl}. You may still proceed.")
        return handle
    elif IS_LINUX:
        import fcntl
        TUNSETIFF = 0x400454ca
        IFF_TUN = 0x0001
        IFF_NO_PI = 0x1000
        fd = os.open("/dev/net/tun", os.O_RDWR)
        ifname = b"LoRaTun0"
        ifr = struct.pack("16sH", ifname, IFF_TUN | IFF_NO_PI)
        fcntl.ioctl(fd, TUNSETIFF, ifr)
        tun_name = ifname.decode()
        print(f"[+] TUN created: {tun_name}")
        # Configure IP and up (assumes root)
        try:
            subprocess.run(["ip", "link", "set", "dev", tun_name, "up"], check=True, capture_output=True)
            subprocess.run(["ip", "addr", "add", "10.10.0.1/24", "dev", tun_name], check=True, capture_output=True)
            print("[+] IP 10.10.0.1/24 configured and interface up on LoRaTun0")
        except subprocess.CalledProcessError as e:
            print(f"[!] Failed to auto-configure IP/link: {e}")
            print("[!] Configure manually: sudo ip link set LoRaTun0 up && sudo ip addr add 10.10.0.1/24 dev LoRaTun0")
        return fd
    elif IS_MAC:
        raise RuntimeError("macOS TUN/TAP creation not fully supported. Create/configure LoRaTun0 manually (e.g., via ifconfig) and modify the script to open the existing device.")
    else:
        raise RuntimeError("Unsupported OS")
# -------------------
# Bridge loops (synchronous I/O for TAP)
# -------------------
def tun_to_serial(tun_handle, ser):
    while True:
        try:
            if IS_WINDOWS:
                err, data = win32file.ReadFile(tun_handle, 1500)
                if err != 0:
                    raise Exception(f"ReadFile error {err}")
            else:
                data = os.read(tun_handle, 1500)
            if len(data) > 0:
                ser.write(struct.pack("<H", len(data)))
                ser.write(data)
        except Exception as e:
            print(f"[!] tun_to_serial error: {e}")
            time.sleep(0.1)
def serial_to_tun(tun_handle, ser):
    while True:
        try:
            hdr = ser.read(2)
            if len(hdr) != 2:
                continue
            (size,) = struct.unpack("<H", hdr)
            packet = ser.read(size)
            if len(packet) == size:
                if IS_WINDOWS:
                    err, _ = win32file.WriteFile(tun_handle, packet)
                    if err != 0:
                        raise Exception(f"WriteFile error {err}")
                else:
                    os.write(tun_handle, packet)
        except Exception as e:
            print(f"[!] serial_to_tun error: {e}")
            time.sleep(0.1)
# -------------------
# Main
# -------------------
def main():
    print(f"[*] Serial port: {SERIAL_PORT} @ {SERIAL_BAUD}")
    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0.1)
    print("[*] Creating and configuring interface...")
    tun_handle = create_interface()
    print("[*] Starting bridge threads...")
    t1 = threading.Thread(target=tun_to_serial, args=(tun_handle, ser), daemon=True)
    t2 = threading.Thread(target=serial_to_tun, args=(tun_handle, ser), daemon=True)
    t1.start()
    t2.start()
    print("[+] Bridge running. Test connectivity (e.g., ping 10.10.0.2 from the other end). Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[*] Exiting.")
        ser.close()
        if IS_WINDOWS:
            win32file.CloseHandle(tun_handle)
        else:
            try:
                os.close(tun_handle)
            except:
                pass
if __name__ == "__main__":
    main()            
