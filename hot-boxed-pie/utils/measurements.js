import { openBoxDb } from "../db.js";

export async function getMeasurementById(boxId, id) {
  const boxDb = await openBoxDb(boxId);

  const measurement = await boxDb.get(
    "SELECT * FROM measurements WHERE id = ?",
    id,
  );
  if (!measurement) {
    throw new Error("Measurement not found");
  }

  return measurement;
}

export async function createMeasurement(boxId, data) {
  const { sensor_id, temperature, humidity, notes, timestamp } = data;
  const boxDb = await openBoxDb(boxId);

  // Verify sensor exists
  const sensor = await boxDb.get(
    "SELECT * FROM sensors WHERE id = ?",
    sensor_id,
  );
  if (!sensor) {
    throw new Error("Sensor not found");
  }

  const result = await boxDb.run(
    "INSERT INTO measurements (sensor_id, timestamp, temperature, humidity, notes) VALUES (?, ?, ?, ?, ?)",
    [sensor_id, timestamp, temperature, humidity || null, notes || null],
  );

  return result.lastID;
}
