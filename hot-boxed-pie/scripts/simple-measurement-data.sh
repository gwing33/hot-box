# Replace YOUR_BOX_ID with the actual box ID
BOX_ID="1756443629592"

# Add several measurements
curl -X POST http://localhost:3000/api/box/$BOX_ID/measurements \
  -H "Content-Type: application/json" \
  -d '{"temperature": 72.5, "humidity": 45.2}'

curl -X POST http://localhost:3000/api/box/$BOX_ID/measurements \
  -H "Content-Type: application/json" \
  -d '{"temperature": 73.1, "humidity": 44.8}'

curl -X POST http://localhost:3000/api/box/$BOX_ID/measurements \
  -H "Content-Type: application/json" \
  -d '{"temperature": 73.8, "humidity": 44.5}'

curl -X POST http://localhost:3000/api/box/$BOX_ID/measurements \
  -H "Content-Type: application/json" \
  -d '{"temperature": 74.2, "humidity": 44.1}'

curl -X POST http://localhost:3000/api/box/$BOX_ID/measurements \
  -H "Content-Type: application/json" \
  -d '{"temperature": 74.5, "humidity": 43.8}'
