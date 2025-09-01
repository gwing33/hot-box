import express from "express";
import { initializeDatabase } from "./database.js";
import { fileURLToPath } from "url";
import path from "path";
// Import routes
import boxesRouter from "./routes/boxes.js";
import sensorsRouter from "./routes/sensors.js";
import measurementsRouter from "./routes/measurements.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = 3000;

// Middleware
app.use(express.json());
app.use(express.static(path.join(__dirname, "client")));

await initializeDatabase();

app.use("/api/box", boxesRouter);
app.use("/api/box", sensorsRouter);
app.use("/api/box", measurementsRouter);

app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "client", "index.html"));
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
