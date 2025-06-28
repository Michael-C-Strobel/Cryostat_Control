FROM python:3.9-slim

WORKDIR /app

# Install system dependencies if needed (e.g., build tools)
RUN apt-get update && apt-get install -y build-essential

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . ./frontend

EXPOSE 8050

CMD ["python", "frontend/app.py"]
