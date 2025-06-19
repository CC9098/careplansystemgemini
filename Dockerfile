# ---- Stage 1: Build the React Frontend ----
# Use an official Node.js image as the builder environment
# Use a specific version for consistency
FROM node:18-alpine AS builder

# Set the working directory
WORKDIR /app/frontend

# Copy package.json and package-lock.json (or yarn.lock)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the frontend source code
COPY . .

# Build the React application
# This will create a 'build' folder with static files
RUN npm run build

# ---- Stage 2: Setup the Python Backend ----
# Use an official Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Set environment variables to prevent Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application code (including the frontend build from the previous stage)
# This is the magic part of multi-stage builds
COPY --from=builder /app/frontend/build ./build
COPY . .

# Expose the port Gunicorn will run on
EXPOSE 8080

# Command to run the application using Gunicorn
# Use the PORT environment variable provided by Railway
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT app:app"] 