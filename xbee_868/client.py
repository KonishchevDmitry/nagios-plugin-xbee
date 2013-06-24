"""Client module for XBee 868 monitor."""

from __future__ import unicode_literals

import errno
import json
import socket
import struct

from xbee_868 import constants
from xbee_868 import system
from xbee_868.core import Error


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
            size_format = b"!Q"
            size = system.read(sock.fileno(), struct.calcsize(size_format))
            size, = struct.unpack(size_format, size)
            stats = system.read(sock, size)
        except socket.timeout:
            raise Error("The request timed out.")
        except EOFError:
            raise Error("The server rejected the request.")

        try:
            return json.loads(stats)
        except ValueError as e:
            raise Error("The server returned an invalid response.")
    except Exception as e:
        raise Error("Error while receiving sensor statistics from XBee 868 monitoring server: {0}", e)
