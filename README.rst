=====================================
Kostal Plenticore Prometheus Exporter
=====================================

This is a Prometheus exporter for the `Kostal Plenticore <https://www.kostal-solar-electric.com/en-gb/products>`_ series of inverters.
It exports the metrics exposed by the inverter in `Prometheus <https://prometheus.io>`_ format.
This way it can be ingested into Prometheus and used for `Grafana <https://grafana.com/>`_ dashboards or to trigger notifications in case of failure events.

Usage
=====

Run the ``kostal-plenticore-exporter`` passing it the IP address of the inverter and the password of the operator user.
As command line arguments can be seen by other users on the system, the password should be passed via environment
variable::

    PASSWORD="my super secret" kostal-plenticore-exporter 192.168.1.3

The metrics will be default be exposed at `<http://localhost:9876/>`_.
See ``kostal-plenticore-exporter --help`` for all arguments available.

Alternatively, you can also invoke the Python module: ``python3 -m kostal_plenticore_exporter --help``.

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
