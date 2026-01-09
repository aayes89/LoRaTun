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

#include <SPI.h>
#include <LoRa.h>
// custom
/*
#define LORA_SS   5
#define LORA_RST  6
#define LORA_DIO0 7
#define LORA_SCK  2
#define LORA_MISO 4
#define LORA_MOSI 3
*/
// meshtastic pinout
#define LORA_SS   3
#define LORA_RST  15
#define LORA_DIO0 20
#define LORA_SCK  10
#define LORA_MISO 12
#define LORA_MOSI 11

#define LED_PIN 25
#define FREQ 433E6

#define MAX_FRAME 255

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(115200);
  while (!Serial);

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

  LoRa.setTxPower(20, PA_OUTPUT_PA_BOOST_PIN);
  LoRa.setSpreadingFactor(8);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.enableCrc();              // IMPORTANTE
  LoRa.setPreambleLength(8);
  LoRa.setSyncWord(0x12);

  Serial.println("LORA RAW BRIDGE READY");
}

void loop() {
  // USB → LoRa
  while (Serial.available()) {
    LoRa.beginPacket();
    while (Serial.available()) {
      LoRa.write(Serial.read());
    }
    LoRa.endPacket();
  }

  // LoRa → USB
  int p = LoRa.parsePacket();
  if (p) {
    while (LoRa.available()) {
      Serial.write(LoRa.read());
    }
  }
}
