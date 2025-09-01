#!/bin/bash

# Production deployment script for hot-boxed-pie

# Check if PM2 is installed globally
if ! command -v pm2 &> /dev/null; then
    echo "Installing PM2 globally..."
    npm install -g pm2
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Install dependencies
echo "Installing dependencies..."
npm install --production

# Check if the application is already running
if pm2 list | grep -q "hot-boxed-pie"; then
    echo "Stopping existing instance..."
    npm run prod:stop
fi

# Start the application
echo "Starting application in production mode..."
npm run prod

# Save PM2 process list
echo "Saving PM2 process list..."
pm2 save

# Display status
echo "Application status:"
pm2 list

# Display logs location
echo "Logs are available in:"
echo "- Error logs: logs/error.log"
echo "- Output logs: logs/out.log"
echo "- Combined logs: logs/combined.log"
echo
echo "To view logs in real-time, run: npm run prod:logs"
