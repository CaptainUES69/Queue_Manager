FROM python:3.12.8-slim

RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    cmake \
    g++ \
    gcc \
    make \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs

ENV PYTHONPATH=/app

CMD ["uvicorn", "src.webserver:app", "--host", "0.0.0.0", "--port", "8000"]