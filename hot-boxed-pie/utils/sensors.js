import { openBoxDb } from "../db.js";

export async function getSensorById(boxId, id) {
  const boxDb = await openBoxDb(boxId);
  return await boxDb.get("SELECT * FROM sensors WHERE id = ?", id);
}

export async function createSensor(boxId, id, name, data) {
  const { type, location } = data;

  const boxDb = await openBoxDb(boxId);
  await boxDb.run(
    "INSERT INTO sensors (id, name, type, location) VALUES (?, ?, ?, ?)",
    [id, name, type || null, location || null],
  );

  return await getSensorById(boxId, id);
}
