#!/bin/bash

# Help text
show_help() {
    echo "Usage: $0 -b BOX_ID -s SENSOR_ID [-t TEMPERATURE] [-h HUMIDITY]"
    echo
    echo "Options:"
    echo "  -b BOX_ID      Box ID (required)"
    echo "  -s SENSOR_ID   Sensor ID (required)"
    echo "  -t TEMP        Temperature in Fahrenheit (optional, random if not provided)"
    echo "  -h HUMIDITY    Humidity percentage (optional, random if not provided)"
    echo
    echo "Example:"
    echo "  $0 -b 1234567890 -s 9876543210 -t 72.5 -h 45.2"
    echo "  $0 -b 1234567890 -s 9876543210  # Uses random values"
}

# Parse command line arguments
while getopts "b:s:t:h:" opt; do
    case $opt in
        b) BOX_ID="$OPTARG";;
        s) SENSOR_ID="$OPTARG";;
        t) TEMPERATURE="$OPTARG";;
        h) HUMIDITY="$OPTARG";;
        ?) show_help; exit 1;;
    esac
done

# Check required parameters
if [ -z "$BOX_ID" ] || [ -z "$SENSOR_ID" ]; then
    echo "Error: Box ID and Sensor ID are required"
    show_help
    exit 1
fi

# Generate random values if not provided
if [ -z "$TEMPERATURE" ]; then
    TEMPERATURE=$(echo "scale=1; 70 + ($RANDOM % 100) / 10" | bc)
fi
if [ -z "$HUMIDITY" ]; then
    HUMIDITY=$(echo "scale=1; 40 + ($RANDOM % 200) / 10" | bc)
fi

echo "Adding measurement for box ${BOX_ID} and sensor ${SENSOR_ID}: ${TEMPERATURE}°F, ${HUMIDITY}%"

# Add the measurement
curl -X POST "http://localhost:3000/api/box/${BOX_ID}/measurements" \
    -H "Content-Type: application/json" \
    -d "{
        \"sensor_id\": \"${SENSOR_ID}\",
        \"timestamp\": \"$(date +%s)\",
        \"temperature\": ${TEMPERATURE},
        \"humidity\": ${HUMIDITY}
    }"

echo # Add newline after curl output
