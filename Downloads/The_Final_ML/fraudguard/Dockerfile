FROM python:3.12-slim

# xgboost needs the OpenMP runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ ./scripts/
COPY samples/ ./samples/
WORKDIR /app/scripts

ENV MODELS_DIR=/app/models
EXPOSE 8000

# Default: start the prediction API. Override the command for training / CLI prediction.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
