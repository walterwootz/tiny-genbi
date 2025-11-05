# Multi-stage build for Tiny GenBI (MySQL)

# Stage 1: Build Frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app/webui

# Copy package files
COPY webui/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY webui/ ./

# Build frontend
RUN npm run build

# Stage 2: Build Backend
FROM python:3.9-slim AS backend

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY src/ ./src/

# Copy example scripts (optional)
COPY example*.py ./

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/webui/dist ./webui/dist

# Create data directories
RUN mkdir -p data/indexed_dumps data/vector_store

# Expose port
EXPOSE 5556

# Environment variables (can be overridden)
ENV API_HOST=0.0.0.0
ENV API_PORT=5556
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5556/health', timeout=5)"

# Run the application
CMD ["python", "src/main.py"]
