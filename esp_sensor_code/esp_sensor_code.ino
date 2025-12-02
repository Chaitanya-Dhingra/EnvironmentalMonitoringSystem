#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP085_U.h>

// --------------------------------------
// SENSOR PINS
// --------------------------------------
const int mq2analog = 32;
const int miscellaneous_gases = 34;

#define DHTPIN 33
#define DHTTYPE DHT11

#define pm_led 12
#define pm_vo 35

// BMP180 Object
Adafruit_BMP085_Unified bmp = Adafruit_BMP085_Unified(100);

// DHT Object
DHT dht(DHTPIN, DHTTYPE);

// --------------------------------------
// WIFI
// --------------------------------------
const char* ssid = "CD OnePlus 13R";
const char* password = "dhingra@1801";

// --------------------------------------
// FASTAPI SERVER URL
// --------------------------------------
// !! CHANGE THIS TO YOUR PC's IPv4 !!
const char* serverURL = "http://10.85.246.106:8000/add-batch";

// Device ID
String device_id = "NODE_01";


// ----------------------------------------------------
// FUNCTION: SEND DATA TO FASTAPI SERVER
// ----------------------------------------------------
void sendToServer(
  float mq2, float mq135, float humi, float pm,
  float pressure, float temp, float altitude
) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected — cannot upload.");
    return;
  }

  HTTPClient http;
  http.begin(serverURL);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<300> doc;
  doc["device_id"] = device_id;
  doc["mq2"] = mq2;
  doc["mq135"] = mq135;
  doc["humidity"] = humi;
  doc["pm_dust"] = pm;
  doc["bmp_pressure"] = pressure;
  doc["bmp_temp"] = temp;
  doc["bmp_altitude"] = altitude;

  String jsonData;
  serializeJson(doc, jsonData);

  Serial.println("\n=== Uploading JSON ===");
  Serial.println(jsonData);

  int httpCode = http.POST(jsonData);

  if (httpCode > 0) {
    Serial.printf("Server Response [%d]: ", httpCode);
    Serial.println(http.getString());
  } else {
    Serial.printf("POST Failed: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();
}



// ----------------------------------------------------
// SENSOR READINGS
// ----------------------------------------------------
float readMQ2() {
  int raw = analogRead(mq2analog);
  float percent = (raw / 4095.0) * 100.0;
  Serial.printf("CO (MQ2): %.2f %%\n", percent);
  return percent;
}

float readMQ135() {
  int raw = analogRead(miscellaneous_gases);
  float percent = (raw / 4095.0) * 100.0;
  Serial.printf("Misc Gases (MQ135): %.2f %%\n", percent);
  return percent;
}

float readHumidity() {
  float humi = dht.readHumidity();
  if (isnan(humi)) {
    Serial.println("Humidity ERROR\n");
    return -1;
  }
  Serial.printf("Humidity: %.2f %%\n", humi);
  return humi;
}

float readDust() {
  digitalWrite(pm_led, LOW);
  delayMicroseconds(280);

  int raw = analogRead(pm_vo);
  delayMicroseconds(40);

  digitalWrite(pm_led, HIGH);
  delayMicroseconds(9680);

  float voltage = (raw / 4095.0) * 3.3;

  float Voc = 0.6;
  float K = 0.35;

  float dustDensity = (voltage - Voc) / K;
  if (dustDensity < 0) dustDensity = 0;

  Serial.printf("Dust Density: %.3f mg/m³\n", dustDensity);

  return dustDensity;
}

float pressure_val = 0, temp_val = 0, altitude_val = 0;

void readBMP180() {
  sensors_event_t event;
  bmp.getEvent(&event);

  if (event.pressure) {
    pressure_val = event.pressure;
    bmp.getTemperature(&temp_val);

    altitude_val = bmp.pressureToAltitude(1013.25, event.pressure);

    Serial.printf("Pressure: %.2f hPa\n", pressure_val);
    Serial.printf("Temperature: %.2f °C\n", temp_val);
    Serial.printf("Altitude: %.2f m\n", altitude_val);
  } else {
    Serial.println("BMP180 ERROR!");
  }
}



// ----------------------------------------------------
// SETUP
// ----------------------------------------------------
void setup() {
  Serial.begin(115200);
  dht.begin();

  WiFi.begin(ssid, password);
  Serial.println("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }
  Serial.println("\nWiFi Connected!");

  pinMode(mq2analog, INPUT);
  pinMode(miscellaneous_gases, INPUT);
  pinMode(pm_led, OUTPUT);
  pinMode(pm_vo, INPUT);

  Wire.begin(21, 22);

  if (!bmp.begin()) {
    Serial.println("BMP180 NOT DETECTED!");
  }

  Serial.println("=== System Ready ===");
}



// ----------------------------------------------------
// MAIN LOOP
// ----------------------------------------------------
void loop() {
  Serial.println("\n==== Environmental Snapshot ====");

  float mq2 = readMQ2();
  float mq135 = readMQ135();
  float humi = readHumidity();
  float dust = readDust();

  readBMP180(); // updates global variables
  delay(200);

  // UPLOAD TO SERVER
  sendToServer(
    mq2,
    mq135,
    humi,
    dust,
    pressure_val,
    temp_val,
    altitude_val
  );

  delay(15 * 60 * 1000);   // 15 minutes
}
