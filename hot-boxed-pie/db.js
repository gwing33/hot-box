import sqlite3 from "sqlite3";
import { open } from "sqlite";
import path from "path";
import fs from "fs";

// Create a databases directory if it doesn't exist
const DB_DIR = "./databases";
if (!fs.existsSync(DB_DIR)) {
  fs.mkdirSync(DB_DIR);
}

async function _openDb(name) {
  return open({
    filename: path.join(DB_DIR, `${name}.sqlite`),
    driver: sqlite3.Database,
  });
}
export async function openCommonDb() {
  return _openDb("common");
}
export async function openBoxDb(boxId) {
  return _openDb(boxId);
}

// Initialize the database and create the boxes table
export async function initializeDatabase() {
  try {
    const db = await openCommonDb();

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

// Initialize a new box database with sensor support
export async function initializeBoxDatabase(boxId) {
  const db = await openBoxDb(boxId);

  await db.exec(`
        CREATE TABLE IF NOT EXISTS sensors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            location TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    `);

  await db.exec(`
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            temperature REAL,
            humidity REAL,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sensor_id) REFERENCES sensors(id)
        )
    `);

  return db;
}
