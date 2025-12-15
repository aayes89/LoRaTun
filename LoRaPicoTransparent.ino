/*
MIT License

Copyright (c) 2025 Allan (Slam)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/
/*
* Código creado por Slam(2025)
* Github: https://github.com/aayes89
*/
// LIBRERIAS
#include <SPI.h>
#include <LoRa.h>
// CONSTANTES GLOBALES
#define LORA_SS 5
#define LORA_RST 6
#define LORA_DIO0 7
#define LORA_SCK 2
#define LORA_MISO 4
#define LORA_MOSI 3

#define LED_PIN 25
#define FREQ 433E6

#define MAGIC 0xA5
#define TYPE_DATA 0x01

#define MAX_PAYLOAD 180
#define LEN_HDR 2
#define MIN_ETH 60

uint8_t tx_seq = 0;
// INICIALIZACION DE PARAMETROS
void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(115200);
  while (!Serial)
    ;

  // SPI (defaults OK en Pico)
  SPI.setSCK(LORA_SCK);
  SPI.setMISO(LORA_MISO);
  SPI.setMOSI(LORA_MOSI);
  SPI.begin();

  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(FREQ)) {
    while (1) {
      digitalWrite(LED_PIN, !digitalRead(LED_PIN));
      delay(200);
    }
  }
  // COMPORTAMIENTO DE LORA
  LoRa.setTxPower(20, PA_OUTPUT_PA_BOOST_PIN);
  LoRa.setSpreadingFactor(8);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(6);
  LoRa.disableCrc();

  Serial.println("LORA BRIDGE READY");
}

void loop() {
  // USB -> LoRa 
  if (Serial.available() >= LEN_HDR) {

    uint16_t len;
    Serial.readBytes((uint8_t*)&len, 2);
    
    // DESCARTAR PAQUETES BASURA
    if (len < MIN_ETH || len > MAX_PAYLOAD) {      
      return;
    }
    
    // PREPARAR BUFER DE LECTURA
    uint8_t buf[MAX_PAYLOAD];
    size_t got = Serial.readBytes(buf, len);
    if (got != len) return;
    
    // ENVIAR EL PAQUETE
    LoRa.beginPacket();
    LoRa.write(MAGIC);
    LoRa.write(TYPE_DATA);
    LoRa.write(tx_seq++);
    LoRa.write(buf, len);
    LoRa.endPacket();

    digitalWrite(LED_PIN, HIGH);
    delay(8);
    digitalWrite(LED_PIN, LOW);
  }


  // LoRa -> USB 
  int p = LoRa.parsePacket();
  if (p >= 4) {

    if (LoRa.read() != MAGIC) return;
    if (LoRa.read() != TYPE_DATA) return;
    
    //RESERVADO
    uint8_t seq = LoRa.read(); 

    uint16_t len = p - 3;
    if (len < MIN_ETH || len > MAX_PAYLOAD) return;

    // ENVIAR PREFIJO DE LONGITUD
    Serial.write((uint8_t*)&len, 2);

    while (LoRa.available()) {
      Serial.write(LoRa.read());
    }

    digitalWrite(LED_PIN, HIGH);
    delay(20);
    digitalWrite(LED_PIN, LOW);
  }
}
