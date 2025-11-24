#include<WiFi.h>
#include<ThingSpeak.h>
#include<DHT.h>                  // including DHT SENSOR library
#include<Wire.h>              // library for i2c communication
#include<Adafruit_Sensor.h>           // standard interface  for Adafruit 
#include<Adafruit_BMP085_U.h>                  // bmp180 is just the newer version of this sensor , libraray is compatible 


const int mq2analog = 32 ; // A0 of mq2 is used 
const int miscellaneous_gases = 34 ;    // A0 of mq135 is used
// cretaing bmp sensor object: avoids confusio during use of multiple Adafruit sensors 
Adafruit_BMP085_Unified bmp = Adafruit_BMP085_Unified(100);     // any arbitrary number can be there in place of 100,
                                                            //  it's just to differentiate different adafruit sensors 

#define DHTPIN 33       
#define DHTTYPE DHT11   // informs library which sensor we are using
#define pm_led 12          // 12,15 are strapping pin 
#define pm_vo 35         // reads analog voltage from pm sensor 

DHT dht(DHTPIN , DHTTYPE);       // dht object is formed 


const  char* ssid ="2x9";
const  char* password = "geeu2025-26";
unsigned long channel_id = 3160929;
const  char* write_api = "D00EZGQ59RTMHZVT";
WiFiClient Client;

// checking whether data is sent to cloud or not 
void data_cloud( int retry)
{
  int status = ThingSpeak.writeFields(channel_id , write_api);
  if (status ==200)         // 200 is HTTP code for "OK"
  {
    Serial.println("All The readings Sent to Cloud");
  }
  else if (retry>0)
  {
    Serial.println("Retrying..");
    delay(5000);  //Avoids Hammering ThingSpeak, 5 seconds gives ESP32 time to stabilize , Prevents Stack Overflow
    data_cloud(retry -1 );
  }

  else 
  {
    Serial.println("Data not sent to cloud ");
  }
}

void mq2_read()
{
  // mq2 code - carbon monoxide 
  int mq2_read = analogRead(mq2analog);
  ThingSpeak.setField( 5,mq2_read);

  float mq2_per = (mq2_read/4095.0)*100.0;
  Serial.printf("CO : %0.2f %% \t\n",mq2_per);
}

void miscellaneous_gases_read()
{
  // mq135 code - carbon dioxide 
  int miscellaneous_gases_read = analogRead(miscellaneous_gases);
  ThingSpeak.setField( 6, miscellaneous_gases_read);

  float miscellaneous_gases_perc = (miscellaneous_gases_read/4095.0)*100.0;
  Serial.printf("miscellaneous gases: %.2f %%\t\n", miscellaneous_gases_perc);
}

void humi_read()
{
  // DHT11 code - temperature and humidity
  //float temp = dht.readTemperature() ;    // reads temperature in celcius 
  float humi =dht.readHumidity()  ;       // reads humidity in percentage 

  if (isnan(humi))  
  {
    Serial.println("Humidity Data ⚠");
  }
  else 
  {
    //Serial.printf("Temperature : %5.1f °C\n", temp);
    ThingSpeak.setField(2 , humi);
    Serial.printf("Humidity    : %5.1f %%\t\n", humi);
  }
}

void pm_read()
{
  // pm code 
  digitalWrite(pm_led,LOW) ;        // when this pin is active low , led inside pm glows up
  delayMicroseconds(280) ;          // recommended 

  int pm_vo_read = analogRead(pm_vo);            // mc reads the data coming from pm during 280 us time interval
  delayMicroseconds(40);    //The ADC sampling capacitor settles,The photodiode signal is fully captured,No electrical noise affect the read

  digitalWrite(pm_led,HIGH);  // pm led is off now else it will be on for infinite time draining power
  delayMicroseconds(9680);    // for completing 100Hz (10msec = 280 +40+9680) cycle: LED to cool,Sensor chamber to clear,Photodiode to reset

  // Convert ADC to voltage (ESP32: 12-bit ADC, 3.3V reference)
  float voltage = (pm_vo_read / 4095.0) * 3.3;

  // Adjusted constants for 3.3V supply
  float Voc = 0.6;  // Baseline voltage at 3.3V (empirically lower than 0.9V)
  float K = 0.35;   // Sensitivity constant (lower LED current → lower slope)

  // Estimate dust density (mg/m³)
  float dustDensity = (voltage - Voc) / K;
  if (dustDensity < 0) dustDensity = 0;

  // Print evaluator-friendly output
  Serial.printf("Dust=%.3f mg/m³\n", dustDensity);

  // Upload dust density to ThingSpeak (Field 7)
  ThingSpeak.setField(7, dustDensity);
}

void bmp180_read()
{
  // bmp180 code 
  sensors_event_t event;            // event object is created to read pressure values 
  bmp.getEvent(&event);            // reading the value of pressure 
  if (event.pressure)
  {
    Serial.printf("Pressure:\t");
    Serial.print(event.pressure);
    Serial.println("hPa");                // hPa is hectopascal
    ThingSpeak.setField( 3 , event.pressure);

    float temperature ;
    bmp.getTemperature(&temperature);         // reads temperature values 
    Serial.printf("Temperature:\t");
    Serial.print(temperature);
    Serial.println("°C");
    ThingSpeak.setField( 1 ,  temperature);

    // altitude ( calculated from pressure )
    float sea_pressure = 1013.25;           // pressure at sea level in hectopascal
    float altitude = bmp.pressureToAltitude(sea_pressure,event.pressure);
    Serial.printf("Altitude:\t");
    Serial.print(altitude);
    Serial.println("m");
    ThingSpeak.setField( 4 , altitude);
  }

  else 
  {
    Serial.println("Pressure reading falied 🔔🔔🔔");
  }
}

void setup()
{
  Serial.begin(115200);

  // esp32 wifi stuff
  WiFi.begin(ssid , password);
  Serial.println("Connecting to WiFi.");
  while ( WiFi.status() != WL_CONNECTED)
  {
    delay(500);   // practical balance between responsiveness and stability
    Serial.println(".");
  }

  Serial.println("WiFi Connected ");
  ThingSpeak.begin(Client);

  // other stuffs
  pinMode(mq2analog,INPUT);      // mq2 pin initiated for taking input 
  pinMode(miscellaneous_gases , INPUT);     // MQ135 PIN IS INITIATED FOR TAKING INPUT
  pinMode(pm_led , OUTPUT);              // led has to glow 
  pinMode(pm_vo , INPUT);

  Wire.begin(21,22);    // initialises i2c communication for SDA , SCK

  // initialising bmp sensor 
  if (!bmp.begin())
  {
    Serial.println("BMP is not working ");
    return ;
  }
  Serial.println("==================================");
}

void loop()
{
  Serial.println("\n==== Environmental Snapshot ====");
  mq2_read();
  miscellaneous_gases_read();
  humi_read();
  pm_read();
  bmp180_read();
  data_cloud(3);
  delay(15000);   // minimum rate to send data to cloud 
  //If  data sent faster than every 15 seconds, ThingSpeak will reject the request
}