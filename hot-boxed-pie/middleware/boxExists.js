import { openCommonDb } from "../database.js";

// Middleware to check if a box exists
export async function boxExists(req, res, next) {
  try {
    const mainDb = await openCommonDb();
    const box = await mainDb.get(
      "SELECT * FROM boxes WHERE id = ?",
      req.params.boxId,
    );

    if (!box) {
      return res.status(404).json({ error: "Box not found" });
    }

    req.box = box; // Attach box to request for later use
    next();
  } catch (error) {
    console.error("Error checking box:", error);
    res.status(500).json({ error: "Internal server error" });
  }
}
