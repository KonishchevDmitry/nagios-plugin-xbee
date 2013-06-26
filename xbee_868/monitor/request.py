"""Monitor client request handlers."""

from __future__ import unicode_literals

import logging

from xbee_868.common.core import Error

import xbee_868.monitor.stats
from xbee_868 import monitor
xbee_868 # Suppress PyFlakes warnings

LOG = logging.getLogger(__name__)


def handle(request):
    """Handles monitor client request."""

    if request["method"] == "uptime":
        return { "uptime": monitor.stats.uptime() }
    else:
        raise Error("Invalid method: {0}.", request["method"])
