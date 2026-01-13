#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>

#define LORA_NSS PA4
#define LORA_SCK PA5
#define LORA_NRST PA3
#define LORA_BUSY PA2
#define LORA_MOSI PA7
#define LORA_MISO PA6
#define LORA_DIO1 PC15
//#define LORA_DIO2  NC
#define LORA_TXEN PA0
#define LORA_RXEN PA1

#define LED_PIN PB11  // PC13
#define LORA_MAX_PACKET 255   // SX1262
#define SERIAL_FLUSH_MS 5     // timeout para agrupar bytes


SX1262 radio = new Module(LORA_NSS, LORA_DIO1, LORA_NRST, LORA_BUSY);  //, spi1);

void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(LORA_TXEN, OUTPUT);
  pinMode(LORA_RXEN, OUTPUT);

  digitalWrite(LED_PIN, HIGH);
  delay(200);
  digitalWrite(LED_PIN, LOW);
  digitalWrite(LORA_TXEN, LOW);
  digitalWrite(LORA_RXEN, HIGH);

  Serial.begin(460800); // 115200
  while (!Serial)
    ;
  // SPI
  SPI.setMISO(LORA_MISO);
  SPI.setMOSI(LORA_MOSI);
  SPI.setSCLK(LORA_SCK);
  SPI.begin();

  // Reset SX1262
  pinMode(LORA_NRST, OUTPUT);
  digitalWrite(LORA_NRST, LOW);
  delay(10);
  digitalWrite(LORA_NRST, HIGH);
  delay(10);

  pinMode(LORA_BUSY, INPUT);
  Serial.print("BUSY=");
  Serial.println(digitalRead(LORA_BUSY)); // debe ser 0

  // PARAMS  
  //radio.setRegulatorMode(RADIOLIB_SX126X_REGULATOR_DC_DC); // por si LDO falla
  radio.setDio2AsRfSwitch(true);  // DX-LR30 usa DIO2

  /*float freq = 434.
    float bw = 125.
    int sf = 9
    int cr = 7
    int syncWord = 18
    int power = 10
    int preambleLength = 8
    float tcxoVoltage = 1.6000000000000001
    bool useRegulatorLDO = false
  */
  radio.XTAL = true;
  int state = radio.begin(915.0, 125.0, 9, 7, 0x12, 22, 8, 0.0);
  Serial.print("Radio init: ");
  Serial.println(state);

  if (state == RADIOLIB_ERR_NONE) {
    Serial.println("DX-LR30 SX1262 READY");
    digitalWrite(LED_PIN, LOW);
  } else {
    Serial.println("Radio FAILED");
    while (1) {
      digitalWrite(LED_PIN, !digitalRead(LED_PIN));
      delay(200);
    }
  }

  Serial.println("DX-LR30 (SX1262) OK");
}

void loop() {
  static uint8_t txBuf[LORA_MAX_PACKET];
  static size_t txLen = 0;
  static uint32_t lastByteTime = 0;

  /* =======================
     USB → LoRa
     ======================= */

  while (Serial.available()) {
    if (txLen < LORA_MAX_PACKET) {
      txBuf[txLen++] = Serial.read();
      lastByteTime = millis();
    } else {
      break;
    }
  }

  // Si hay datos y pasó el timeout → enviar
  if (txLen > 0 && (millis() - lastByteTime) > SERIAL_FLUSH_MS) {
    digitalWrite(LORA_RXEN, LOW);
    digitalWrite(LORA_TXEN, HIGH);

    int state = radio.transmit(txBuf, txLen);

    digitalWrite(LORA_TXEN, LOW);
    digitalWrite(LORA_RXEN, HIGH);

    txLen = 0;

    radio.startReceive();
  }

  /* =======================
     LoRa → USB
     ======================= */

  uint8_t rxBuf[LORA_MAX_PACKET];
  int len = radio.getPacketLength();

  if (len > 0 && len <= LORA_MAX_PACKET) {
    int state = radio.readData(rxBuf, len);

    if (state == RADIOLIB_ERR_NONE) {
      for (int i = 0; i < len; i++) {
        Serial.write(rxBuf[i]);
      }
    }

    radio.startReceive();
  }
}
