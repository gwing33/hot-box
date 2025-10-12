import express from "express";
import { openCommonDb, initializeBoxDatabase } from "../db.js";
import { boxExists } from "../middleware/boxExists.js";
import path from "path";

const router = express.Router();

// GET all boxes
router.get("/", async (req, res) => {
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
router.get("/:boxId", boxExists, async (req, res) => {
  try {
    const box = req.box;

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
router.post("/", async (req, res) => {
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
router.put("/:boxId", boxExists, async (req, res) => {
  try {
    const db = await openCommonDb();
    const data = JSON.stringify(req.body);

    const result = await db.run("UPDATE boxes SET data = ? WHERE id = ?", [
      data,
      req.params.boxId,
    ]);

    if (result.changes === 0) {
      return res.status(404).json({ error: "Box not found" });
    }

    const box = await db.get(
      "SELECT database_path FROM boxes WHERE id = ?",
      req.params.boxId,
    );

    res.json({
      id: req.params.boxId,
      database_path: box.database_path,
      ...req.body,
    });
  } catch (error) {
    console.error("Error updating box:", error);
    res.status(500).json({ error: "Failed to update box" });
  }
});

// DELETE a box
router.delete("/api/box/:boxId", boxExists, async (req, res) => {
  try {
    const box = req.box;
    // Delete the box's specific database file
    const fs = await import("fs/promises");
    await fs.unlink(box.database_path).catch(console.error);

    // Remove from main database
    await db.run("DELETE FROM boxes WHERE id = ?", req.params.boxId);

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

export default router;
