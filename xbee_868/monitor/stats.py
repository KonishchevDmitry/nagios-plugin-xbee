"""Collects all monitor's statistics."""

from __future__ import unicode_literals

import time

from xbee_868.common.core import Error

_MONITOR_START_TIME = None
"""The monitor service start time."""


def monitor_started():
    """Called on the monitor start."""

    global _MONITOR_START_TIME

    if _MONITOR_START_TIME is not None:
        raise Error("The monitor is already started.")

    _MONITOR_START_TIME = time.time()


def uptime():
    """Returns current monitor uptime."""

    if _MONITOR_START_TIME is None:
        raise Error("The monitor is not started.")

    return int(time.time() - _MONITOR_START_TIME)
