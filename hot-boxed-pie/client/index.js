// Global state for current time range
let currentTimeRange = 24; // Default to 24 hours

// Helper function to format date for API
function formatDate(date) {
  return date.toISOString().split(".")[0] + "Z";
}

// Get date range for API query
function getDateRange(hours) {
  const end = new Date();
  const start = new Date(end - hours * 60 * 60 * 1000);
  return {
    start: formatDate(start),
    end: formatDate(end),
  };
}

// Fetch all boxes and their latest measurements
async function fetchBoxes() {
  try {
    const response = await fetch("/api/box");
    const boxes = await response.json();
    return boxes;
  } catch (error) {
    console.error("Error fetching boxes:", error);
    return [];
  }
}

// Fetch measurements for a specific box
async function fetchMeasurements(boxId) {
  try {
    const dateRange = getDateRange(currentTimeRange);
    const response = await fetch(
      `/api/box/${boxId}/measurements?` +
        new URLSearchParams({
          start_time: dateRange.start,
          end_time: dateRange.end,
          limit: 1000, // Increased limit for better resolution
        }),
    );
    const data = await response.json();
    return data.measurements;
  } catch (error) {
    console.error(`Error fetching measurements for box ${boxId}:`, error);
    return [];
  }
}

// Create a temperature chart for a box
function createTemperatureChart(containerId, measurements) {
  const ctx = document.getElementById(containerId).getContext("2d");

  // Reverse measurements to show oldest to newest
  const chartData = measurements.reverse();

  const labels = chartData.map((m) => new Date(m.timestamp).toLocaleString());
  const temperatures = chartData.map((m) => m.temperature);
  const humidities = chartData.map((m) => m.humidity);

  return new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Temperature (°F)",
          data: temperatures,
          borderColor: "rgb(255, 99, 132)",
          backgroundColor: "rgba(255, 99, 132, 0.1)",
          fill: true,
          tension: 0.4,
        },
        {
          label: "Humidity (%)",
          data: humidities,
          borderColor: "rgb(54, 162, 235)",
          backgroundColor: "rgba(54, 162, 235, 0.1)",
          fill: true,
          tension: 0.4,
          hidden: true, // Hidden by default, can be toggled
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: `Temperature & Humidity (Last ${currentTimeRange} hours)`,
        },
        tooltip: {
          mode: "index",
          intersect: false,
        },
      },
      scales: {
        y: {
          beginAtZero: false,
          ticks: {
            callback: function (value) {
              return value + (this.chart.data.datasets[0].hidden ? "%" : "°F");
            },
          },
        },
        x: {
          ticks: {
            maxTicksLimit: 8, // Limit the number of x-axis labels
          },
        },
      },
      interaction: {
        intersect: false,
        mode: "index",
      },
    },
  });
}

// Get stats from measurements
function getStats(measurements) {
  if (measurements.length === 0) return null;

  const temperatures = measurements.map((m) => m.temperature);
  const humidities = measurements
    .filter((m) => m.humidity)
    .map((m) => m.humidity);

  return {
    temp: {
      current: temperatures[temperatures.length - 1].toFixed(1),
      min: Math.min(...temperatures).toFixed(1),
      max: Math.max(...temperatures).toFixed(1),
      avg: (
        temperatures.reduce((a, b) => a + b, 0) / temperatures.length
      ).toFixed(1),
    },
    humidity: humidities.length
      ? {
          current: humidities[humidities.length - 1].toFixed(1),
          min: Math.min(...humidities).toFixed(1),
          max: Math.max(...humidities).toFixed(1),
          avg: (
            humidities.reduce((a, b) => a + b, 0) / humidities.length
          ).toFixed(1),
        }
      : null,
  };
}

// Render a single box with its measurements and chart
function renderBox(box, measurements) {
  const stats = getStats(measurements);
  const chartId = `chart-${box.id}`;

  return `
        <div class="box-item">
            <h2>${box.name || "Unnamed Box"}</h2>
            <p>Location: ${box.location || "No location set"}</p>

            ${
              stats
                ? `
                <div class="data-grid">
                    <div class="latest-readings">
                        <h3>Temperature</h3>
                        <p>Current: ${stats.temp.current}°F</p>
                        <p>Min: ${stats.temp.min}°F</p>
                        <p>Max: ${stats.temp.max}°F</p>
                        <p>Average: ${stats.temp.avg}°F</p>
                    </div>
                    ${
                      stats.humidity
                        ? `
                        <div class="latest-readings">
                            <h3>Humidity</h3>
                            <p>Current: ${stats.humidity.current}%</p>
                            <p>Min: ${stats.humidity.min}%</p>
                            <p>Max: ${stats.humidity.max}%</p>
                            <p>Average: ${stats.humidity.avg}%</p>
                        </div>
                    `
                        : ""
                    }
                </div>
                <div class="chart-container">
                    <canvas id="${chartId}"></canvas>
                </div>
            `
                : "<p>No measurements available</p>"
            }
        </div>
    `;
}

// Initialize the dashboard
async function initDashboard() {
  const boxList = document.getElementById("boxList");
  const boxes = await fetchBoxes();

  if (boxes.length === 0) {
    boxList.innerHTML = "No boxes found. Create a box to get started.";
    return;
  }

  // Fetch measurements for each box and render them
  const boxPromises = boxes.map(async (box) => {
    const measurements = await fetchMeasurements(box.id);
    return {
      html: renderBox(box, measurements),
      measurements,
      id: box.id,
    };
  });

  const results = await Promise.all(boxPromises);

  // Render all boxes
  boxList.innerHTML = results.map((result) => result.html).join("");

  // Initialize charts after DOM elements are created
  results.forEach((result) => {
    if (result.measurements.length > 0) {
      createTemperatureChart(`chart-${result.id}`, result.measurements);
    }
  });
}

// Handle time range changes
function handleTimeRangeChange(event) {
  currentTimeRange = parseInt(event.target.value);
  initDashboard();
}

// Start the dashboard
document
  .getElementById("timeRange")
  .addEventListener("change", handleTimeRangeChange);
initDashboard();

// Refresh data periodically (every minute)
setInterval(initDashboard, 60000);
