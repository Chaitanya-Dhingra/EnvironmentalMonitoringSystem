from fastapi import FastAPI
from models import SensorData
from db import get_connection
from datetime import datetime

app = FastAPI()

import os
from fastapi import FastAPI

app = FastAPI()

@app.get("/debug-env")
def debug_env():
    return {
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_PORT": os.getenv("DB_PORT"),
        "DB_USER": os.getenv("DB_USER"),
        "DB_NAME": os.getenv("DB_NAME"),
        "DB_PASS_MASKED": None if os.getenv("DB_PASS") is None else "****(set)"
    }
@app.get("/")
def home():
    return {"message": "IoT API is running!"}

@app.post("/add")
def add_sensor_data(data: SensorData):
    conn = get_connection()
    cursor = conn.cursor()

    # Use current time if timestamp is not sent
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
