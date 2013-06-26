"""Client module for XBee 868 monitor."""

from __future__ import unicode_literals

import errno
import json
import socket
import struct

from psys import eintr_retry

from xbee_868.common import constants
from xbee_868.common.core import Error


def get_stats():
    """Requests sensor statistics from the server."""

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(constants.IPC_TIMEOUT)

        try:
            sock.connect(constants.SERVER_SOCKET_PATH)
        except socket.timeout:
            raise Error("Connection timed out.")
        except socket.error as e:
            if e.errno in (errno.ENOENT, errno.ECONNREFUSED):
                raise Error("Unable to connect to the server. May be it's not running?")
            else:
                raise e

        try:
            sock.shutdown(socket.SHUT_WR)

            stats = bytearray()

            data = "empty"
            while data:
                data = eintr_retry(sock.recv)(constants.BUFSIZE)
                stats.extend(data)

            stats = bytes(stats)
        except socket.timeout:
            raise Error("The request timed out.")

        size_format = b"!Q"
        size_length = struct.calcsize(size_format)

        if len(stats) < size_length:
            raise Error("The server rejected the request.")

        size, = struct.unpack_from(size_format, stats)

        if len(stats) < size_length + size:
            raise Error("The server rejected the request.")

        if len(stats) != size_length + size:
            raise Error("The server returned a malformed response.")

        try:
            return json.loads(stats[size_length:].decode("utf-8"))
        except ValueError as e:
            raise Error("The server returned an invalid response.")
    except Exception as e:
        raise Error("Error while receiving sensor statistics from XBee 868 monitoring server: {0}", e)
