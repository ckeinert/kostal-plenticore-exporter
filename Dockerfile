# base image - use slim with Python 3.12 for compatibility
FROM python:3.12-slim

# set workdir
WORKDIR /app

# copy requirements first (better layer caching)
COPY requirements.txt .

# install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# copy code
COPY plenticore_exporter.py .
COPY session_cache.py .
COPY gauges.py .

# create entrypoint script for graceful shutdown
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# set port
EXPOSE 8080

# healthcheck - verify metrics endpoint is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# run exporter with entrypoint script (handles signals properly)
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "plenticore_exporter.py"]
