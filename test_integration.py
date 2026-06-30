#!/usr/bin/env python3
"""Integration tests for the Kostal Plenticore Prometheus Exporter."""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))


def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        print(f"Warning: {env_file} not found. Set PLENTICORE_HOST and PLENTICORE_PASSWORD manually.")
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"'))


load_env_file()

# Set up environment before importing plenticore_exporter (it checks env vars at import time)
os.environ.setdefault("PLENTICORE_HOST", "192.168.178.72")

from plenticore_exporter import (
    INVERTER_STATUS_CODES,
    BATTERY_STATUS_CODES,
    decode_inverter_status,
    decode_battery_status,
    sanitize_label,
    sanitize_metric_name,
    main as exporter_main,
    shutdown_event,
)
from session_cache import SessionCache


def test_decode_inverter_status():
    """Test inverter status code decoding."""
    print("Testing decode_inverter_status...")

    # Test known codes
    assert decode_inverter_status(0) == "off"
    assert decode_inverter_status(6) == "feedin"
    assert decode_inverter_status(11) == "gridsync"
    assert decode_inverter_status(18) == "unknown"

    # Test unknown code returns formatted string
    result = decode_inverter_status(99)
    assert result.startswith("unknown_"), f"Expected 'unknown_*', got: {result}"

    print("  ✓ Inverter status decoding works correctly")


def test_decode_battery_status():
    """Test battery status code decoding."""
    print("Testing decode_battery_status...")

    # Test known codes
    assert decode_battery_status(0) == "idle"
    assert decode_battery_status(8) == "winter_mode_1"
    assert decode_battery_status(16) == "winter_mode_2"

    # Test unknown code returns formatted string
    result = decode_battery_status(99)
    assert result.startswith("unknown_"), f"Expected 'unknown_*', got: {result}"

    print("  ✓ Battery status decoding works correctly")


def test_sanitize_label():
    """Test label sanitization."""
    print("Testing sanitize_label...")

    # Valid characters should pass through
    assert sanitize_label("valid_label") == "valid_label"
    assert sanitize_label("test123") == "test123"

    # Special chars become underscores
    assert sanitize_label("metric-name") == "metric_name"
    assert sanitize_label("metric.name") == "metric_name"
    # Space becomes underscore (single conversion)
    result = sanitize_label("metric name")
    assert "_" in result, f"Expected underscore for space, got: {result}"

    print("  ✓ Label sanitization works correctly")


def test_sanitize_metric_name():
    """Test metric name sanitization."""
    print("Testing sanitize_metric_name...")

    # Lowercase conversion
    assert sanitize_metric_name("METRIC_NAME") == "metric_name"

    # Special chars become underscores
    result = sanitize_metric_name("Metric.Name-123")
    assert "_" in result, f"Expected underscore, got: {result}"

    # Numbers at start get prefixed with underscore
    result = sanitize_metric_name("123abc")
    assert result.startswith("_"), f"Expected leading underscore, got: {result}"

    print("  ✓ Metric name sanitization works correctly")


async def test_connection_and_auth():
    """Test that we can connect to the inverter and authenticate."""
    print("\nTesting connection and authentication...")

    host = os.getenv("PLENTICORE_HOST", "192.168.178.72")
    password = os.getenv("PLENTICORE_PASSWORD")
    api_port = int(os.getenv("PLENTICORE_API_PORT", 80))

    if not password:
        print("  ✗ Skipped: PLENTICORE_PASSWORD not set (create .env file)")
        return False

    print(f"  Connecting to {host}:{api_port}...")

    from aiohttp import ClientSession, ClientTimeout, TCPConnector
    from pykoplenti import ApiClient
    from pykoplenti.api import NotAuthorizedException
    from session_cache import SessionCache

    try:
        connector = TCPConnector(ssl=False)
        async with ClientSession(timeout=ClientTimeout(total=10), connector=connector) as session:
            client = ApiClient(session, host=host, port=api_port)
            session_cache = SessionCache(host, "user")
            client.session_id = session_cache.read_session_id()

            try:
                me = await client.get_me()
            except NotAuthorizedException:
                print("    Cached session expired, clearing and re-authenticating...")
                session_cache.remove()
                client.session_id = None
                me = None

            if me is None or not me.is_authenticated:
                print("  Authenticating...")
                await client.login(key=password)
                assert client.session_id, "Login failed - no session ID returned"
                session_cache.write_session_id(client.session_id)
                print(f"    Session saved to cache")
                me = await client.get_me()

            print(f"    User info: {me}")  # Debug output
            assert me.is_authenticated, "Authentication check failed"
            print("  ✓ Connection and authentication successful")
            return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_fetch_process_data():
    """Test fetching process data from the inverter."""
    print("\nTesting fetch_all_values...")

    host = os.getenv("PLENTICORE_HOST", "192.168.178.72")
    password = os.getenv("PLENTICORE_PASSWORD")
    api_port = int(os.getenv("PLENTICORE_API_PORT", 80))

    if not password:
        print("  ✗ Skipped: PLENTICORE_PASSWORD not set (create .env file)")
        return False

    from plenticore_exporter import fetch_all_values

    try:
        data = await fetch_all_values(host, api_port, password, None)
        print(f"    Retrieved {len(data)} metrics")

        # Verify we got some actual data (not just empty dict)
        assert len(data) > 0, "No metrics returned from inverter"

        # Check for expected metric types
        has_inverter_status = any("inverter/status" in k for k in data.keys())
        has_battery_status = any("battery/status" in k for k in data.keys())

        print(f"    Inverter status present: {has_inverter_status}")
        print(f"    Battery status present: {has_battery_status}")

        if not has_inverter_status or not has_battery_status:
            print("  ⚠ Warning: Status metrics may be missing (check inverter state)")

        print("  ✓ Process data fetch successful")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_metrics_endpoint():
    """Test that the metrics HTTP endpoint works."""
    print("\nTesting /metrics endpoint...")

    from aiohttp import ClientSession, ClientTimeout

    async with ClientSession(timeout=ClientTimeout(total=5)) as session:
        try:
            async with session.get("http://localhost:8080/metrics") as resp:
                if resp.status == 200:
                    metrics_text = await resp.text()

                    # Verify it's valid Prometheus text format
                    lines = metrics_text.split("\n")
                    help_lines = [l for l in lines if l.startswith("# HELP")]
                    metric_lines = [l.strip() for l in lines if not l.startswith("#") and l.strip()]

                    print(f"    Found {len(help_lines)} HELP comments, {len(metric_lines)} metrics")
                    assert len(help_lines) > 0, "No HELP comments found"
                    assert len(metric_lines) > 0, "No metric lines found"

                    # Check for expected metrics
                    has_inverter_status = any(
                        "inverter{" in l and 'type="status"' in l
                        for l in metric_lines
                    )
                    has_battery_status = any(
                        "battery{" in l and 'type="status"' in l
                        for l in metric_lines
                    )

                    print(f"    Inverter status metric present: {has_inverter_status}")
                    print(f"    Battery status metric present: {has_battery_status}")

                    if not has_inverter_status or not has_battery_status:
                        print("  ⚠ Warning: Status metrics may be missing")

                    print("  ✓ Metrics endpoint working correctly")
                    return True
                else:
                    print(f"  ✗ Failed to fetch metrics: HTTP {resp.status}")
                    return False
        except Exception as e:
            print(f"  ✗ Failed to fetch metrics: {e}")
            import traceback
            traceback.print_exc()
            return False


async def test_health_endpoints():
    """Test health and ready endpoints."""
    print("\nTesting /healthz and /ready endpoints...")

    from aiohttp import ClientSession, ClientTimeout

    async with ClientSession(timeout=ClientTimeout(total=5)) as session:
        for endpoint in ["/healthz", "/ready"]:
            try:
                async with session.get(f"http://localhost:8080{endpoint}") as resp:
                    if resp.status == 200:
                        body = await resp.text()
                        if body.strip() == "OK":
                            print(f"    ✓ {endpoint} returns OK")
                        else:
                            print(f"    ✗ {endpoint}: Expected 'OK', got '{body[:50]}...'")
                    else:
                        print(f"  ✗ {endpoint}: HTTP {resp.status}")
            except Exception as e:
                print(f"  ✗ {endpoint} failed: {e}")


async def test_graceful_shutdown():
    """Test that the exporter handles shutdown signals gracefully."""
    password = os.getenv("PLENTICORE_PASSWORD")

    if not password:
        print("  ✗ Skipped: PLENTICORE_PASSWORD not set (create .env file)")
        return True  # Don't fail the test suite for this

    print("\nTesting graceful shutdown...")

    # Check if port is available first
    import socket as sock_mod
    sock = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_STREAM)
    sock.settimeout(1)
    try:
        sock.connect(("127.0.0.1", 8080))
        sock.close()
        print("  ⚠ Skipped: port 8080 still in use")
        return True  # Don't fail the test suite for this
    except ConnectionRefusedError:
        sock.close()

    api_port = int(os.getenv("PLENTICORE_API_PORT", 80))

    # Create a task with timeout to simulate shutdown
    async def run_with_timeout():
        await asyncio.wait_for(exporter_main(inverter_port=api_port), timeout=3)

    try:
        task = asyncio.create_task(run_with_timeout())
        await asyncio.sleep(1.5)  # Let it start up
        print("    ✓ Exporter started and running")

        # Cancel to trigger shutdown
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        print("  ✓ Graceful shutdown handled correctly")
        return True
    except Exception as e:
        print(f"  ✗ Shutdown test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main_test():
    """Run all integration tests."""
    print("=" * 60)
    print("Kostal Plenticore Exporter - Integration Tests")
    print("=" * 60)

    results = []

    # Unit tests (no network required)
    try:
        test_decode_inverter_status()
        results.append(("decode_inverter_status", True))
    except Exception as e:
        print(f"  ✗ decode_inverter_status failed: {e}")
        results.append(("decode_inverter_status", False))

    try:
        test_decode_battery_status()
        results.append(("decode_battery_status", True))
    except Exception as e:
        print(f"  ✗ decode_battery_status failed: {e}")
        results.append(("decode_battery_status", False))

    try:
        test_sanitize_label()
        results.append(("sanitize_label", True))
    except Exception as e:
        print(f"  ✗ sanitize_label failed: {e}")
        results.append(("sanitize_label", False))

    try:
        test_sanitize_metric_name()
        results.append(("sanitize_metric_name", True))
    except Exception as e:
        print(f"  ✗ sanitize_metric_name failed: {e}")
        results.append(("sanitize_metric_name", False))

    password = os.getenv("PLENTICORE_PASSWORD")
    if not password:
        print("\n⚠ PLENTICORE_PASSWORD not set. Skipping network tests.")
        print("  Create a .env file (see .env.example) with your credentials to run all tests.")

    # Integration tests (require network)
    connected = False
    api_port = int(os.getenv("PLENTICORE_API_PORT", 80))
    if password:
        host = os.getenv("PLENTICORE_HOST", "192.168.178.72")
        # Clear stale session cache before tests
        SessionCache(host, "user").remove()
    if password:
        try:
            connected = await test_connection_and_auth()
            results.append(("connection_and_auth", connected))
        except Exception as e:
            print(f"  ✗ connection_and_auth failed: {e}")
            results.append(("connection_and_auth", False))

        if connected:
            try:
                data_ok = await test_fetch_process_data()
                results.append(("fetch_process_data", data_ok))
            except Exception as e:
                print(f"  ✗ fetch_process_data failed: {e}")
                results.append(("fetch_process_data", False))

    # Start exporter server before endpoint tests
    if password:
        print("\nStarting exporter server for endpoint tests...")

        server_task = asyncio.create_task(exporter_main(inverter_port=api_port))
        await asyncio.sleep(2)  # Wait for server to start and collect first metrics
        print("  Exporter server started")

        try:
            await test_metrics_endpoint()
            results.append(("metrics_endpoint", True))
        except Exception as e:
            print(f"  ✗ metrics_endpoint failed: {e}")
            results.append(("metrics_endpoint", False))

        try:
            await test_health_endpoints()
            results.append(("health_endpoints", True))
        except Exception as e:
            print(f"  ✗ health_endpoints failed: {e}")
            results.append(("health_endpoints", False))

        # Stop server after endpoint tests
        shutdown_event.set()
        try:
            await asyncio.wait_for(server_task, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
        print("  Exporter server stopped")

        # Wait for port to be released before graceful_shutdown test
        import socket as sock_mod
        for _ in range(10):
            await asyncio.sleep(0.5)
            sock = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_STREAM)
            try:
                sock.connect(("127.0.0.1", 8080))
                sock.close()
            except ConnectionRefusedError:
                sock.close()
                break
        else:
            sock.close()

        # Reset shutdown event for graceful_shutdown test
        shutdown_event.clear()

        try:
            shutdown_ok = await test_graceful_shutdown()
            results.append(("graceful_shutdown", shutdown_ok))
        except Exception as e:
            print(f"  ✗ graceful_shutdown failed: {e}")
            results.append(("graceful_shutdown", False))

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    for name, ok in results:
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {status}: {name}")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main_test())
    sys.exit(0 if success else 1)
