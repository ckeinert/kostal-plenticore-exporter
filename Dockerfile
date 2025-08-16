# base image
FROM python:3.12-slim

# set workdir
WORKDIR /app

# copy requirements
COPY requirements.txt .

# install dependecies
RUN pip install --no-cache-dir -r requirements.txt

# copy code
COPY plenticore_exporter.py .
COPY session_cache.py .

# set port
EXPOSE 8080

# run exporter
CMD ["python", "plenticore_exporter.py"]
