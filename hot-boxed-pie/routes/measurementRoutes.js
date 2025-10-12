import express from "express";
import { openBoxDb } from "../db.js";
import { boxExists } from "../middleware/boxExists.js";
import {
  getMeasurementById,
  createMeasurement,
} from "../utils/measurements.js";

const router = express.Router();

router.get("/:boxId/measurements", boxExists, async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 100;
    const offset = parseInt(req.query.offset) || 0;
    const startTime = req.query.start_time;
    const endTime = req.query.end_time;

    const boxDb = await openBoxDb(req.params.boxId);

    let query = `
            SELECT m.*, s.name as sensor_name
            FROM measurements m
            JOIN sensors s ON m.sensor_id = s.id
        `;

    let queryParams = [];

    if (startTime || endTime) {
      const conditions = [];
      if (startTime) {
        conditions.push("m.timestamp >= ?");
        queryParams.push(startTime);
      }
      if (endTime) {
        conditions.push("m.timestamp <= ?");
        queryParams.push(endTime);
      }
      if (conditions.length > 0) {
        query += " WHERE " + conditions.join(" AND ");
      }
    }

    query += " ORDER BY m.timestamp DESC LIMIT ? OFFSET ?";
    queryParams.push(limit, offset);

    const measurements = await boxDb.all(query, queryParams);

    // Get total count
    const countResult = await boxDb.get(
      "SELECT COUNT(*) as total FROM measurements",
    );

    // Get all sensors for this box
    const sensors = await boxDb.all("SELECT * FROM sensors");

    res.json({
      box_id: req.params.boxId,
      total_measurements: countResult.total,
      limit,
      offset,
      sensors,
      measurements,
    });
  } catch (error) {
    console.error("Error fetching measurements:", error);
    res.status(500).json({ error: "Failed to fetch measurements" });
  }
});

// Update POST measurements endpoint to require sensor_id
router.post("/:boxId/measurements", boxExists, async (req, res) => {
  try {
    const { sensor_id, temperature, humidity, notes, timestamp } = req.body;

    if (!sensor_id || !timestamp || temperature === undefined) {
      return res
        .status(400)
        .json({ error: "sensor_id, timestamp and temperature are required" });
    }

    const measurementId = await createMeasurement(req.params.boxId, {
      sensor_id,
      temperature,
      humidity,
      notes,
      timestamp,
    });
    const measurement = await getMeasurementById(
      req.params.boxId,
      measurementId,
    );
    return res.status(201).json(measurement);
  } catch (error) {
    if (error.message === "Sensor not found") {
      return res.status(404).json({ error: error.message });
    }
    console.error("Error adding measurement:", error);
    res.status(500).json({ error: "Failed to add measurement" });
  }
});

export default router;
