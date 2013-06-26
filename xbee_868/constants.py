"""Contains all constants."""

from __future__ import unicode_literals


BUFSIZE = 4 * 1024
"""I/O buffer size."""

CONFIG_PATH = "/etc/xbee-868-monitor.conf"
"""Configuration file path."""

SERVER_SOCKET_PATH = "/var/run/xbee-868/monitor.socket"
"""Path to the server socket."""

IPC_TIMEOUT = 10
"""Timeout for IPC requests."""
