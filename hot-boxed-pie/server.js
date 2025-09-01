import express from "express";
import {
  initializeDatabase,
  initializeBoxDatabase,
  openBoxDb,
  openCommonDb,
} from "./database.js";
import { fileURLToPath } from "url";
import path from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = 3000;

// Middleware to parse JSON bodies
app.use(express.json());

// Serve static files from the client directory
app.use(express.static(path.join(__dirname, "client")));

// Serve index.html for the root route
app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "client", "index.html"));
});

// Initialize database
await initializeDatabase();

// GET all boxes
app.get("/api/box", async (req, res) => {
  try {
    const db = await openCommonDb();
    const boxes = await db.all("SELECT * FROM boxes");
    res.json(
      boxes.map((box) => ({
        id: box.id,
        database_path: box.database_path,
        ...JSON.parse(box.data),
      })),
    );
  } catch (error) {
    console.error("Error fetching boxes:", error);
    res.status(500).json({ error: "Failed to fetch boxes" });
  }
});

// GET a specific box by ID
app.get("/api/box/:id", async (req, res) => {
  try {
    const db = await openCommonDb();
    const box = await db.get("SELECT * FROM boxes WHERE id = ?", req.params.id);

    if (!box) {
      return res.status(404).json({ error: "Box not found" });
    }

    res.json({
      id: box.id,
      database_path: box.database_path,
      ...JSON.parse(box.data),
    });
  } catch (error) {
    console.error("Error fetching box:", error);
    res.status(500).json({ error: "Failed to fetch box" });
  }
});

// POST a new box
app.post("/api/box", async (req, res) => {
  try {
    const mainDb = await openCommonDb();
    const id = Date.now().toString();
    const database_path = path.join("databases", `${id}.sqlite`);
    const data = JSON.stringify(req.body);

    // Initialize the box's specific database
    await initializeBoxDatabase(id);

    // Store the box metadata in the main database
    await mainDb.run(
      "INSERT INTO boxes (id, database_path, data) VALUES (?, ?, ?)",
      [id, database_path, data],
    );

    res.status(201).json({
      id,
      database_path,
      ...req.body,
    });
  } catch (error) {
    console.error("Error creating box:", error);
    res.status(500).json({ error: "Failed to create box" });
  }
});

// PUT (update) a box
app.put("/api/box/:id", async (req, res) => {
  try {
    const db = await openCommonDb();
    const data = JSON.stringify(req.body);

    const result = await db.run("UPDATE boxes SET data = ? WHERE id = ?", [
      data,
      req.params.id,
    ]);

    if (result.changes === 0) {
      return res.status(404).json({ error: "Box not found" });
    }

    const box = await db.get(
      "SELECT database_path FROM boxes WHERE id = ?",
      req.params.id,
    );

    res.json({
      id: req.params.id,
      database_path: box.database_path,
      ...req.body,
    });
  } catch (error) {
    console.error("Error updating box:", error);
    res.status(500).json({ error: "Failed to update box" });
  }
});

// DELETE a box
app.delete("/api/box/:id", async (req, res) => {
  try {
    const db = await openCommonDb();
    const box = await db.get("SELECT * FROM boxes WHERE id = ?", req.params.id);

    if (!box) {
      return res.status(404).json({ error: "Box not found" });
    }

    // Delete the box's specific database file
    const fs = await import("fs/promises");
    await fs.unlink(box.database_path).catch(console.error);

    // Remove from main database
    await db.run("DELETE FROM boxes WHERE id = ?", req.params.id);

    res.json({
      id: box.id,
      database_path: box.database_path,
      ...JSON.parse(box.data),
    });
  } catch (error) {
    console.error("Error deleting box:", error);
    res.status(500).json({ error: "Failed to delete box" });
  }
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});

// ... (previous imports and setup remain the same)

// Get sensors for a box
app.get("/api/box/:id/sensors", async (req, res) => {
  try {
    const mainDb = await openCommonDb();
    const box = await mainDb.get(
      "SELECT * FROM boxes WHERE id = ?",
      req.params.id,
    );

    if (!box) {
      return res.status(404).json({ error: "Box not found" });
    }

    const boxDb = await openBoxDb(req.params.id);
    const sensors = await boxDb.all("SELECT * FROM sensors");

    res.json(sensors);
  } catch (error) {
    console.error("Error fetching sensors:", error);
    res.status(500).json({ error: "Failed to fetch sensors" });
  }
});

// Add a sensor to a box
app.post("/api/box/:id/sensors", async (req, res) => {
  try {
    const mainDb = await openCommonDb();
    const box = await mainDb.get(
      "SELECT * FROM boxes WHERE id = ?",
      req.params.id,
    );

    if (!box) {
      return res.status(404).json({ error: "Box not found" });
    }

    const { name, type, location } = req.body;
    if (!name) {
      return res.status(400).json({ error: "Sensor name is required" });
    }

    const boxDb = await openBoxDb(req.params.id);
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
app.put("/api/box/:boxId/sensors/:sensorId", async (req, res) => {
  try {
    const { boxId, sensorId } = req.params;
    const { name, type, location } = req.body;

    const mainDb = await openCommonDb();
    const box = await mainDb.get("SELECT * FROM boxes WHERE id = ?", boxId);

    if (!box) {
      return res.status(404).json({ error: "Box not found" });
    }

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

// Update measurements endpoint to handle sensors
app.get("/api/box/:id/measurements", async (req, res) => {
  try {
    const mainDb = await openCommonDb();
    const box = await mainDb.get(
      "SELECT * FROM boxes WHERE id = ?",
      req.params.id,
    );

    if (!box) {
      return res.status(404).json({ error: "Box not found" });
    }

    const limit = parseInt(req.query.limit) || 100;
    const offset = parseInt(req.query.offset) || 0;
    const startTime = req.query.start_time;
    const endTime = req.query.end_time;

    const boxDb = await openBoxDb(req.params.id);

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
      box_id: req.params.id,
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
app.post("/api/box/:id/measurements", async (req, res) => {
  try {
    const mainDb = await openCommonDb();
    const box = await mainDb.get(
      "SELECT * FROM boxes WHERE id = ?",
      req.params.id,
    );

    if (!box) {
      return res.status(404).json({ error: "Box not found" });
    }

    const { sensor_id, temperature, humidity, notes, timestamp } = req.body;

    if (!sensor_id || !timestamp || temperature === undefined) {
      return res
        .status(400)
        .json({ error: "sensor_id and temperature are required" });
    }

    const boxDb = await openBoxDb(req.params.id);

    // Verify sensor exists
    const sensor = await boxDb.get(
      "SELECT * FROM sensors WHERE id = ?",
      sensor_id,
    );
    if (!sensor) {
      return res.status(404).json({ error: "Sensor not found" });
    }

    const result = await boxDb.run(
      "INSERT INTO measurements (sensor_id, timestamp, temperature, humidity, notes) VALUES (?, ?, ?, ?, ?)",
      [sensor_id, timestamp, temperature, humidity || null, notes || null],
    );

    const measurement = await boxDb.get(
      "SELECT m.*, s.name as sensor_name FROM measurements m JOIN sensors s ON m.sensor_id = s.id WHERE m.id = ?",
      result.lastID,
    );

    res.status(201).json(measurement);
  } catch (error) {
    console.error("Error adding measurement:", error);
    res.status(500).json({ error: "Failed to add measurement" });
  }
});
