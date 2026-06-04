# Use Node.js LTS (Hydrogen)
FROM node:18-slim

# Create app directory
WORKDIR /app

# Install app dependencies
# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy app source
COPY . .

# Create necessary directories
RUN mkdir -p logs databases

# Expose port
EXPOSE 8080

# Start the server
CMD [ "node", "server.js" ]
