import express from "express";
import { initializeDatabase } from "./db.js";
import { fileURLToPath } from "url";
import path from "path";
import mqtt from "mqtt";
// Import routes
import boxesRouter from "./routes/boxRoutes.js";
import sensorsRouter from "./routes/sensorRoutes.js";
import measurementsRouter from "./routes/measurementRoutes.js";
import { handleMeasurementMsg } from "./msgs/measurementMsgs.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = 3000;
const mqttBroker = "mqtt://localhost:1883"; // Change this to your MQTT broker URL

// Initialize MQTT client
const mqttClient = mqtt.connect(mqttBroker);

// MQTT connection handling
mqttClient.on("connect", () => {
  console.log("Connected to MQTT broker");

  // Subscribe to relevant topics
  mqttClient.subscribe("hotbox/+/measurement", (err) => {
    if (!err) {
      console.log("Subscribed to measurment topics");
    }
  });
});

// Handle incoming MQTT messages
mqttClient.on("message", async (topic, message) => {
  try {
    const [prefix, id, type] = topic.split("/");

    if (prefix !== "hotbox") {
      throw new Error("Invalid topic prefix");
    }

    const boxId = parseInt(id);
    const box = await getBoxById(boxId);
    if (!box) {
      throw new Error("Box not found");
    }

    const payload = JSON.parse(message.toString());

    // Validate payload has required fields
    if (!payload || typeof payload !== "object") {
      throw new Error("Invalid message format - expected JSON object");
    }

    await handleMeasurementMsg(boxId, type, payload);
  } catch (error) {
    console.error("Error processing MQTT message:", error);
    console.error("Message content:", message.toString());
  }
});

// Handle MQTT errors
mqttClient.on("error", (error) => {
  console.error("MQTT Error:", error);
});

// Middleware
app.use(express.json());
app.use(express.static(path.join(__dirname, "client")));

await initializeDatabase();

app.use("/api/box", boxesRouter);
app.use("/api/box", sensorsRouter);
app.use("/api/box", measurementsRouter);

app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "client", "index.html"));
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});

// Cleanup MQTT connection on server shutdown
process.on("SIGINT", () => {
  mqttClient.end(() => {
    console.log("MQTT connection closed");
    process.exit();
  });
});
