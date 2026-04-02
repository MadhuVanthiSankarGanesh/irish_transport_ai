FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-agent.txt ./
RUN pip install --upgrade pip && pip install -r requirements-agent.txt

COPY dashboard ./dashboard
COPY src ./src
RUN mkdir -p /app/data/features /app/data/clean /app/data/cache /app/data/GTFS_All_extracted
COPY data/features/event_demand.csv ./data/features/event_demand.csv
COPY data/clean/stops.csv ./data/clean/stops.csv
COPY data/cache ./data/cache
COPY data/GTFS_All_extracted ./data/GTFS_All_extracted
COPY config.yaml ./

EXPOSE 8501 8765

CMD ["streamlit", "run", "dashboard/chat.py", "--server.port=8501", "--server.address=0.0.0.0"]
