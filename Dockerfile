FROM python:3.11-slim

LABEL maintainer="mohamedtarek77"
LABEL description="InsightDrop CLI – sales analytics pipeline"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pipeline.py      .
COPY insightdrop.py   .

RUN mkdir -p /app/data

VOLUME ["/app/data"]

ENTRYPOINT ["python", "insightdrop.py"]
CMD ["--help"]