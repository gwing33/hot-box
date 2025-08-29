import express from "express";
import { openDb, initDb } from "./database.js";

const app = express();
const port = 3000;

// Middleware to parse JSON bodies
app.use(express.json());

// Initialize database
await initDb();

// GET all boxes
app.get("/api/box", async (req, res) => {
  try {
    const db = await openDb();
    const boxes = await db.all("SELECT * FROM boxes");
    res.json(
      boxes.map((box) => ({
        id: box.id,
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
    const db = await openDb();
    const id = Date.now().toString();
    const data = JSON.stringify(req.body);

    await db.run("INSERT INTO boxes (id, data) VALUES (?, ?)", [id, data]);

    res.status(201).json({
      id,
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

    res.json({
      id: req.params.id,
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

    await db.run("DELETE FROM boxes WHERE id = ?", req.params.id);

    res.json({
      id: box.id,
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
