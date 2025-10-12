import express from "express";
import { openBoxDb } from "../db.js";
import { boxExists } from "../middleware/boxExists.js";

const router = express.Router();

// Get sensors for a box
router.get("/:boxId/sensors", boxExists, async (req, res) => {
  try {
    const boxDb = await openBoxDb(req.params.boxId);
    const sensors = await boxDb.all("SELECT * FROM sensors");

    res.json(sensors);
  } catch (error) {
    console.error("Error fetching sensors:", error);
    res.status(500).json({ error: "Failed to fetch sensors" });
  }
});

// Add a sensor to a box
router.post("/:boxId/sensors", boxExists, async (req, res) => {
  try {
    const { name, type, location } = req.body;
    if (!name) {
      return res.status(400).json({ error: "Sensor name is required" });
    }

    const boxDb = await openBoxDb(req.params.boxId);
    const sensorId = Date.now().toString();

    await boxDb.run(
      "INSERT INTO sensors (id, name, type, location) VALUES (?, ?, ?, ?)",
      [sensorId, name, type || null, location || null],
    );

    const sensor = await boxDb.get(
      "SELECT * FROM sensors WHERE id = ?",
      sensorId,
    );
    res.status(201).json(sensor);
  } catch (error) {
    console.error("Error creating sensor:", error);
    res.status(500).json({ error: "Failed to create sensor" });
  }
});

// Update a sensor
router.put("/:boxId/sensors/:sensorId", boxExists, async (req, res) => {
  try {
    const { boxId, sensorId } = req.params;
    const { name, type, location } = req.body;

    const boxDb = await openBoxDb(boxId);
    const sensor = await boxDb.get(
      "SELECT * FROM sensors WHERE id = ?",
      sensorId,
    );

    if (!sensor) {
      return res.status(404).json({ error: "Sensor not found" });
    }

    await boxDb.run(
      "UPDATE sensors SET name = ?, type = ?, location = ? WHERE id = ?",
      [
        name || sensor.name,
        type !== undefined ? type : sensor.type,
        location !== undefined ? location : sensor.location,
        sensorId,
      ],
    );

    const updatedSensor = await boxDb.get(
      "SELECT * FROM sensors WHERE id = ?",
      sensorId,
    );
    res.json(updatedSensor);
  } catch (error) {
    console.error("Error updating sensor:", error);
    res.status(500).json({ error: "Failed to update sensor" });
  }
});

export default router;
