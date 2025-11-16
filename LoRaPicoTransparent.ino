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
// --- LIBRERÍAS ---
#include <SPI.h>
#include <LoRa.h>
// --- CONEXIONES LORA-PICO ---
#define LORA_SS    5
#define LORA_RST   6
#define LORA_DIO0  7
#define LORA_SCK   2
#define LORA_MISO  4
#define LORA_MOSI  3
#define LED_PIN    25
// --- FRECUENCIA ---
#define LORA_FREQ  433E6
// --- GLOBALES ---
#define SERIAL_BAUD 115200
#define TX_BUFFER_SIZE 128

byte txBuffer[TX_BUFFER_SIZE];
int txLen = 0;
unsigned long lastTx = 0;

void setup() {
  Serial.begin(SERIAL_BAUD);
  while (!Serial);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  SPI.setSCK(LORA_SCK);
  SPI.setMISO(LORA_MISO);
  SPI.setMOSI(LORA_MOSI);
  SPI.begin();

  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    while (1) {
      digitalWrite(LED_PIN, HIGH);
      delay(100);
      digitalWrite(LED_PIN, LOW);
      delay(100);
    }
  }

  LoRa.setTxPower(20, PA_OUTPUT_PA_BOOST_PIN);
  LoRa.setSpreadingFactor(7);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);

  Serial.println("LoRa Serial Bridge Ready");
}

void loop() {
  // RX
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    digitalWrite(LED_PIN, HIGH);
    while (LoRa.available()) {
      Serial.write(LoRa.read());
    }
    digitalWrite(LED_PIN, LOW);
  }

  // TX
  while (Serial.available() && txLen < TX_BUFFER_SIZE) {
    txBuffer[txLen++] = Serial.read();
    lastTx = millis();
  }

  if (txLen > 0 && (txLen == TX_BUFFER_SIZE || (millis() - lastTx > 300))) {
    digitalWrite(LED_PIN, HIGH);
    LoRa.beginPacket();
    LoRa.write(txBuffer, txLen);
    LoRa.endPacket();
    txLen = 0;
    digitalWrite(LED_PIN, LOW);
  }
}
