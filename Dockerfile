FROM python:3.11-slim

WORKDIR /app

# Install system deps for OpenCV headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir "ultralytics>=8.0.0" "numpy>=1.24.0" "pandas>=2.0.0" "opencv-python-headless>=4.8.0" "pytest>=7.4.0" "httpx>=0.25.0"

COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
