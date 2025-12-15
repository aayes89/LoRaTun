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

<b>Windows variante 1:</b> 
 - Instala: https://swupdate.openvpn.org/community/releases/tap-windows-9.24.2-I601-Win10.exe<br>
 - En PowerShell obten el GUID del adaptador usando este comando si falla el script: <br><code>Get-NetAdapter | Where-Object {$_.InterfaceDescription -Like "*TAP*"} | Format-List -Property Name, InterfaceDescription, InterfaceGuid</code><br> 
 - En caso de que no configure correctamente la interfaz: "Conexión de área local", renombrar a <b>LoRaTun0</b>.<br>
 - De igual forma si falla la configuración automática de la interfaz de red, usar: <code>netsh interface ip set address name="LoRaTun0" static 10.10.0.1 255.255.255.0</code>
 
 <b>Windos Variante 2: </b>
 - Ejecutar desde PowerShell como administrador el script <b>lora_wintun_slip.py</b>.
 - Establecer la IP de forma manual si al crease la interfaz no aparece como espera. 

<b>Linux: </b>
- Ejecutar los siguientes comandos en el terminal de tu preferencia como administrador: <code>
  sudo ip addr add 10.10.0.1/24 dev LoRaTun0
  sudo ip link set LoRaTun0 up</code>

<b>MacOS: </b>
- Ejecutar el script lora_utun_slip.py como administrador. (<b>MacOS UTUN no es accesible de otra forma</b>)
 
# Por mejorar
* Configuración automática en los sistemas operativos.
* Añadir soporte para Android e IOs. 

# Licencia
Éste código utiliza licencia MIT

# Capturas

<img width="863" height="514" alt="imagen" src="https://github.com/user-attachments/assets/a12096ef-79d8-4067-9f69-ef677223aa2f" />


