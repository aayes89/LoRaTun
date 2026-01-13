#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>

// ────────────────────────────────────────────────
// Pines (ajusta según tu módulo / board)
#define LORA_NSS    PA4
#define LORA_SCK    PA5
#define LORA_MOSI   PA7
#define LORA_MISO   PA6
#define LORA_NRST   PA3
#define LORA_BUSY   PA2
#define LORA_DIO1   PC15
#define LORA_TXEN   PA0     // HIGH → TX, LOW → RX   (invierte si es activo en LOW)
#define LORA_RXEN   PA1
#define LED_PIN     PB11

#define UART_BAUD   460800 // 115200 230400 460800
#define MAX_PKT     128     // ↑ si necesitas más throughput (max ~250)

SX1262 radio = new Module(LORA_NSS, LORA_DIO1, LORA_NRST, LORA_BUSY);

volatile bool txDone = false;
volatile bool rxDone = false;

uint8_t txBuf[MAX_PKT];
uint8_t rxBuf[MAX_PKT];

volatile size_t txCount = 0;

// ────────────────────────────────────────────────
// Callbacks IRQ (importante: ICACHE_RAM_ATTR si es ESP, no en STM32)
void setTxFlag() {
  txDone = true;
}

void setRxFlag() {
  rxDone = true;
}

// ────────────────────────────────────────────────
void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(LORA_TXEN, OUTPUT);
  pinMode(LORA_RXEN, OUTPUT);

  digitalWrite(LED_PIN, HIGH); delay(100); digitalWrite(LED_PIN, LOW);
  digitalWrite(LORA_TXEN, LOW);
  digitalWrite(LORA_RXEN, HIGH);   // empezar en RX

  Serial.begin(UART_BAUD);
  while(!Serial);   // comenta en producción

  SPI.setMOSI(LORA_MOSI);
  SPI.setMISO(LORA_MISO);
  SPI.setSCLK(LORA_SCK);
  SPI.begin();

  // Reset
  digitalWrite(LORA_NRST, LOW); delay(10);
  digitalWrite(LORA_NRST, HIGH); delay(20);

  // Configuración recomendada para throughput + alcance razonable
  // Puedes bajar SF a 7–8 si quieres más velocidad (menor alcance)
  int state = radio.begin(
    915.0,          // frecuencia (cambia a tu banda)
    250.0,          // BW más ancha = más velocidad
    9,              // SF9 buen compromiso velocidad/alcance
    5,              // CR 4/5 → menos overhead
    0x12,           // sync word private
    22,             // potencia (ajusta según regulaciones y módulo)
    8,              // preamble
    0.0             // TCXO  → 1.6 o 1.8 si tu módulo lo tiene
  );

  if (state != RADIOLIB_ERR_NONE) {
    Serial.print("begin failed: "); Serial.println(state);
    while(true) { digitalWrite(LED_PIN, !digitalRead(LED_PIN)); delay(200); }
  }

  radio.setDio2AsRfSwitch(true);          // muchos módulos lo usan
  radio.setPacketSentAction(setTxFlag);
  radio.setPacketReceivedAction(setRxFlag);

  radio.setRxBoostedGainMode(true); // mejora sensibilidad RX (consume 1-2mA extra)
  radio.startReceive();
  Serial.println("SX1262 ready - transparent mode");
}

// ────────────────────────────────────────────────
void loop() {
  // RX → UART (prioridad)
  if (rxDone) {
    rxDone = false;
    size_t len = radio.getPacketLength(true);
    if (len > 0 && len <= MAX_PKT) {
      if (radio.readData(rxBuf, len) == RADIOLIB_ERR_NONE) {
        Serial.write(rxBuf, len);
      }
    }
    radio.startReceive();  // inmediato
  }

  // Acumula UART sin bloquear
  while (Serial.available() && txCount < MAX_PKT) {
    txBuf[txCount++] = Serial.read();
  }

  static uint32_t lastByteMs = 0;
  if (txCount > 0) lastByteMs = millis();

  // Envía si: lleno, o timeout 4–8 ms sin bytes nuevos, y no enviando
  if (txCount > 0 && !txDone && (txCount >= MAX_PKT || (millis() - lastByteMs >= 5))) {
    digitalWrite(LORA_RXEN, LOW);
    digitalWrite(LORA_TXEN, HIGH);

    radio.startTransmit(txBuf, txCount);
    txCount = 0;
  }

  // Fin TX → back to RX
  if (txDone) {
    txDone = false;
    
    radio.finishTransmit(); // limpieza post-TX

    digitalWrite(LORA_TXEN, LOW);
    digitalWrite(LORA_RXEN, HIGH);

    // Limpieza crítica para evitar "stuck" en RX continuo
    radio.standby();
    radio.startReceive();  // fuerza reset de estado interno
  }
}
