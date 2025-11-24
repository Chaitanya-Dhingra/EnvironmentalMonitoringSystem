async function fetchData() {
    const response = await fetch("/api/data");
    const data = await response.json();
    return data;
}

async function renderChart() {
    const data = await fetchData();

    const ctx = document.getElementById('sensorChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.times,   // X-axis (time)
            datasets: [
                {
                    label: "Today's Data",
                    data: data.today,
                    borderColor: 'blue',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.1
                },
                {
                    label: "Historical Average",
                    data: data.average,
                    borderColor: 'red',
                    borderDash: [5, 5],
                    borderWidth: 2,
                    fill: false,
                    tension: 0.1
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: "Today's Trend vs Historical Average"
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: "Time of Day"
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: "Sensor Value"
                    }
                }
            }
        }
    });
}

renderChart();
