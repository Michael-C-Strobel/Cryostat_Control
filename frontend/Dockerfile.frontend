FROM python:3.9

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Streamlit app
COPY . .

# Error out if port 8050 is in use
RUN lsof -ti:8050 && (echo "Port 8050 is already in use" && exit 1) || echo "Port 8050 is free"

# Run Streamlit
CMD ["python", "app.py"]