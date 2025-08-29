import express from "express";
import {
  openDb,
  initializeDatabase,
  initializeBoxDatabase,
  openBoxDb,
} from "./database.js";
import path from "path";

const app = express();
const port = 3000;

// Middleware to parse JSON bodies
app.use(express.json());

// Initialize database
await initializeDatabase();

// GET all boxes
app.get("/api/box", async (req, res) => {
  try {
    const db = await openDb();
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
    const db = await openDb();
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
    const mainDb = await openDb();
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
    const db = await openDb();
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
    const db = await openDb();
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

// GET measurements from a specific box
app.get("/api/box/:id/measurements", async (req, res) => {
  try {
    // First, verify the box exists in the main database
    const mainDb = await openDb();
    const box = await mainDb.get(
      "SELECT * FROM boxes WHERE id = ?",
      req.params.id,
    );

    if (!box) {
      return res.status(404).json({ error: "Box not found" });
    }

    // Query parameters for filtering
    const limit = parseInt(req.query.limit) || 100; // Default to 100 records
    const offset = parseInt(req.query.offset) || 0;
    const startDate = req.query.start_date; // Format: YYYY-MM-DD
    const endDate = req.query.end_date; // Format: YYYY-MM-DD

    // Open the box's specific database
    const boxDb = await openBoxDb(req.params.id);

    let query = "SELECT * FROM measurements";
    let queryParams = [];

    // Add date range filters if provided
    if (startDate || endDate) {
      const conditions = [];
      if (startDate) {
        conditions.push("timestamp >= ?");
        queryParams.push(startDate);
      }
      if (endDate) {
        conditions.push("timestamp < ?");
        queryParams.push(endDate + " 23:59:59"); // Include the entire end date
      }
      if (conditions.length > 0) {
        query += " WHERE " + conditions.join(" AND ");
      }
    }

    // Add ordering and pagination
    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?";
    queryParams.push(limit, offset);

    const measurements = await boxDb.all(query, queryParams);

    // Get total count for pagination
    const countResult = await boxDb.get(
      "SELECT COUNT(*) as total FROM measurements",
    );

    res.json({
      box_id: req.params.id,
      total_measurements: countResult.total,
      limit,
      offset,
      measurements,
    });
  } catch (error) {
    console.error("Error fetching measurements:", error);
    res.status(500).json({ error: "Failed to fetch measurements" });
  }
});

// Add a measurement to a box
app.post("/api/box/:id/measurements", async (req, res) => {
  try {
    // First, verify the box exists in the main database
    const mainDb = await openDb();
    const box = await mainDb.get(
      "SELECT * FROM boxes WHERE id = ?",
      req.params.id,
    );

    if (!box) {
      return res.status(404).json({ error: "Box not found" });
    }

    const { temperature, humidity, notes } = req.body;

    // Validate required fields
    if (temperature === undefined) {
      return res.status(400).json({ error: "Temperature is required" });
    }

    // Open the box's specific database
    const boxDb = await openBoxDb(req.params.id);

    // Insert the measurement
    const result = await boxDb.run(
      "INSERT INTO measurements (temperature, humidity, notes) VALUES (?, ?, ?)",
      [temperature, humidity || null, notes || null],
    );

    // Get the inserted measurement
    const measurement = await boxDb.get(
      "SELECT * FROM measurements WHERE id = ?",
      result.lastID,
    );

    res.status(201).json(measurement);
  } catch (error) {
    console.error("Error adding measurement:", error);
    res.status(500).json({ error: "Failed to add measurement" });
  }
});
