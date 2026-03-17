# 1. Build the React frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend .
RUN npm run build

# 2. Setup the unified python backend & pollers
FROM python:3.10-slim
WORKDIR /app

# Install OS dependencies required for compiling Python packages
RUN apt-get update && apt-get install -y sqlite3 gcc g++ python3-dev && rm -rf /var/lib/apt/lists/*

# Install exact production dependencies for fast builds
RUN pip install --no-cache-dir fastapi uvicorn requests pyyaml ExceptionGroup

# Copy all source files
COPY . .

# Extract built frontend assets from the node builder
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Define default port
EXPOSE 8000

# Setting Python Path so module imports work correctly
ENV PYTHONPATH="/app"

# Start backend using the unified python launcher.
# This launcher handles dynamic $PORT allocation for Railway/Render automatically.
CMD ["python", "-m", "backend.main"]
