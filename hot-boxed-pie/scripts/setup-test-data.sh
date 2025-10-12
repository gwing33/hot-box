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
        "name": "Test Box 01",
        "description": "This payload can have any information you want"
    }')

BOX_ID=$(echo $BOX_RESPONSE | jq -r '.id')

if [ -z "$BOX_ID" ] || [ "$BOX_ID" = "null" ]; then
    echo "Failed to create box!"
    exit 1
fi

echo "Created box with ID: $BOX_ID"

# Create sensors
echo "Creating sensors..."

# Create a sensor
A_SENSOR_RESPONSE=$(curl -s -X POST "${API_URL}/api/box/${BOX_ID}/sensors" \
    -H "Content-Type: application/json" \
    -d '{
        "id": "TEMP_01",
        "name": "A Sensor",
        "type": "DHT22",
        "location": "South Wall"
    }')

A_SENSOR_ID=$(echo $A_SENSOR_RESPONSE | jq -r '.id')

# Create b sensor
B_SENSOR_RESPONSE=$(curl -s -X POST "${API_URL}/api/box/${BOX_ID}/sensors" \
    -H "Content-Type: application/json" \
    -d '{
        "id": "TEMP_02",
        "name": "B Sensor",
        "type": "DHT22",
        "location": "South Wall"
    }')

B_SENSOR_ID=$(echo $B_SENSOR_RESPONSE | jq -r '.id')

echo "Created sensors:"
echo "A Sensor ID: $A_SENSOR_ID"
echo "B Sensor ID: $B_SENSOR_ID"

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
    A_TEMP=$(random_range 72 77)    # Top sensor slightly warmer
    A_HUMIDITY=$(random_range 45 55)
    B_TEMP=$(random_range 70 75)  # Bottom sensor slightly cooler
    B_HUMIDITY=$(random_range 40 50)

    # Add measurement for top sensor
    curl -s -X POST "${API_URL}/api/box/${BOX_ID}/measurements" \
        -H "Content-Type: application/json" \
        -d "{
            \"sensor_id\": \"${A_SENSOR_ID}\",
            \"timestamp\": \"${TIMESTAMP}\",
            \"temperature\": ${A_TEMP},
            \"humidity\": ${A_HUMIDITY}
        }" > /dev/null

    # Add measurement for bottom sensor
    curl -s -X POST "${API_URL}/api/box/${BOX_ID}/measurements" \
        -H "Content-Type: application/json" \
        -d "{
            \"sensor_id\": \"${B_SENSOR_ID}\",
            \"timestamp\": \"${TIMESTAMP}\",
            \"temperature\": ${B_TEMP},
            \"humidity\": ${B_HUMIDITY}
        }" > /dev/null

    echo "Added measurements for hour -${hour}"
done

echo "Setup complete!"
echo "Box ID: $BOX_ID"
echo "Top Sensor ID: $A_SENSOR_ID"
echo "Bottom Sensor ID: $B_SENSOR_ID"
echo "Visit http://localhost:3000 to see the dashboard"
