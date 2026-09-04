FROM python:3.11-slim

# Install curl for healthchecks
RUN apt update && apt install -y curl

# Set work directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

# Expose port
EXPOSE 5000

# Run backend
CMD ["python", "app.py"]
