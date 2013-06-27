"""Collects all monitor's statistics."""

from __future__ import unicode_literals

import time

from xbee.common.core import Error

from xbee.monitor import config


_MONITOR_START_TIME = None
"""The monitor service start time."""

_METRICS = {}
"""Recorded metrics."""


def monitor_started():
    """Called on the monitor start."""

    global _MONITOR_START_TIME

    if _MONITOR_START_TIME is not None:
        raise Error("The monitor is already started.")

    _MONITOR_START_TIME = time.time()


def get_uptime():
    """Returns current monitor uptime."""

    if _MONITOR_START_TIME is None:
        raise Error("The monitor is not started.")

    return int(time.time() - _MONITOR_START_TIME)



def add_metric(host, name, value):
    """Adds a new metric."""

    _METRICS.setdefault(host, {})[name] = {
        "time":  int(time.time()),
        "value": value,
    }


def get_metrics(host):
    """Returns recorded metrics for the specified host."""

    if host not in config.HOSTS:
        raise Error("Unknown host {0}.", host)

    return _METRICS.get(host, {})
