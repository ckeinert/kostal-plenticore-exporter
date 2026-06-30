import asyncio
import re
import signal
import sys
import os
import math
import logging
from aiohttp import ClientSession, ClientTimeout, TCPConnector
from aiohttp import web
from pykoplenti import ApiClient
from pykoplenti.api import NotAuthorizedException
from typing import Optional, Any, Callable, Awaitable, Dict
from session_cache import SessionCache
from collections import defaultdict
from prometheus_client import generate_latest, Gauge
from gauges import ThreadSafeGauges

# Global gauges instance shared between data collection and /metrics endpoint
gauges = ThreadSafeGauges()

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

# Inverter Status Codes (from Kostal documentation)
INVERTER_STATUS_CODES = {
    0: "off",
    1: "init",
    2: "isomeas",
    3: "gridcheck",
    4: "startup",
    5: "-",
    6: "feedin",
    7: "throttled",
    8: "extswitchoff",
    9: "update",
    10: "standby",
    11: "gridsync",
    12: "gridprecheck",
    13: "gridswitchoff",
    14: "overheating",
    15: "shutdown",
    16: "improperdcvoltage",
    17: "esb",
    18: "unknown",
}

BATTERY_STATUS_CODES = {
    0: "idle",
    1: "na",
    2: "emergency_battery_charge",
    4: "na",
    8: "winter_mode_1",
    16: "winter_mode_2",
}


def decode_inverter_status(value: int) -> str:
    """Convert numeric inverter status to human-readable string."""
    return INVERTER_STATUS_CODES.get(int(value), f"unknown_{value}")


def decode_battery_status(value: int) -> str:
    """Convert numeric battery status to human-readable string."""
    return BATTERY_STATUS_CODES.get(int(value), f"unknown_{value}")


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
    connector = TCPConnector(ssl=False)
    async with ClientSession(timeout=ClientTimeout(total=10), connector=connector) as session:
        client = ApiClient(session, host=host, port=port)
        session_cache = SessionCache(host, "user" if service_code is None else "master")
        client.session_id = session_cache.read_session_id()

        try:
            me = await client.get_me()
        except NotAuthorizedException:
            logger.info("Cached session expired, clearing and re-authenticating...")
            session_cache.remove()
            client.session_id = None
            if key is None:
                raise ValueError("Could not reuse session and no login key is given.")
            await client.login(key=key, service_code=service_code)
            if client.session_id:
                session_cache.write_session_id(client.session_id)
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

            for metric_key, value in data.items():
                if '/' in metric_key:
                    metric_base, metric_type = metric_key.rsplit('/', 1)
                else:
                    metric_base, metric_type = metric_key, "value"

                metric_name = sanitize_metric_name(metric_base)
                label_value = sanitize_label(metric_type)

                gauges.get_or_create(
                    metric_name, f"SCB metric {metric_base}", ["type"]
                ).labels(label_value).set(value)
                logger.info(f"{metric_name}{{type={label_value}}} = {value}")
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")

        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=15)
        except asyncio.TimeoutError:
            pass


async def main(host=None, port=None, key=None, service_code=None, inverter_port=None):
    host = host or os.getenv("PLENTICORE_HOST")
    if not host:
        logger.error("PLENTICORE_HOST must be set or provided as argument!")
        sys.exit(1)

    port = port or int(os.getenv("PLENTICORE_EXPORTER_PORT", 8080))
    key = key or os.getenv("PLENTICORE_PASSWORD")
    if not key:
        logger.error("PLENTICORE_PASSWORD must be set or provided as argument!")
        sys.exit(1)

    inverter_port = inverter_port or int(os.getenv("PLENTICORE_API_PORT", 80))

    logger.info(f"Exporter running on :{port}")

    app = web.Application()
    app.router.add_get("/metrics", lambda r: web.Response(
        text=generate_latest().decode("utf-8"), content_type="text/plain"))
    app.router.add_get("/healthz", health_handler)
    app.router.add_get("/ready", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("Exporter serving requests")
    asyncio.create_task(update_metrics(host, inverter_port, key, service_code))
    await shutdown_event.wait()
    await runner.cleanup()


async def health_handler(request):
    """Simple health check endpoint."""
    return web.Response(text="OK", status=200)


def parse_args():
    """Parse command-line arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kostal Plenticore Prometheus Exporter"
    )
    parser.add_argument(
        "host", type=str, nargs="?", default=None, help="Inverter IP address (required or PLENTICORE_HOST env var)"
    )
    parser.add_argument(
        "--port", "-p", type=int, default=8080,
        help="HTTP port for metrics endpoint (default: 8080)"
    )
    parser.add_argument(
        "--api-port", "-a", type=int, default=80,
        help="Inverter API port (default: 80)"
    )
    parser.add_argument(
        "--key", "-k", type=str, default=None,
        help="Login key for authentication"
    )
    parser.add_argument(
        "--service-code", "-s", type=str, default=None,
        help="Service code (e.g., 'master' or 'user')"
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    try:
        asyncio.run(
            main(args.host, args.port, args.key, args.service_code, args.api_port)
        )
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
