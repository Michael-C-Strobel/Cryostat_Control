FROM python:3.9

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# install lsusb
RUN apt-get update && apt-get install -y usbutils

# Copy application code
COPY . .

# Error out if port 8000 is in use
RUN lsof -ti:8000 && (echo "Port 8000 is already in use" && exit 1) || echo "Port 8000 is free"

# Run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# Run mock_backend app instead
# CMD ["uvicorn", "mock_backend:app", "--host", "0.0.0.0", "--port", "8000"]