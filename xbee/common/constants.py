"""Contains all constants."""

from __future__ import unicode_literals


KILOBYTE = 1024
"""Bytes in kilobyte."""

MEGABYTE = 1024 * KILOBYTE
"""Bytes in megabyte."""


BUFSIZE = 4 * KILOBYTE
"""I/O buffer size."""

SERVER_SOCKET_PATH = "/var/run/xbee-monitor"
"""Path to the server socket."""

IPC_TIMEOUT = 10
"""Timeout for IPC requests."""
