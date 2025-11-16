# LoRaTun
Envía TCP/IP crudo con Raspberry Pi Pico + SX1278 usando TUN/TAP.

# Configuración
Dependencias en Python: <code>pip install pywin32 wmi pyserial</code>

<b>Windows:</b> 
 - Instala: https://swupdate.openvpn.org/community/releases/tap-windows-9.24.2-I601-Win10.exe<br>
 - En PowerShell obten el GUID del adaptador usando este comando si falla el script: <br><code>Get-NetAdapter | Where-Object {$_.InterfaceDescription -Like "*TAP*"} | Format-List -Property Name, InterfaceDescription, InterfaceGuid</code><br> 
 - En caso de que no configure correctamente la interfaz: "Conexión de área local", renombrar a <b>LoRaTun0</b>.<br>
 - De igual forma si falla la configuración automática de la interfaz de red, usar: <code>netsh interface ip set address name="LoRaTun0" static 10.10.0.1 255.255.255.0</code>

<b>Linux/MacOS: </b>
- Ejecutar los siguientes comandos en el terminal de tu preferencia como administrador: <code>
  sudo ip addr add 10.10.0.1/24 dev LoRaTun0
  sudo ip link set LoRaTun0 up</code>

# Por mejorar
* Configuración automática en los sistemas operativos.
* Añadir soporte para Android e IOs.
 

# Licencia
Éste código utiliza licencia MIT
