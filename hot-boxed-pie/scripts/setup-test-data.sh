#!/bin/bash

VERSION=$(jq --version)
echo "jq version: $VERSION"

if [ -z "$VERSION" ] || [ "$VERSION" = "null" ]; then
  echo "This script requires jq. Please install it first."
  echo "On macOS: brew install jq"
  echo "On Ubuntu/Debian: sudo apt-get install jq"
  exit 1
fi

# Configuration
API_URL="http://localhost:3000"

echo "Creating new box..."
# Create a box and capture its ID
BOX_RESPONSE=$(curl -s -X POST "${API_URL}/api/box" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Jackie'\''s Big Box",
        "location": "South Wall"
    }')

BOX_ID=$(echo $BOX_RESPONSE | jq -r '.id')

if [ -z "$BOX_ID" ] || [ "$BOX_ID" = "null" ]; then
    echo "Failed to create box!"
    exit 1
fi

echo "Created box with ID: $BOX_ID"

# Create sensors
echo "Creating sensors..."

# Create top sensor
TOP_SENSOR_RESPONSE=$(curl -s -X POST "${API_URL}/api/box/${BOX_ID}/sensors" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Top Sensor"
    }')

TOP_SENSOR_ID=$(echo $TOP_SENSOR_RESPONSE | jq -r '.id')

# Create bottom sensor
BOTTOM_SENSOR_RESPONSE=$(curl -s -X POST "${API_URL}/api/box/${BOX_ID}/sensors" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Bottom Sensor"
    }')

BOTTOM_SENSOR_ID=$(echo $BOTTOM_SENSOR_RESPONSE | jq -r '.id')

echo "Created sensors:"
echo "Top Sensor ID: $TOP_SENSOR_ID"
echo "Bottom Sensor ID: $BOTTOM_SENSOR_ID"

# Generate test data for the last 24 hours
echo "Generating test data for the last 24 hours..."

# Function to generate random number in range
random_range() {
    local MIN=$1
    local MAX=$2
    echo "scale=1; $MIN + ($RANDOM % (($MAX - $MIN) * 10)) / 10" | bc
}

# Loop through the last 24 hours
for hour in $(seq 24 -1 0); do
    # Calculate timestamp
    TIMESTAMP=$(date -u -v-${hour}H +"%Y-%m-%dT%H:%M:%SZ")

    # Generate random temperatures and humidity
    TOP_TEMP=$(random_range 72 77)    # Top sensor slightly warmer
    TOP_HUMIDITY=$(random_range 45 55)
    BOTTOM_TEMP=$(random_range 70 75)  # Bottom sensor slightly cooler
    BOTTOM_HUMIDITY=$(random_range 40 50)

    # Add measurement for top sensor
    curl -s -X POST "${API_URL}/api/box/${BOX_ID}/measurements" \
        -H "Content-Type: application/json" \
        -d "{
            \"sensor_id\": \"${TOP_SENSOR_ID}\",
            \"temperature\": ${TOP_TEMP},
            \"humidity\": ${TOP_HUMIDITY}
        }" > /dev/null

    # Add measurement for bottom sensor
    curl -s -X POST "${API_URL}/api/box/${BOX_ID}/measurements" \
        -H "Content-Type: application/json" \
        -d "{
            \"sensor_id\": \"${BOTTOM_SENSOR_ID}\",
            \"temperature\": ${BOTTOM_TEMP},
            \"humidity\": ${BOTTOM_HUMIDITY}
        }" > /dev/null

    echo "Added measurements for hour -${hour}"
done

echo "Setup complete!"
echo "Box ID: $BOX_ID"
echo "Top Sensor ID: $TOP_SENSOR_ID"
echo "Bottom Sensor ID: $BOTTOM_SENSOR_ID"
echo "Visit http://localhost:3000 to see the dashboard"
