# Use lightweight Python image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for caching layers)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Expose the ports
EXPOSE 3000
EXPOSE 7171

# Run the server
CMD ["python", "server.py"]
