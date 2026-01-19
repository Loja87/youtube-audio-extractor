FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Importante: usar shell para expandir $PORT
CMD ["sh", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
