# Replace YOUR_BOX_ID with the actual box ID
BOX_ID="1756443629592"

# Add measurements for different times
for i in {1..24}; do
  # Calculate timestamp for each hour in the last 24 hours
  TIMESTAMP=$(date -u -v-${i}H +"%Y-%m-%dT%H:%M:%SZ")
  TEMP=$(echo "70 + ($RANDOM % 10)" | bc)
  HUMIDITY=$(echo "40 + ($RANDOM % 20)" | bc)

  curl -X POST http://localhost:3000/api/box/$BOX_ID/measurements \
    -H "Content-Type: application/json" \
    -d "{
      \"temperature\": $TEMP,
      \"humidity\": $HUMIDITY,
      \"timestamp\": \"$TIMESTAMP\"
    }"

  echo "Added measurement for $TIMESTAMP"
  sleep 1
done
