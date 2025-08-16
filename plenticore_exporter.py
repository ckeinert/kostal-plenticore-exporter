import asyncio
import re
import signal
import sys
import os
from aiohttp import ClientSession, ClientTimeout
from pykoplenti import ApiClient
from typing import Optional, Any, Callable
from session_cache import SessionCache
from collections import defaultdict
from prometheus_client import start_http_server, Gauge

gauges = {}

# Umgebungsvariablen prüfen
host = os.getenv("PLENTICORE_HOST")
key = os.getenv("PLENTICORE_PASSWORD")

if not host or not key:
    print("ERROR: PLENTICORE_HOST und PLENTICORE_PASSWORD müssen gesetzt sein!")
    sys.exit(1)


def graceful_exit(signum, frame):
    print("Stopping gracefully...")
    # hier Cleanup einfügen, z.B. offene Dateien schließen
    sys.exit(0)

# Signal-Handler registrieren
signal.signal(signal.SIGTERM, graceful_exit)
signal.signal(signal.SIGINT, graceful_exit)  # optional für CTRL+C


async def command_main(
    host: str,
    port: int,
    key: Optional[str],
    service_code: Optional[str],
    fn: Callable[[ApiClient], Any],
):
    async with ClientSession(timeout=ClientTimeout(total=10)) as session:
        # ApiClient initialisieren
        client = ApiClient(session, host=host, port=port)

        # SessionCache laden (user = master oder user)
        session_cache = SessionCache(host, "user" if service_code is None else "master")

        # Versuche bestehende Session zu nutzen
        client.session_id = session_cache.read_session_id()

        me = await client.get_me()
        if not me.is_authenticated:
            if key is None:
                raise ValueError("Could not reuse session and no login key is given.")

            # Neue Session anlegen
            await client.login(key=key, service_code=service_code)

            if client.session_id is not None:
                session_cache.write_session_id(client.session_id)

        return await fn(client)


async def fetch_all_values(host, port, key, service_code):
    """Ermittelt alle Keys und fragt dann deren Werte ab."""

    async def fn(client: ApiClient):
        # Schritt 1: Alle Keys holen
        all_data = await client.get_process_data()

        # Keys in ein Query-Dict überführen
        query = defaultdict(list)
        for module_id, values in all_data.items():
            for v in values:
                query[module_id].append(v)

        # Schritt 2: Werte aller Keys holen
        values = await client.get_process_data_values(query)

    # Gib die Werte zurück
        result = {}
        for module_id, vdict in values.items():
            for entry in vdict.values():
                result[f"{module_id}/{entry.id}"] = entry.value
        return result

    # command_main ist async, also await nutzen
    return await command_main(host, port, key, service_code, fn)


def sanitize_label(value: str) -> str:
    """Sanitize a string to be a valid Prometheus label value"""
    return re.sub(r'[^a-zA-Z0-9_]', '_', value)


def sanitize_metric_name(value: str) -> str:
    """Sanitize a string to be a valid Prometheus metric name"""
    value = value.lower()
    value = re.sub(r'[^a-z0-9_]', '_', value)
    if re.match(r'^\d', value):
        value = "_" + value
    return value


async def update_metrics(host, port, key, service_code):

    while True:
        data = await fetch_all_values(host, port, key, service_code)
        
        for key, value in data.items():
            # Teile aufteilen
            if '/' in key:
                metric_base, metric_type = key.rsplit('/', 1)
            else:
                metric_base, metric_type = key, "value"

            metric_name = sanitize_metric_name(metric_base.split(":")[-1])  # letzter Teil nach ":"
            label_value = sanitize_label(metric_type)
            
            if metric_name not in gauges:
                gauges[metric_name] = Gauge(metric_name, f"SCB metric {metric_base}", ["type"])
            
            gauges[metric_name].labels(type=label_value).set(value)
            print(f"{metric_name}{{type={label_value}}} = {value}")
        
        await asyncio.sleep(15)


async def main():
    start_http_server(8080)  # Prometheus liest hier
    print("Exporter running on :8080")

    await update_metrics(host, port, key, service_code)


if __name__ == "__main__":
    # Beispielaufruf
    # host = ""  # IP oder Hostname deines WR
    # key = ""  # User-Passwort vom WR
    port = 80                   # oder 443 wenn HTTPS
    service_code = None         # nur wenn du dich mit "master" anmelden willst

    try:
        asyncio.run(main())
    except RuntimeError:  # z.B. in Jupyter / VSCode
        loop = asyncio.get_event_loop()
        loop.create_task(main())
