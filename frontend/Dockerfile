FROM node:20-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files from frontend directory
COPY frontend/package*.json ./

# Install dependencies
RUN npm install

# Copy frontend application code
COPY frontend/ .

# Expose port (will be set by environment variable)
EXPOSE ${VITE_PORT:-5173}

# Run the development server
CMD ["npm", "run", "dev"]
