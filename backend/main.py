from fastapi import FastAPI
from models import SensorData
from db import get_connection
from datetime import datetime, date, time, timedelta
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

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

@app.get("/daily-summary/{sensor_name}")
def daily_summary(sensor_name: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            MIN(value), 
            MAX(value), 
            AVG(value)
        FROM sensor_readings
        WHERE sensor_name = %s
          AND timestamp >= CURRENT_DATE
    """, (sensor_name,))

    row = cur.fetchone()
    conn.close()

    return {
        "min": float(row[0]) if row[0] is not None else None,
        "max": float(row[1]) if row[1] is not None else None,
        "avg": float(row[2]) if row[2] is not None else None
    }


app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/dashboard")
def dashboard():
    return FileResponse("static/dashboard.html")


@app.get("/latest")
def latest():
    conn = get_connection()
    cur = conn.cursor()

    sensors = [
        "MQ2", "MQ135", "Humidity", "PM_Dust",
        "BMP_Pressure", "BMP_Temperature", "BMP_Altitude"
    ]

    output = {}

    for s in sensors:
        cur.execute("""
            SELECT value FROM sensor_readings
            WHERE sensor_name = %s
            ORDER BY timestamp DESC LIMIT 1
        """, (s,))
        row = cur.fetchone()
        output[s] = row[0] if row else None

    conn.close()
    return output

@app.get("/trend/{sensor_name}")
def trend(sensor_name: str):
    """
    Returns:
      {
        "timestamps": ["00:00","00:15",...],    # 96 items
        "today": [val_or_null, ...],            # 96 items (last reading in each slot for today)
        "historical": [avg_or_null, ...]        # 96 items (avg of all previous days per slot)
      }
    Uses server's local date (IST for you).
    """
    conn = get_connection()
    cur = conn.cursor()

    # Historical averages for all days BEFORE today (slots 0..95)
    cur.execute("""
        SELECT
          floor((extract(hour from timestamp)::int * 60 + extract(minute from timestamp)::int) / 15)::int AS slot,
          AVG(value) AS avg_val
        FROM sensor_readings
        WHERE sensor_name = %s
          AND timestamp::date <= current_date
        GROUP BY slot;
    """, (sensor_name,))
    hist_rows = cur.fetchall()

    historical = [None] * 96
    for slot, avg_val in hist_rows:
        if avg_val is not None:
            historical[int(slot)] = float(avg_val)

    # Today's last reading in each slot (take the latest timestamp within the slot)
    cur.execute("""
        SELECT slot, value FROM (
          SELECT
            floor((extract(hour from timestamp)::int * 60 + extract(minute from timestamp)::int) / 15)::int AS slot,
            value,
            row_number() OVER (PARTITION BY floor((extract(hour from timestamp)::int * 60 + extract(minute from timestamp)::int) / 15)::int
                               ORDER BY timestamp DESC) AS rn
          FROM sensor_readings
          WHERE sensor_name = %s
            AND timestamp::date = current_date
        ) t
        WHERE rn = 1;
    """, (sensor_name,))
    today_rows = cur.fetchall()

    today = [None] * 96
    for slot, val in today_rows:
        if val is not None:
            today[int(slot)] = float(val)

    conn.close()

    # Build labels in 15-min steps (00:00 ... 23:45) using server local time (IST as requested)
    labels = []
    base = datetime.combine(date.today(), time(0, 0))
    for i in range(96):
        dt = base + timedelta(minutes=15 * i)
        labels.append(dt.strftime("%H:%M"))

    return {"timestamps": labels, "today": today, "historical": historical}

