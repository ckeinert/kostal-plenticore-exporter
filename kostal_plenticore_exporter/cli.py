from wsgiref.simple_server import make_server

import click
from prometheus_client import CollectorRegistry, make_wsgi_app

from .collector import PlenticoreCollector


@click.command()
@click.option(
    "--password",
    envvar="PASSWORD",
    required=True,
    show_envvar=True,
    help="Password of the operator user. For security reasons this should be passed via environment variable."
)
@click.option(
    "--bind-ip",
    envvar="BIND_IP",
    help="IP on which to serve metrics.",
    default="127.0.0.1",
    show_default=True
)
@click.option(
    "--bind-port",
    envvar="BIND_PORT",
    type=int,
    help="Port on which to serve metrics.",
    default=9876,
    show_default=True
)
@click.option(
    "--inverter_address",
    envvar="INVERTER_ADDRESS",
    required=True,
    help="IP of the Kostal inverter."
)

def cli(inverter_address: str, password: str, bind_ip: str, bind_port: int):
    """Export metrics of the Kostal Plenticore at INVERTER_ADDRESS as Prometheus metrics."""
    collector = PlenticoreCollector(inverter_address, password)
    registry = CollectorRegistry()
    registry.register(collector)

    app = make_wsgi_app(registry)
    click.echo(f"Serving metrics on http://{bind_ip}:{bind_port}")
    with make_server(bind_ip, bind_port, app) as httpd:
        httpd.serve_forever()
