# LoRaTun
Establece conexión TCP/IP sobre SLIP con Raspberry Pi Pico + SX1278 usando TUN sobre capa 3, permitiendo servicios como PING, SSH, WWW, etc. <br>

# Requisitos de hardware
- Raspberry Pi Pico (2)
- Módulos LoRa SX1278 (433MHz) (2)
- PC o Laptop (2)

# Requisitos de software
- Ser administrador del sistema.
- Sistema Operativo (Windows, Linux o MacOS)
- Driver TAP instalado previamente.
- Arduino IDE (para compilar el código a usar en las Rasbperry Pi Pico)

# Esquema de conexión LORA - RPI
- LORA SS - PICO 5
- LORA RST - PICO 6
- LORA DIO0 - PICO 7
- LORA SCK - PICO 2
- LORA MISO - PICO 4
- LORA MOSI - PICO 3
- LED PIN PICO 25 (indicador) 

# Configuración
Dependencias en Python: <code>pip install pywin32 wmi pyserial</code><br>

<b>Windows variante manual:</b> 
 - Instala: https://swupdate.openvpn.org/community/releases/tap-windows-9.24.2-I601-Win10.exe<br>
 - En PowerShell obten el GUID del adaptador usando este comando si falla el script: <br><code>Get-NetAdapter | Where-Object {$_.InterfaceDescription -Like "*TAP*"} | Format-List -Property Name, InterfaceDescription, InterfaceGuid</code><br> 
 - En caso de que no configure correctamente la interfaz: "Conexión de área local", renombrar a <b>LoRaTun0</b>.<br>
 - De igual forma si falla la configuración automática de la interfaz de red, usar: <code>netsh interface ip set address name="LoRaTun0" static 10.10.0.1 255.255.255.0</code>
 
<b>Windows Variante automática: </b>
 - Ejecutar desde PowerShell como administrador:
 - PC principal: <code>sudo python3 lora_tun_multios.py --port COM# [--baud 115200] --ip 10.10.0.1 --peer 10.10.0.2 [--mtu 576]</code>
 - PC auxiliar:  <code>sudo python3 lora_tun_multios.py --port COM# [--baud 115200] --ip 10.10.0.2 --peer 10.10.0.1 [--mtu 576]</code> 

<b>Linux: (PRUEBAS PENDIENTE)</b>
- Ejecutar como administrador en cualquiera de estos modos:
- PC principal: <code>sudo python3 lora_tun_multios.py --port /dev/ttyACM# [--baud 115200] --ip 10.10.0.1 --peer 10.10.0.2 [--mtu 576]</code>
- PC auxiliar:  <code>sudo python3 lora_tun_multios.py --port /dev/ttyACM# [--baud 115200] --ip 10.10.0.2 --peer 10.10.0.1 [--mtu 576]</code>

<b>MacOS: </b>
- Ejecutar el script lora_tun_multios.py como administrador. (<b>MacOS UTUN no es accesible de otra forma</b>)
- PC principal: <code>sudo python3 lora_tun_multios.py --port /dev/tty.usbmodem# [--baud 115200] --ip 10.10.0.1 --peer 10.10.0.2 [--mtu 576]</code>
- PC auxiliar:  <code>sudo python3 lora_tun_multios.py --port /dev/tty.usbmodem# [--baud 115200] --ip 10.10.0.2 --peer 10.10.0.1 [--mtu 576]</code>

<b>Leyenda: </b> [--baud ...| --mtu ...] - opcionales

# Por mejorar/hacer
* Añadir soporte para Android e IOs.
* Intentar eliminar el requisito de permisos como administrador para una conexión Plug-and-Play.
* Optimizar implementación de SLIP/TUN para aumentar el ancho de banda.
* Probar con otros módulos para escalabilidad del código.
* Diseñar y Fabricar PCB para protección de los componentes y presentación al público.

# Licencia
Éste código utiliza licencia MIT

# Capturas y Anexos

<img width="863" height="514" alt="imagen" src="https://github.com/user-attachments/assets/a12096ef-79d8-4067-9f69-ef677223aa2f" />


