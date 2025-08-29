import sqlite3 from "sqlite3";
import { open } from "sqlite";

// We'll export this to be used in our server
export async function openDb() {
  return open({
    filename: "./database.sqlite",
    driver: sqlite3.Database,
  });
}

// Initialize the database and create the boxes table
export async function initDb() {
  try {
    const db = await openDb();

    await db.exec(`
            CREATE TABLE IF NOT EXISTS boxes (
                id TEXT PRIMARY KEY,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                data TEXT
            )
        `);

    // Create a trigger to update the updated_at timestamp
    await db.exec(`
            CREATE TRIGGER IF NOT EXISTS update_boxes_timestamp
            AFTER UPDATE ON boxes
            BEGIN
                UPDATE boxes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
        `);
  } catch (error) {
    console.error("Database initialization error:", error);
    throw error;
  }
}
