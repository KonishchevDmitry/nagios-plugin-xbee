"""Monitor client request handlers."""

from __future__ import unicode_literals

import logging

from xbee_868.common.core import Error

import xbee_868.monitor.stats
from xbee_868 import monitor
xbee_868 # Suppress PyFlakes warnings

_HANDLERS = {}
"""Registered handlers."""

LOG = logging.getLogger(__name__)


def handle(method, params):
    """Handles monitor client request."""

    try:
        handler = _HANDLERS[method]
    except KeyError:
        raise Error("Invalid method: {0}.", method)

    return handler(**params)


def _handler(method):
    """Registers a request handlers."""

    def register(handler):
        if method in _HANDLERS:
            raise Error("Handler for method {0} is already registered.", method)

        _HANDLERS[method] = handler
        return handler

    return register


@_handler("uptime")
def _uptime():
    """Returns monitor service uptime."""

    return { "uptime": monitor.stats.uptime() }
