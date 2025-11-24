from pydantic import BaseModel

class SensorData(BaseModel):
    sensor_name: str
    value: float
    timestamp: str | None = None
    device_id: str | None = None
