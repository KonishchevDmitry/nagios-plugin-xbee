"""Monitor client request handlers."""

from __future__ import unicode_literals

import logging

from xbee.common.core import Error

import xbee.monitor.stats
from xbee import monitor

xbee # Suppress PyFlakes warnings

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


@_handler("metrics")
def _metrics(host):
    """Returns metrics for the specified host."""

    return monitor.stats.get_metrics(host)


@_handler("uptime")
def _uptime():
    """Returns monitor service uptime."""

    return monitor.stats.get_uptime()
