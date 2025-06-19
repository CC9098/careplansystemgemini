# Use an official Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for building frontend
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Copy package.json and install Node.js dependencies
COPY package.json ./
RUN npm install

# Copy frontend source code and build
COPY src ./src
COPY public ./public
RUN npm run build

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python application files
COPY app.py .
COPY models.py .
COPY api ./api

# Expose the port
EXPOSE 8080

# Command to run the application
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT app:app"] 