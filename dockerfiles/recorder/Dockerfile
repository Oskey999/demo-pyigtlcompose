FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-dejavu-core \
    chromium \
    chromium-driver \
    ca-certificates \
    openssl \
    libssl3 \
    libnss3 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    flask \
    docker \
    playwright \
    opencv-python \
    pillow \
    numpy \
    requests

# Install Playwright browsers and dependencies
RUN playwright install chromium

RUN mkdir -p /recordings && chmod 777 /recordings

COPY recorder.py /app/recorder.py
WORKDIR /app
EXPOSE 8080
CMD ["python", "recorder.py"]