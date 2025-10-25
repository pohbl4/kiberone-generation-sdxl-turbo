FROM pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY app/inference/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app/inference/worker.py ./worker.py
COPY app/inference/logging_config.py ./logging_config.py
COPY app/inference/scripts ./scripts
COPY app/common ./app/common
COPY app/__init__.py ./app/__init__.py

EXPOSE 8080

CMD ["python", "-m", "worker"]
