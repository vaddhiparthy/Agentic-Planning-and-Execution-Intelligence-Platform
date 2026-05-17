FROM python:3.12-slim

# Avoid tzdata interactive prompt and set default TZ
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Detroit

WORKDIR /app
COPY requirements.txt ./

# Install tzdata (for robust timezone support) then Python deps
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# App
COPY app.py ./app.py
COPY config.yaml ./config.yaml
COPY templates ./templates

EXPOSE 7000
CMD ["python", "app.py"]
