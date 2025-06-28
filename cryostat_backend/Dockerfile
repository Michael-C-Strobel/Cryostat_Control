FROM python:3.9

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# install lsusb and lsof
RUN apt-get update && apt-get install -y usbutils

# Copy application code
COPY . .

# Run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# Run mock_backend app instead
# CMD ["uvicorn", "mock_backend:app", "--host", "0.0.0.0", "--port", "8000"]