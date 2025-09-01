import sqlite3 from "sqlite3";
import { open } from "sqlite";
import path from "path";
import fs from "fs";

// Create a databases directory if it doesn't exist
const DB_DIR = "./databases";
if (!fs.existsSync(DB_DIR)) {
  fs.mkdirSync(DB_DIR);
}

// We'll export this to be used in our server
export async function openDb() {
  return open({
    filename: path.join(DB_DIR, "common.sqlite"),
    driver: sqlite3.Database,
  });
}

// Initialize the database and create the boxes table
export async function initializeDatabase() {
  try {
    const db = await openDb();

    await db.exec(`
            CREATE TABLE IF NOT EXISTS boxes (
                id TEXT PRIMARY KEY,
                database_path TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                data TEXT
            )
        `);

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

// Helper function to open a box's specific database
export async function openBoxDb(boxId) {
  return open({
    filename: path.join(DB_DIR, `${boxId}.sqlite`),
    driver: sqlite3.Database,
  });
}

// Initialize a new box database with sensor support
export async function initializeBoxDatabase(boxId) {
  const db = await openBoxDb(boxId);

  await db.exec(`
        CREATE TABLE IF NOT EXISTS sensors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    `);

  await db.exec(`
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            temperature REAL,
            humidity REAL,
            notes TEXT,
            FOREIGN KEY (sensor_id) REFERENCES sensors(id)
        )
    `);

  return db;
}
