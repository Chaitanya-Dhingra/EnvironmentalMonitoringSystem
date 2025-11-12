#include<WiFi.h>
#include<ThingSpeak.h>
#include<DHT.h>                  // including DHT SENSOR library
#include<Wire.h>              // library for i2c communication
#include<Adafruit_Sensor.h>           // standard interface  for Adafruit 
#include<Adafruit_BMP085_U.h>                  // bmp180 is just the newer version of this sensor , libraray is compatible 


const int mq2analog = 32 ; // A0 of mq2 is used 
const int mq135analog = 34 ;    // A0 of mq135 is used
// cretaing bmp sensor object: avoids confusio during use of multiple Adafruit sensors 
Adafruit_BMP085_Unified bmp = Adafruit_BMP085_Unified(100);     // any arbitrary number can be there in place of 100,
                                                            //  it's just to differentiate different adafruit sensors 

#define DHTPIN 33       
#define DHTTYPE DHT11   // informs library which sensor we are using
#define pm_led 12          // 12,15 are strapping pin 
#define pm_vo 15         // reads analog voltage from pm sensor 

DHT dht(DHTPIN , DHTTYPE);       // dht object is formed 


const  char* ssid ="2x9";
const  char* password = "geeu2025-26";
unsigned long channel_id = 3150540;
const  char* write_api = "ECNQVPZTGWSYMRRT";
WiFiClient Client;
void setup()
{
  Serial.begin(115200);

  // esp32 wifi stuff
  WiFi.begin(ssid , password);
  if ( WiFi.status() != WL_CONNECTED)
  {
    Serial.println("Connecting to Wifi.........");
    delay(100);
  }

  Serial.println("Wifi Connected ");
  ThingSpeak.begin(Client);

  // other stuffs
  pinMode(mq2analog,INPUT);      // mq2 pin initiated for taking input 
  pinMode(mq135analog , INPUT);     // MQ135 PIN IS INITIATED FOR TAKING INPUT
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

  // mq2 code - carbon monoxide 
  int mq2_read = analogRead(mq2analog);
  ThingSpeak.setField( 5,mq2_read);

  float mq2_per = (mq2_read/4095.0)*100.0;
  Serial.printf("CO : %0.2f %% \t\n",mq2_per);

  // DHT11 code - temperature and humidity
  //float temp = dht.readTemperature() ;    // reads temperature in celcius 
  float humi =dht.readHumidity()  ;       // reads humidity in percentage 

  if (isnan(humi))  
  {
    Serial.println("Humidity Data ⚠");
    ThingSpeak.setField(2 , humi);
  }
  else 
  {
    //Serial.printf("Temperature : %5.1f °C\n", temp);
    Serial.printf("Humidity    : %5.1f %%\t\n", humi);
  }

  // mq135 code - carbon dioxide 
  int mq135_read = analogRead(mq135analog);
  ThingSpeak.setField( 6, mq135_read);

  float mq135_perc = (mq135_read/4095.0)*100.0;
  Serial.printf("CO2: %.2f %%\t\n",mq135_perc);

  // pm code 
  digitalWrite(pm_led,LOW) ;        // when this pin is active low , led inside pm glows up
  delayMicroseconds(280) ;          // recommended 

  int pm_vo_read = analogRead(pm_vo);            // mc reads the data coming from pm during 280 us time interval
  delayMicroseconds(40);    //The ADC sampling capacitor settles,The photodiode signal is fully captured,No electrical noise affect the read

  digitalWrite(pm_led,HIGH);  // pm led is off now else it will be on for infinite time draining power
  delayMicroseconds(9680);    // for completing 100Hz (10msec = 280 +40+9680) cycle: LED to cool,Sensor chamber to clear,Photodiode to reset

  Serial.printf("PM SENSOR  : %d\T \n" , pm_vo_read);
  Serial.printf("ADC");
  ThingSpeak.setField( 7 , pm_vo_read);

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

  // checking whether data is sent to cloud or not 
  int status = ThingSpeak.writeFields(channel_id , write_api);
  if (status ==200)         // 200 is HTTP code for "OK"
  {
    Serial.println("All The readings Sent to Cloud");
  }
  else 
  {
    Serial.println("Data Not Sent To Cloud ");
  }
  
  delay(1500);
}