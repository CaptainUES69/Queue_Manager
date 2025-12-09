FROM python:3.12-slim

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

ENV PYTHONPATH=/app