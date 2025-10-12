import { openCommonDb } from "../db.js";

export async function getBoxById(id) {
  const mainDb = await openCommonDb();
  const box = await mainDb.get("SELECT * FROM boxes WHERE id = ?", id);
  return box;
}
