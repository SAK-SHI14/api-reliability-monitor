# 1. Build the React frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend .
RUN npm run build

# 2. Setup the unified python backend & pollers
FROM python:3.10-slim
WORKDIR /app

# Install OS dependencies
RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*

# Install python dependencies for both subprojects
COPY backend/requirements.txt backend/
COPY api_reliability_monitor/requirements.txt api_reliability_monitor/
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN pip install --no-cache-dir -r api_reliability_monitor/requirements.txt

# Copy all source files
COPY . .

# Extract built frontend assets from the node builder
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Define default port
EXPOSE 8000

# Setting Python Path so module imports work correctly
ENV PYTHONPATH="/app"

# Start backend using Uvicorn. This script has been instructed to automatically 
# spin up the background polling daemons via subprocess on lifespan startup!
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
