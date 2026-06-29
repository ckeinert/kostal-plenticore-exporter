=====================================
Kostal Plenticore Prometheus Exporter
=====================================

This is a Prometheus exporter for the `Kostal Plenticore <https://www.kostal-solar-electric.com/en-gb/products>`_ series of inverters.
It exports the metrics exposed by the inverter in `Prometheus <https://prometheus.io>`_ format.
This way it can be ingested into Prometheus and used for `Grafana <https://grafana.com/>`_ dashboards or to trigger notifications in case of failure events.

Usage
=====

Run the exporter with the inverter IP address and authentication credentials.
Command line arguments are visible to other users on the system, so prefer environment variables::

    PLENTICORE_PASSWORD="my super secret" kostal-plenticore-exporter 192.168.1.3

The metrics will be exposed at `<http://localhost:8080/metrics>`_.
See ``kostal-plenticore-exporter --help`` for all arguments available.

Alternatively, you can also invoke the Python module: ``python3 -m kostal_plenticore_exporter --help``.

CLI Arguments
-------------

The exporter supports the following command-line options:

* ``<host>`` — IP address of the inverter (required)
* ``--port``, ``-p <port>`` — HTTP port for metrics endpoint (default: 8080)
* ``--key``, ``-k <key>`` — Login key for authentication
* ``--service-code``, ``-s <code>`` — Service code (e.g., "master" or "user")

Example with all arguments::

    kostal-plenticore-exporter 192.168.1.3 --port 9876 --key myloginkey --service-code master


Docker Compose Configuration
============================

The exporter can be run via Docker Compose for easy deployment and management.

Prerequisites
-------------

* Docker installed on your system
* A `.env` file with the following variables::

    PLENTICORE_HOST=192.168.1.3
    PLENTICORE_PASSWORD=my super secret
    PLENTICORE_EXPORTER_PORT=8080

  Alternatively, you can use Docker secrets (more secure for production)::

    docker secret create plenticore_host < host_file.txt
    docker secret create plenticore_password < password_file.txt

* A `docker-compose.yml` file in the exporter directory::

    version: "3.8"

    services:
      plenticore-exporter:
        image: z7x5fm937w/kostal-plenticore-exporter:latest
        container_name: kostal-exporter
        restart: unless-stopped
        ports:
          - "8080:8080"
        environment:
          - PLENTICORE_HOST=${PLENTICORE_HOST}
          - PLENTICORE_PASSWORD=${PLENTICORE_PASSWORD}
          - PLENTICORE_EXPORTER_PORT=${PLENTICORE_EXPORTER_PORT}
        secrets:
          - plenticore_host
          - plenticore_password

    secrets:
      plenticore_host:
        external: true
      plenticore_password:
        external: true

  Or using a mounted `.env` file::

    version: "3.8"

    services:
      plenticore-exporter:
        image: z7x5fm937w/kostal-plenticore-exporter:latest
        container_name: kostal-exporter
        restart: unless-stopped
        ports:
          - "8080:8080"
        env_file: .env

* Build the image locally (optional, for development)::

    docker build -t kostal-plenticore-exporter .


Running with Docker Compose
---------------------------

1. Place your `.env` file in the exporter directory (or create secrets as shown above)
2. Start the container::

    docker compose up -d

3. Verify it's running and accessible::

    curl http://localhost:8080/healthz
    # Should return "OK"

4. Check metrics are being exported::

    curl http://localhost:8080/metrics | grep "^# HELP"


Inverter Authentication Setup
==============================

Before deploying, ensure the inverter is properly configured for authentication:

1. Log into the Plenticore web UI with your operator account
2. Navigate to **Settings** → **User Management** (or similar)
3. Verify that a password has been set for your user account
4. Test login — you should be able to access the UI without being prompted for a "service technician installation code"

If you see the service technician prompt, the inverter may have reset its configuration or the password was not properly saved. Re-enter your credentials and ensure they are stored correctly.


Status Metrics
==============

Some metrics export state as a numeric value.
These decoded meanings of these values are given in `the interface description document available on the Kostal product page <https://www.kostal-solar-electric.com/en-gb/products/hybrid-inverter/plenticore-plus/>`_.

For the ``kostal_plenticore_inverter_status`` metric these values are:

* 0: Off
* 1: Init
* 2: IsoMeas
* 3: GridCheck
* 4: StartUp
* 5: -
* 6: FeedIn
* 7: Throttled
* 8: ExtSwitchOff
* 9: Update
* 10: Standby
* 11: GridSync
* 12: GridPreCheck
* 13: GridSwitchOff
* 14: Overheating
* 15: Shutdown
* 16: ImproperDcVoltage
* 17: ESB
* 18: Unknown

For the ``kostal_plenticore_battery_status`` metric, which is called `energy manager status` in the document, these values are:

* 0: Idle
* 1: n/a
* 2: Emergency Battery Charge
* 4: n/a
* 8: Winter Mode Step 1; on the UI and in the user manual this is `Battery Sleep Mode 1`.
* 16: Winter Mode Step 2; on the UI and in the user manual this is `Battery Sleep Mode 2`.

License
=======

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see `<http://www.gnu.org/licenses/>`_.


Notes
=======

# Forked from kostal-plenticore-exporter

This program is developed by Marix. You can find the original repo on Codeberg:  
[https://codeberg.org/Marix/kostal-plenticore-exporter](https://codeberg.org/Marix/kostal-plenticore-exporter)

Original author: @Marix on Codeberg
