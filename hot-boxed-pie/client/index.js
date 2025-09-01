// Global state for current time range
let currentTimeRange = 24; // Default to 24 hours
let chartInstances = new Map(); // Store chart instances by box ID

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
          limit: 1000,
        }),
    );
    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`Error fetching measurements for box ${boxId}:`, error);
    return { measurements: [], sensors: [] };
  }
}

// Create or update temperature chart for a box
function updateChart(containerId, measurements, sensors) {
  const ctx = document.getElementById(containerId);
  if (!ctx) return; // Exit if container not found

  // Group measurements by sensor
  const sensorData = {};
  measurements.reverse().forEach((m) => {
    if (!sensorData[m.sensor_id]) {
      sensorData[m.sensor_id] = {
        name: m.sensor_name,
        timestamps: [],
        temperatures: [],
        humidities: [],
      };
    }
    sensorData[m.sensor_id].timestamps.push(
      new Date(m.timestamp).toLocaleString(),
    );
    sensorData[m.sensor_id].temperatures.push(m.temperature);
    sensorData[m.sensor_id].humidities.push(m.humidity);
  });

  // Get or create chart instance
  let chart = chartInstances.get(containerId);

  // Generate consistent colors for sensors (store in closure)
  const sensorColors = new Map();
  function getColorForSensor(sensorId) {
    if (!sensorColors.has(sensorId)) {
      const hue = (sensorColors.size * 137.5) % 360; // Golden angle for good color distribution
      sensorColors.set(sensorId, `hsl(${hue}, 70%, 50%)`);
    }
    return sensorColors.get(sensorId);
  }

  // Create datasets for each sensor
  const datasets = [];
  Object.entries(sensorData).forEach(([sensorId, data]) => {
    const color = getColorForSensor(sensorId);

    // Temperature dataset
    datasets.push({
      label: `${data.name} (°F)`,
      data: data.temperatures,
      borderColor: color,
      backgroundColor: color + "20",
      fill: false,
      tension: 0.4,
    });

    // Humidity dataset (hidden by default)
    if (data.humidities.some((h) => h !== null)) {
      datasets.push({
        label: `${data.name} Humidity (%)`,
        data: data.humidities,
        borderColor: color,
        backgroundColor: color + "10",
        fill: false,
        tension: 0.4,
        hidden: true, // or check previous state if updating
      });
    }
  });

  // Get timestamps from any sensor
  const labels = Object.values(sensorData)[0]?.timestamps || [];

  if (chart) {
    // Update existing chart
    chart.data.labels = labels;
    chart.data.datasets = datasets;
    chart.options.plugins.title.text = `Temperature & Humidity (Last ${currentTimeRange} hours)`;
    chart.update("none"); // Update without animation for real-time updates
  } else {
    // Create new chart
    chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: datasets,
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
          },
          x: {
            ticks: {
              maxTicksLimit: 8,
            },
          },
        },
        interaction: {
          intersect: false,
          mode: "index",
        },
      },
    });
    chartInstances.set(containerId, chart);
  }
}

// Update a single box's data
async function updateBoxData(boxId) {
  const { measurements } = await fetchMeasurements(boxId);
  if (measurements && measurements.length > 0) {
    updateChart(`chart-${boxId}`, measurements);

    // Update latest readings display
    const stats = getStats(measurements);
    const latestReadingsDiv = document.querySelector(
      `#box-${boxId} .latest-readings`,
    );
    if (latestReadingsDiv && stats) {
      // Group latest readings by sensor
      const sensorReadings = {};
      measurements.forEach((m) => {
        if (
          !sensorReadings[m.sensor_id] ||
          new Date(m.timestamp) >
            new Date(sensorReadings[m.sensor_id].timestamp)
        ) {
          sensorReadings[m.sensor_id] = m;
        }
      });

      // Update the display for each sensor
      Object.values(sensorReadings).forEach((reading) => {
        const sensorStatsDiv = latestReadingsDiv.querySelector(
          `#sensor-${reading.sensor_id}-stats`,
        );
        if (sensorStatsDiv) {
          sensorStatsDiv.innerHTML = `
                        <h3>${reading.sensor_name}</h3>
                        <p>Current: ${reading.temperature.toFixed(1)}°F</p>
                        ${reading.humidity ? `<p>Humidity: ${reading.humidity.toFixed(1)}%</p>` : ""}
                        <p><small>Updated: ${new Date(reading.timestamp).toLocaleString()}</small></p>
                    `;
        }
      });
    }
  }
}

// Function to update all box data
async function updateAllBoxData() {
  const boxes = await fetchBoxes();
  boxes.forEach((box) => updateBoxData(box.id));
}

// Initialize the dashboard
async function initDashboard() {
  const boxList = document.getElementById("boxList");
  const boxes = await fetchBoxes();

  if (boxes.length === 0) {
    boxList.innerHTML = "No boxes found. Create a box to get started.";
    return;
  }

  // Initial render of all boxes
  const boxPromises = boxes.map(async (box) => {
    const { measurements } = await fetchMeasurements(box.id);
    return {
      html: renderBox(box, measurements),
      measurements,
      id: box.id,
    };
  });

  const results = await Promise.all(boxPromises);
  boxList.innerHTML = results.map((result) => result.html).join("");

  // Initialize charts
  results.forEach((result) => {
    if (result.measurements.length > 0) {
      updateChart(`chart-${result.id}`, result.measurements);
    }
  });
}

// Create a temperature chart for a box
function createTemperatureChart(containerId, measurements, sensors) {
  const ctx = document.getElementById(containerId).getContext("2d");

  // Group measurements by sensor
  const sensorData = {};
  measurements.reverse().forEach((m) => {
    if (!sensorData[m.sensor_id]) {
      sensorData[m.sensor_id] = {
        name: m.sensor_name,
        timestamps: [],
        temperatures: [],
        humidities: [],
      };
    }
    sensorData[m.sensor_id].timestamps.push(
      new Date(m.timestamp).toLocaleString(),
    );
    sensorData[m.sensor_id].temperatures.push(m.temperature);
    sensorData[m.sensor_id].humidities.push(m.humidity);
  });

  // Generate random colors for sensors
  function getRandomColor() {
    const letters = "0123456789ABCDEF";
    let color = "#";
    for (let i = 0; i < 6; i++) {
      color += letters[Math.floor(Math.random() * 16)];
    }
    return color;
  }

  // Create datasets for each sensor
  const datasets = [];
  Object.entries(sensorData).forEach(([sensorId, data]) => {
    const color = getRandomColor();

    // Temperature dataset
    datasets.push({
      label: `${data.name} (°F)`,
      data: data.temperatures,
      borderColor: color,
      backgroundColor: color + "20", // Add transparency
      fill: false,
      tension: 0.4,
    });

    // Humidity dataset (hidden by default)
    if (data.humidities.some((h) => h !== null)) {
      datasets.push({
        label: `${data.name} Humidity (%)`,
        data: data.humidities,
        borderColor: color,
        backgroundColor: color + "10", // More transparent
        fill: false,
        tension: 0.4,
        hidden: true,
      });
    }
  });

  // Get timestamps from any sensor (they should all have the same timestamps)
  const labels = Object.values(sensorData)[0]?.timestamps || [];

  return new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: datasets,
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
        },
        x: {
          ticks: {
            maxTicksLimit: 8,
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

// Handle time range changes
function handleTimeRangeChange(event) {
  currentTimeRange = parseInt(event.target.value);
  initDashboard();
}

// Start the dashboard
document.getElementById("timeRange").addEventListener("change", (event) => {
  currentTimeRange = parseInt(event.target.value);
  chartInstances.clear(); // Clear existing chart instances
  initDashboard(); // Reinitialize with new time range
});

// Initialize dashboard and set up refresh interval
initDashboard();
setInterval(updateAllBoxData, 60000); // Update every minute
