from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import os
import smtplib
from email.mime.text import MIMEText

from db import get_connection
from models import SensorData


# =====================================================
#  BREVO EMAIL ALERT SYSTEM (100% WORKING)
# =====================================================

def send_email_alert(subject: str, body: str):
    sender = os.getenv("ALERT_EMAIL")               # your verified sender
    receiver = os.getenv("ALERT_TO")                # where the alert goes
    smtp_username = os.getenv("SMTP_USERNAME")      # Brevo SMTP login
    smtp_password = os.getenv("SMTP_PASSWORD")      # Brevo SMTP key
    smtp_server = os.getenv("SMTP_SERVER", "smtp-relay.brevo.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    if not all([sender, receiver, smtp_username, smtp_password]):
        print("⚠ Email alerts DISABLED — missing SMTP settings.")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=20)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender, [receiver], msg.as_string())
        server.quit()
        print("📧 Email sent successfully via Brevo!")
    except Exception as e:
        print("❌ Email send FAILED:", e)


# =====================================================
#  ALERT THRESHOLDS
# =====================================================

THRESHOLDS = {
    "MQ2": {"high": 40, "low": 35, "cooldown_min": 30},
    "MQ135": {"high": 30, "low": 25, "cooldown_min": 30},
    "Humidity": {"high": 90, "low": 85, "cooldown_min": 60},
    "PM_Dust": {"high": 0.5, "low": 0.4, "cooldown_min": 15},
    "BMP_Pressure": {
        "high": 1030, "low": 1020,
        "low2": 910, "high2": 900,
        "cooldown_min": 60
    },
    "BMP_Temperature": {"high": 32, "low": 30, "cooldown_min": 30}
}


def check_alert_needed(sensor, value):
    if sensor not in THRESHOLDS:
        return None

    t = THRESHOLDS[sensor]

    if "high" in t and value > t["high"]:
        return f"{sensor} ALERT: Value {value} above safe limit!"

    if "low" in t and value < t["low"]:
        return None

    if sensor == "BMP_Pressure":
        if value < t["high2"]:
            return f"LOW PRESSURE ALERT: {value} hPa!"

    return None


def should_send_alert(conn, sensor):
    cur = conn.cursor()
    cur.execute("SELECT last_alert FROM sensor_alerts WHERE sensor_name = %s", (sensor,))
    row = cur.fetchone()

    if not row or not row[0]:
        return True

    last_alert = row[0]
    cooldown = timedelta(minutes=THRESHOLDS[sensor]["cooldown_min"])

    return (datetime.now() - last_alert) >= cooldown


def register_alert(conn, sensor, value, message):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sensor_alerts (sensor_name, last_alert, last_value, message)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (sensor_name)
        DO UPDATE SET 
            last_alert = EXCLUDED.last_alert,
            last_value = EXCLUDED.last_value,
            message = EXCLUDED.message;
    """, (sensor, datetime.now(), value, message))
    conn.commit()


# =====================================================
#  FASTAPI APP
# =====================================================

app = FastAPI()


# =====================================================
#  TEST EMAIL ENDPOINT (NEW!)
# =====================================================
@app.get("/test-email")
def test_email():
    try:
        send_email_alert("Test Email", "This is a test email from your IoT Monitoring System (Brevo SMTP).")
        return {"status": "sent"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# =====================================================
#  SENSOR INSERTION
# =====================================================
@app.get("/")
def home():
    return {"status": "running", "message": "IoT API is live"}


@app.post("/add")
def add_sensor_data(data: SensorData):
    conn = get_connection()
    cur = conn.cursor()

    timestamp = data.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
        INSERT INTO sensor_readings (sensor_name, value, timestamp, device_id)
        VALUES (%s, %s, %s, %s)
    """, (data.sensor_name, data.value, timestamp, data.device_id))

    conn.commit()
    conn.close()

    return {"status": "ok"}


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

    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    timestamp = ist_now.strftime("%Y-%m-%d %H:%M:%S")

    def insert(sensor_name, value):
        if value is None:
            return

        alert_msg = check_alert_needed(sensor_name, value)
        if alert_msg and should_send_alert(conn, sensor_name):
            send_email_alert(f"{sensor_name} Alert", alert_msg)
            register_alert(conn, sensor_name, value, alert_msg)

        cur.execute("""
            INSERT INTO sensor_readings (sensor_name, value, timestamp, device_id)
            VALUES (%s, %s, %s, %s)
        """, (sensor_name, value, timestamp, data.device_id))

    insert("MQ2", data.mq2)
    insert("MQ135", data.mq135)
    insert("Humidity", data.humidity)
    insert("PM_Dust", data.pm_dust)
    insert("BMP_Pressure", data.bmp_pressure)
    insert("BMP_Temperature", data.bmp_temp)
    insert("BMP_Altitude", data.bmp_altitude)

    conn.commit()
    conn.close()

    return {"status": "ok", "timestamp_ist": timestamp}


# =====================================================
#  STATIC FILES (Dashboard)
# =====================================================
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/dashboard")
def dashboard():
    return FileResponse("static/dashboard.html")


# =====================================================
#  LATEST READINGS
# =====================================================

@app.get("/latest")
def latest():
    conn = get_connection()
    cur = conn.cursor()

    sensors = [
        "MQ2", "MQ135", "Humidity", "PM_Dust",
        "BMP_Pressure", "BMP_Temperature", "BMP_Altitude"
    ]

    out = {}
    for s in sensors:
        cur.execute("""
            SELECT value
            FROM sensor_readings
            WHERE sensor_name = %s
            ORDER BY timestamp DESC LIMIT 1
        """, (s,))
        row = cur.fetchone()
        out[s] = row[0] if row else None

    conn.close()
    return out


# =====================================================
#  TREND (15-MIN SLOTS, TODAY + HISTORICAL)
# =====================================================

@app.get("/trend/{sensor_name}")
def trend(sensor_name: str):
    ist = ZoneInfo("Asia/Kolkata")
    today = datetime.now(ist).date()

    conn = get_connection()
    cur = conn.cursor()

    # Historical averages
    cur.execute("""
        SELECT
          FLOOR((EXTRACT(HOUR FROM timestamp) * 60 +
                 EXTRACT(MINUTE FROM timestamp)) / 15)::int AS slot,
          AVG(value)
        FROM sensor_readings
        WHERE sensor_name = %s
        GROUP BY slot;
    """, (sensor_name,))
    historical_rows = cur.fetchall()

    historical = [None] * 96
    for slot, avg in historical_rows:
        if 0 <= slot < 96:
            historical[slot] = float(avg)

    # Today's latest readings per slot
    cur.execute("""
        SELECT slot, value FROM (
            SELECT
              FLOOR((EXTRACT(HOUR FROM timestamp) * 60 +
                     EXTRACT(MINUTE FROM timestamp)) / 15)::int AS slot,
              value,
              ROW_NUMBER() OVER (
                PARTITION BY FLOOR((EXTRACT(HOUR FROM timestamp) * 60 +
                                    EXTRACT(MINUTE FROM timestamp)) / 15)
                ORDER BY timestamp DESC
              ) AS rn
            FROM sensor_readings
            WHERE sensor_name = %s
              AND timestamp::date = %s
        ) t
        WHERE rn = 1;
    """, (sensor_name, today))

    today_list = [None] * 96
    for slot, val in cur.fetchall():
        if 0 <= slot < 96:
            today_list[slot] = float(val)

    conn.close()

    # Time labels
    labels = []
    base = datetime.combine(today, time(0, 0), ist)
    for i in range(96):
        labels.append((base + timedelta(minutes=15 * i)).strftime("%H:%M"))

    return {
        "timestamps": labels,
        "today": today_list,
        "historical": historical
    }


# =====================================================
#  DAILY SUMMARY
# =====================================================

@app.get("/daily-summary/{sensor_name}")
def daily_summary(sensor_name: str):
    ist = ZoneInfo("Asia/Kolkata")
    today = datetime.now(ist).date()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT MIN(value), MAX(value), AVG(value)
        FROM sensor_readings
        WHERE sensor_name = %s
          AND timestamp::date = %s
    """, (sensor_name, today))

    m = cur.fetchone()
    conn.close()

    return {
        "min": float(m[0]) if m[0] else None,
        "max": float(m[1]) if m[1] else None,
        "avg": float(m[2]) if m[2] else None
    }