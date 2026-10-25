FROM python:3.12-slim AS base
WORKDIR /app
# Show print() output in "docker logs" immediately instead of buffering it
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
COPY extra/ extra/

# docker build --target test .   runs the test suite during the build
FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests/ tests/
RUN python -m pytest -q

FROM base AS runtime
# credentials/ is expected as a read-only volume (see docker-compose.yml)
CMD ["python", "alert.py"]
