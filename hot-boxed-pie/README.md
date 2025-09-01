# Hot Boxed Pie
This is the server for the Hot Box tempature harness.

Potential Tasks
- Custom date range
- Export data as CSV
- Add `sensor_id` to measurements table
- Basic Authentication, not by user but by hard coded key
- Temp unit conversion


## API Endpoints
All endpoints are RESTful and use JSON for data exchange.

### Boxes Endpoint
A Box is a test or defined region for the temperature sensor.
```
/api/box/:id
```

### Box Sensors Endpoint
Temperature and/or humidity sensors that are attached to a specific Box.
```
/api/box/:id/sensors/:sensor_id
```

### Box Sensor Measurements Endpoint
Temperature and/or humidity measurements taken from a specific sensor.
```
/api/box/:id/sensor/:sensor_id/measurements
```

## Test Commands
```shell
# Setup New Box, Sensors and backfill with 1 day of measurements
scripts/setup-test-data.sh

# Add Measurement: temp and humidity are optional
scripts/add-measurement.sh -b YOUR_BOX_ID -s YOUR_SENSOR_ID -t 72.5 -h 45.2
```

Below are various commands:

```shell
# Where 1756443629592 is the box ID

# Get all boxes
curl http://localhost:3000/api/box

# Create a new box
curl -X POST http://localhost:3000/api/box \
  -H "Content-Type: application/json" \
  -d '{"name": "Jackie'\''s Box", "contents": "Items"}'

# Get a specific box
curl http://localhost:3000/api/box/1756443629592

# Update a box
curl -X PUT http://localhost:3000/api/box/1756443629592 \
  -H "Content-Type: application/json" \
  -d '{"name": "Jackie'\''s Big Box"}'

# Delete a box
curl -X DELETE http://localhost:3000/api/box/1756443629592
```

### Box Measurements Endpoint
A Box Measurement is a record of the temperature reading taken from a specific Box.

```shell
# Get all measurements (latest 100)
curl http://localhost:3000/api/box/1756443629592/measurements

# Get measurements with pagination
curl http://localhost:3000/api/box/1756443629592/measurements?limit=10&offset=20

# Get measurements for a date range
curl http://localhost:3000/api/box/1756443629592/measurements?start_date=2024-01-01&end_date=2024-01-15

curl -X POST http://localhost:3000/api/box/1756443629592/measurements \
  -H "Content-Type: application/json" \
  -d '{
    "temperature": 72.5,
    "humidity": 45.2,
    "notes": "Regular afternoon reading"
  }'
```
