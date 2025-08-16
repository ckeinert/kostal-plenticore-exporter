# Basisimage
FROM python:3.12-slim

# Arbeitsverzeichnis
WORKDIR /app

# Abhängigkeiten kopieren
COPY requirements.txt .

# Abhängigkeiten installieren
RUN pip install --no-cache-dir -r requirements.txt

# Quellcode kopieren
COPY exporter.py .

# Port freigeben
EXPOSE 8000

# Container-Start
CMD ["python", "plenticore_exporter.py"]
