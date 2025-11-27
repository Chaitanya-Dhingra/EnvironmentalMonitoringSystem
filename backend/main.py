from fastapi import FastAPI
from models import SensorData
from db import get_connection
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import os

app = FastAPI()

# ----------------------------
# DEBUG ENDPOINT
# ----------------------------
@app.get("/debug-env")
def debug_env():
    return {
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_PORT": os.getenv("DB_PORT"),
        "DB_USER": os.getenv("DB_USER"),
        "DB_NAME": os.getenv("DB_NAME"),
        "DB_PASS_MASKED": None if os.getenv("DB_PASS") is None else "****(set)"
    }

# ----------------------------
# HOME
# ----------------------------
@app.get("/")
def home():
    return {"message": "IoT API is running!"}

# ----------------------------
# SINGLE SENSOR INSERT
# ----------------------------
@app.post("/add")
def add_sensor_data(data: SensorData):
    conn = get_connection()
    cursor = conn.cursor()

    timestamp = data.timestamp if data.timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sql = """
        INSERT INTO sensor_readings (sensor_name, value, timestamp, device_id)
        VALUES (%s, %s, %s, %s)
    """

    cursor.execute(sql, (data.sensor_name, data.value, timestamp, data.device_id))
    conn.commit()

    cursor.close()
    conn.close()

    return {"status": "ok", "message": "Data inserted successfully!"}

# ----------------------------
# BATCH INSERT ENDPOINT
# ----------------------------
class BatchData(BaseModel):
    device_id: str
    mq2: Optional[float] = None
    mq135: Optional[float] = None
    humidity: Optional[float] = None
    pm_dust: Optional[float] = None
    bmp_pressure: Optional[float] = None
    bmp_temp: Optional[float] = None
    bmp_altitude: Optional[float] = None


@app.post("/add-batch")
def add_batch(data: BatchData):
    conn = get_connection()
    cur = conn.cursor()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def insert(sensor_name, value):
        if value is None:
            return
        cur.execute(
            """
            INSERT INTO sensor_readings (sensor_name, value, timestamp, device_id)
            VALUES (%s, %s, %s, %s)
            """,
            (sensor_name, value, timestamp, data.device_id)
        )

    insert("MQ2", data.mq2)
    insert("MQ135", data.mq135)
    insert("Humidity", data.humidity)
    insert("PM_Dust", data.pm_dust)
    insert("BMP_Pressure", data.bmp_pressure)
    insert("BMP_Temperature", data.bmp_temp)
    insert("BMP_Altitude", data.bmp_altitude)

    conn.commit()
    cur.close()
    conn.close()

    return {"status": "ok", "message": "Batch inserted"}
