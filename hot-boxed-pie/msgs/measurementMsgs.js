import { createMeasurement } from "../utils/measurements.js";

export async function handleMeasurementMsg(boxId, type, payload) {
  if (type != "measurement") {
    return;
  }

  // You can add code here to save the measurement to your database
  console.log("Received measurement payload:", payload);
  const measurementId = await createMeasurement(boxId, payload);
  console.log(`Measurement saved with ID: ${measurementId}`);
}
