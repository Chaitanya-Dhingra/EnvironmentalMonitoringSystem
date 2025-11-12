from flask import Flask, render_template, jsonify
import numpy as np
import datetime

app = Flask(__name__)

def get_sensor_data():
    times = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
    today_data = np.random.randint(20, 40, size=48).tolist()
    historical_avg = np.random.randint(25, 35, size=48).tolist()
    return times, today_data, historical_avg

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/data")
def api_data():
    times, today_data, historical_avg = get_sensor_data()
    return jsonify({
        "times": times,
        "today": today_data,
        "average": historical_avg
    })

if __name__ == "__main__":
    app.run(debug=True)
