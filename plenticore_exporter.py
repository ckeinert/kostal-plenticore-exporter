import asyncio
import re
import signal
import sys
import os
import math
import logging
from aiohttp import ClientSession, ClientTimeout
from pykoplenti import ApiClient
from typing import Optional, Any, Callable, Awaitable, Dict
from session_cache import SessionCache
from collections import defaultdict
from prometheus_client import start_http_server, Gauge

# Logger konfigurieren
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Umgebungsvariablen prüfen
host = os.getenv("PLENTICORE_HOST")
key = os.getenv("PLENTICORE_PASSWORD")

if not host or not key:
    logger.error("PLENTICORE_HOST und PLENTICORE_PASSWORD müssen gesetzt sein!")
    sys.exit(1)

# Signal-Event für Graceful Shutdown
shutdown_event = asyncio.Event()
gauges: Dict[str, Gauge] = {}


def graceful_exit(signum, frame):
    logger.info("Stopping gracefully...")
    shutdown_event.set()


# Signal-Handler registrieren
signal.signal(signal.SIGTERM, graceful_exit)
signal.signal(signal.SIGINT, graceful_exit)


async def command_main(
    host: str,
    port: int,
    key: Optional[str],
    service_code: Optional[str],
    fn: Callable[[ApiClient], Awaitable[Dict[str, float]]],
) -> Dict[str, float]:
    async with ClientSession(timeout=ClientTimeout(total=10)) as session:
        client = ApiClient(session, host=host, port=port)
        session_cache = SessionCache(host, "user" if service_code is None else "master")
        client.session_id = session_cache.read_session_id()

        me = await client.get_me()
        if not me.is_authenticated:
            if key is None:
                raise ValueError("Could not reuse session and no login key is given.")
            await client.login(key=key, service_code=service_code)
            if client.session_id:
                session_cache.write_session_id(client.session_id)

        return await fn(client)


async def fetch_all_values(host, port, key, service_code) -> Dict[str, float]:
    async def fetch_values(client: ApiClient) -> Dict[str, float]:
        try:
            all_data = await client.get_process_data()
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Prozessdaten: {e}")
            return {}

        if not all_data:
            logger.warning("Keine Prozessdaten vom Client erhalten")
            return {}

        query = defaultdict(list)
        for module_id, values in all_data.items():
            query[module_id].extend(values)

        try:
            values = await client.get_process_data_values(query)
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Werte: {e}")
            return {}

        result = {}
        for module_id, vdict in values.items():
            for entry in vdict.values():
                value = getattr(entry, "value", float('nan'))
                if value is None:
                    value = float('nan')
                entry_id = getattr(entry, "id", "unknown")
                result[f"{module_id}/{entry_id}"] = value

        return result

    try:
        return await command_main(host, port, key, service_code, fetch_values)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        logger.warning("Inverter reagierte nicht rechtzeitig")
        return {}
    except Exception as e:
        logger.error(f"Unbekannter Fehler beim Abrufen der Werte: {e}")
        return {}


def sanitize_label(value: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_]', '_', value)


def sanitize_metric_name(value: str) -> str:
    value = value.lower()
    value = re.sub(r'[^a-z0-9_]', '_', value)
    if re.match(r'^\d', value):
        value = "_" + value
    return value


async def update_metrics(host, port, key, service_code):
    while not shutdown_event.is_set():
        try:
            data = await fetch_all_values(host, port, key, service_code)
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Metriken: {e}")
            data = {}

        for full_key, value in data.items():
            if '/' in full_key:
                metric_base, metric_type = full_key.rsplit('/', 1)
            else:
                metric_base, metric_type = full_key, "value"

            metric_name = sanitize_metric_name(metric_base.split(":")[-1])
            label_value = sanitize_label(metric_type)

            if metric_name not in gauges:
                gauges[metric_name] = Gauge(metric_name, f"SCB metric {metric_base}", ["type"])

            gauges[metric_name].labels(type=label_value).set(value)
            logger.debug(f"{metric_name}{{type={label_value}}} = {value}")

        await asyncio.wait([shutdown_event.wait()], timeout=15)


async def main():
    start_http_server(8080)
    logger.info("Exporter running on :8080")
    await update_metrics(host, port, key, service_code)


if __name__ == "__main__":
    port = 80
    service_code = None

    try:
        asyncio.run(main())
    except RuntimeError:  # z.B. in Jupyter / VSCode
        loop = asyncio.get_event_loop()
        loop.create_task(main())
