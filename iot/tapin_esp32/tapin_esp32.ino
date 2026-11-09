/*
  WorkTwin meeting tap-in reader
  ESP32 + RC522 (MFRC522) NFC reader. Members tap their student card at the start of a
  team meeting; the reader POSTs the card UID to the WorkTwin backend (Cloud Run).

  Wiring (RC522 -> ESP32 DevKit, SPI):
    SDA/SS -> GPIO 5     SCK  -> GPIO 18
    MOSI   -> GPIO 23    MISO -> GPIO 19
    RST    -> GPIO 22    3.3V -> 3V3   GND -> GND
  Optional: green LED on GPIO 2 (built-in on most boards), buzzer on GPIO 4.

  Libraries (Arduino Library Manager): "MFRC522" by GithubCommunity, "ArduinoJson" by Benoit Blanchon.
  Board: "ESP32 Dev Module" (Espressif ESP32 board package).
*/
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>
#include <ArduinoJson.h>

// ---------- fill these in ----------
const char* WIFI_SSID     = "YOUR_WIFI";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* API_URL       = "https://YOUR-CLOUD-RUN-URL/tapin";
const char* TEAM_ID       = "demo-team";          // the team this reader belongs to
const char* DEVICE_TOKEN  = "change-me";          // must match TAPIN_DEVICE_TOKEN on the backend
// -----------------------------------

#define SS_PIN  5
#define RST_PIN 22
#define LED_PIN 2
#define BUZZER_PIN 4

MFRC522 rfid(SS_PIN, RST_PIN);
String lastCard = "";
unsigned long lastTapMs = 0;

void beep(int times, int ms) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    tone(BUZZER_PIN, 2200, ms);
    delay(ms);
    digitalWrite(LED_PIN, LOW);
    delay(ms);
  }
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.println(" connected: " + WiFi.localIP().toString());
}

String readUid() {
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

void sendTap(const String& card) {
  if (WiFi.status() != WL_CONNECTED) connectWifi();

  WiFiClientSecure client;
  client.setInsecure();  // prototype only: skips certificate checks. Pin the Google root CA for production.
  HTTPClient http;
  http.begin(client, API_URL);
  http.addHeader("Content-Type", "application/json");

  JsonDocument body;
  body["team"] = TEAM_ID;
  body["card"] = card;
  body["token"] = DEVICE_TOKEN;
  String payload;
  serializeJson(body, payload);

  int code = http.POST(payload);
  String resp = http.getString();
  http.end();
  Serial.printf("POST %d %s\n", code, resp.c_str());

  JsonDocument out;
  if (code == 200 && !deserializeJson(out, resp) && out["known"] == true) {
    Serial.printf("Welcome, %s\n", (const char*)out["name"]);
    beep(1, 120);   // one beep: checked in
  } else {
    beep(3, 80);    // three beeps: unknown card or error (link the card in the app)
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  SPI.begin();
  rfid.PCD_Init();
  connectWifi();
  Serial.println("Tap a student card...");
}

void loop() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;
  String card = readUid();
  // ignore the same card held on the reader for a few seconds
  if (card == lastCard && millis() - lastTapMs < 5000) return;
  lastCard = card;
  lastTapMs = millis();
  Serial.println("Card: " + card);
  sendTap(card);
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}
