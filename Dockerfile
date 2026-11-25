FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENGINE=auto

RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng \
        libgomp1 libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-full.txt .
RUN pip install --no-cache-dir -r requirements-full.txt
COPY . .

EXPOSE 8080
HEALTHCHECK --interval=45s --timeout=10s --start-period=40s \
  CMD curl -fsS "http://localhost:${PORT:-8080}/health" || exit 1

CMD uvicorn app:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1 --timeout-keep-alive 75
