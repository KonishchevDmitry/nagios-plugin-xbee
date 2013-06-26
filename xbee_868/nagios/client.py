"""Client module for XBee 868 monitor."""

from __future__ import unicode_literals

import errno
import json
import socket
import struct

from psys import eintr_retry

from xbee_868.common import constants
from xbee_868.common.core import Error, LogicalError


def metrics(host):
    """Returns metrics for the specified host."""

    return _send("metrics", { "host": host })


def uptime():
    """Returns monitor service uptime."""

    return _send("uptime")


def _send(method, request=None):
    """Sends a request to the monitor."""

    try:
        request = (request or {}).copy()

        if "method" in request:
            raise LogicalError()

        request["method"] = method

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

        size_format = b"!Q"

        try:
            message = json.dumps(request).encode("utf-8")
            sock.sendall(struct.pack(size_format, len(message)) + message)

            message = bytearray()

            data = "-"
            while data:
                data = eintr_retry(sock.recv)(constants.BUFSIZE)
                message.extend(data)

            message = bytes(message)
        except socket.timeout:
            raise Error("The request timed out.")

        size_length = struct.calcsize(size_format)

        if len(message) < size_length:
            raise Error("The server rejected the request.")

        size, = struct.unpack_from(size_format, message)

        if len(message) < size_length + size:
            raise Error("The server rejected the request.")

        if len(message) != size_length + size:
            raise Error("The server returned a malformed response.")

        try:
            reply = json.loads(message[size_length:].decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise Error("The server returned an invalid response.")
    except Exception as e:
        raise Error("XBee 868 monitor request failed: {0}", e)

    if "error" in reply or "result" not in reply:
        raise Error(reply.get("error", "Unknown error."))

    return reply["result"]
