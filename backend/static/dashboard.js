// dashboard.js

const sensors = [
  "MQ2",
  "MQ135",
  "Humidity",
  "PM_Dust",
  "BMP_Pressure",
  "BMP_Temperature",
  "BMP_Altitude"
];

const sensorLabels = {
  "MQ2": "MQ2",
  "MQ135": "MQ135",
  "Humidity": "Humidity",
  "PM_Dust": "PM Dust",
  "BMP_Pressure": "Pressure",
  "BMP_Temperature": "Temperature",
  "BMP_Altitude": "Altitude"
};

let chart = null;

function buildDropdown() {
  const sel = document.getElementById("sensorSelect");
  sensors.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.text = sensorLabels[s] || s;
    sel.appendChild(opt);
  });
  sel.addEventListener("change", () => {
    const s = sel.value;
    loadTrend(s);
    updateSummary(s);
});

  // default selection
  sel.value = "MQ2";
}

async function fetchLatest() {
  const response = await fetch("/latest");
  return await response.json();
}

async function updateCards() {
  try {
    const data = await fetchLatest();
    document.getElementById("mq2_card").innerHTML = `MQ2<br>${data.MQ2 ?? "—"}`;
    document.getElementById("mq135_card").innerHTML = `MQ135<br>${data.MQ135 ?? "—"}`;
    document.getElementById("humidity_card").innerHTML = `Humidity<br>${data.Humidity ?? "—"}`;
    document.getElementById("pm_card").innerHTML = `PM Dust<br>${data.PM_Dust ?? "—"}`;
    document.getElementById("pressure_card").innerHTML = `Pressure<br>${data.BMP_Pressure ?? "—"}`;
    document.getElementById("temp_card").innerHTML = `Temperature<br>${data.BMP_Temperature ?? "—"}`;
    document.getElementById("altitude_card").innerHTML = `Altitude<br>${data.BMP_Altitude ?? "—"}`;
  } catch (e) {
    console.error("Failed to update cards", e);
  }
}

async function loadTrend(sensorName) {
  try {
    const res = await fetch(`/trend/${encodeURIComponent(sensorName)}`);
    if (!res.ok) {
      console.error("Trend fetch failed", res.status);
      return;
    }
    const json = await res.json();

    const labels = json.timestamps;            // 96 labels (HH:MM)
    const today = json.today.map(v => v === null ? null : Number(v));
    const hist = json.historical.map(v => v === null ? null : Number(v));

    const ctx = document.getElementById("sensorChart").getContext("2d");

    // If chart exists, update datasets, otherwise create
    if (chart) {
      chart.data.labels = labels;
      chart.data.datasets[0].data = today;
      chart.data.datasets[1].data = hist;
      chart.options.plugins.title.text = `${sensorLabels[sensorName] || sensorName} — Today vs Historical`;
      chart.update();
    } else {
      chart = new Chart(ctx, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Today",
              data: today,
              borderColor: "rgba(34,139,230,1)",
              backgroundColor: "rgba(34,139,230,0.12)",
              tension: 0.25,
              spanGaps: true,
              pointRadius: 2
            },
            {
              label: "Historical (15-min avg)",
              data: hist,
              borderColor: "rgba(255,165,0,1)",
              backgroundColor: "rgba(255,165,0,0.12)",
              tension: 0.25,
              spanGaps: true,
              pointRadius: 0
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            title: {
              display: true,
              text: `${sensorLabels[sensorName] || sensorName} — Today vs Historical`
            },
            legend: { position: "top" }
          },
          scales: {
            x: {
              display: true,
              ticks: { maxTicksLimit: 12 } // keep x-labels readable
            },
            y: {
              display: true,
              beginAtZero: false
            }
          }
        }
      });
    }

  } catch (err) {
    console.error("Error loading trend", err);
  }
}

async function updateSummary(sensorName) {
    try {
        const res = await fetch(`/daily-summary/${sensorName}`);
        const json = await res.json();

        document.getElementById("min_card").innerHTML =
            `Min:<br>${json.min ?? "—"}`;

        document.getElementById("max_card").innerHTML =
            `Max:<br>${json.max ?? "—"}`;

        document.getElementById("avg_card").innerHTML =
            `Avg:<br>${json.avg?.toFixed(2) ?? "—"}`;

    } catch (e) {
        console.error("Summary load failed", e);
    }
}


window.onload = function () {
  buildDropdown();
  updateCards();

  const selected = document.getElementById("sensorSelect").value;
  loadTrend(selected);
  updateSummary(selected);

  // refresh logic (cards update every 1 min)
  setInterval(updateCards, 60 * 1000);

  // refresh chart + summary every 5 minutes
  setInterval(() => {
      const s = document.getElementById("sensorSelect").value;
      loadTrend(s);
      updateSummary(s);
  }, 5 * 60 * 1000);
};